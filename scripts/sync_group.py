#!/usr/bin/env python3
"""Generate Group page from CV source sections.

Rules:
- Graduate students: Graduate Committees rows with role Chair and degree In progress
- Postdocs: Postdoctoral Scholars Supervised rows with years containing Present
  - if note contains KITP Fellow => role "Postdoc (KITP)", else "Postdoc"
- Undergrads: Undergraduate Students Supervised rows with years containing Present

Persistent profile mapping (data/group_profiles.json):
- Keeps image paths and member lifecycle metadata.
- Current members have active=true and alumni fields set to null.
- Members no longer in current lists are marked active=false and shown in
  a Former Group Members table.
- Former member seed data is parsed from CV sections:
  - Postdoctoral Scholars Supervised rows without "Present"
  - Undergraduate Students Supervised rows without "Present"
"""

from __future__ import annotations

import argparse
import html
import json
import re
from dataclasses import dataclass
from pathlib import Path

SECTION_RE = re.compile(r"\\cvsection(?:\[[^\]]*\])?\{([^}]*)\}")


@dataclass
class Person:
    name: str
    role: str


@dataclass
class FormerSeed:
    name: str
    role: str
    years_in_group: str | None


def _display_name(name: str) -> str:
    n = " ".join(name.split())
    if "," in n:
        last, first = [part.strip() for part in n.split(",", 1)]
        if first:
            return f"{first} {last}"
    return n


def _clean_cell(cell: str) -> str:
    s = cell.strip()
    s = re.sub(r"\\textbf\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\emph\{([^}]*)\}", r"\1", s)
    s = re.sub(r"\\url\{([^}]*)\}", r"\1", s)
    s = s.replace("\\&", "&")
    return " ".join(s.split())


def _section_block(tex: str, title: str) -> str:
    matches = list(SECTION_RE.finditer(tex))
    for i, m in enumerate(matches):
        if m.group(1).strip() == title:
            start = m.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(tex)
            return tex[start:end]
    raise ValueError(f"Section '{title}' not found")


def _parse_rows(section_text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw in section_text.splitlines():
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        if not line.endswith("\\\\") or line.startswith("\\"):
            continue
        body = line[:-2].strip()
        if not body or "&" not in body:
            continue
        cols = [_clean_cell(c) for c in body.split("&")]
        if cols and any("Student Name" in c or "Degree Completed" in c or "Project Title" in c for c in cols):
            continue
        rows.append(cols)
    return rows


def collect_people(tex: str) -> tuple[list[Person], list[Person], list[Person]]:
    grads: list[Person] = []
    postdocs: list[Person] = []
    undergrads: list[Person] = []

    grad_block = _section_block(tex, "Graduate Committees")
    for cols in _parse_rows(grad_block):
        if len(cols) < 3:
            continue
        name, degree, role = cols[0], cols[1], cols[2]
        if "in progress" in degree.lower() and role.strip().lower() == "chair":
            grads.append(Person(name=_display_name(name), role="Graduate Student"))

    post_block = _section_block(tex, "Postdoctoral Scholars Supervised")
    for cols in _parse_rows(post_block):
        if len(cols) < 4:
            continue
        name, years, note = cols[0], cols[1], cols[2]
        if "present" not in years.lower():
            continue
        role = "Postdoc (KITP)" if "kitp fellow" in note.lower() else "Postdoc"
        postdocs.append(Person(name=_display_name(name), role=role))

    ug_block = _section_block(tex, "Undergraduate Students Supervised")
    for cols in _parse_rows(ug_block):
        if len(cols) < 2:
            continue
        name, years = cols[0], cols[1]
        if "present" not in years.lower():
            continue
        undergrads.append(Person(name=_display_name(name), role="Undergraduate Student"))

    return grads, postdocs, undergrads


def collect_former_seeds(tex: str) -> list[FormerSeed]:
    seeds: list[FormerSeed] = []

    post_block = _section_block(tex, "Postdoctoral Scholars Supervised")
    for cols in _parse_rows(post_block):
        if len(cols) < 3:
            continue
        name, years, note = cols[0], cols[1], cols[2]
        if "present" in years.lower():
            continue
        role = "Postdoc (KITP)" if "kitp fellow" in note.lower() else "Postdoc"
        seeds.append(FormerSeed(name=_display_name(name), role=role, years_in_group=years))

    ug_block = _section_block(tex, "Undergraduate Students Supervised")
    for cols in _parse_rows(ug_block):
        if len(cols) < 2:
            continue
        name, years = cols[0], cols[1]
        if "present" in years.lower():
            continue
        seeds.append(FormerSeed(name=_display_name(name), role="Undergraduate Student", years_in_group=years))

    return seeds


def _load_profile_map(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 3, "people": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"schema_version": 3, "people": {}}
    people = data.get("people")
    if not isinstance(people, dict):
        people = {}
    return {"schema_version": 3, "people": people}


def _load_legacy_photo_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    people = data.get("people") if isinstance(data, dict) else None
    if not isinstance(people, dict):
        return {}
    out: dict[str, str] = {}
    for name, info in people.items():
        if isinstance(info, dict):
            image = str(info.get("image") or "").strip()
            if image:
                out[name] = image
    return out


def _normalize_entry(entry: dict | None, placeholder_path: str) -> dict:
    e = entry if isinstance(entry, dict) else {}
    return {
        "image": str(e.get("image") or placeholder_path),
        "active": bool(e.get("active", True)),
        "role_in_group": e.get("role_in_group"),
        "years_in_group": e.get("years_in_group"),
        "role_after_group": e.get("role_after_group"),
        "current_role": e.get("current_role"),
    }


def _sync_profile_map(
    path: Path,
    people: list[Person],
    former_seeds: list[FormerSeed],
    placeholder_path: str,
) -> dict[str, dict]:
    data = _load_profile_map(path)
    people_map: dict[str, dict] = {
        name: _normalize_entry(info, placeholder_path) for name, info in data["people"].items()
    }

    current = {person.name: person for person in people}

    for name, person in current.items():
        entry = people_map.get(name) or _normalize_entry({}, placeholder_path)
        entry["image"] = str(entry.get("image") or placeholder_path)
        entry["active"] = True
        entry["role_in_group"] = person.role
        if not entry.get("years_in_group"):
            entry["years_in_group"] = None
        entry["role_after_group"] = None
        entry["current_role"] = None
        people_map[name] = entry

    for seed in former_seeds:
        if seed.name in current:
            continue
        entry = people_map.get(seed.name) or _normalize_entry({}, placeholder_path)
        entry["image"] = str(entry.get("image") or placeholder_path)
        entry["active"] = False
        if not entry.get("role_in_group"):
            entry["role_in_group"] = seed.role
        if not entry.get("years_in_group"):
            entry["years_in_group"] = seed.years_in_group
        people_map[seed.name] = entry

    for name, entry in list(people_map.items()):
        if name in current:
            continue
        e = _normalize_entry(entry, placeholder_path)
        e["active"] = False
        people_map[name] = e

    ordered = {name: people_map[name] for name in sorted(people_map)}
    payload = {"schema_version": 3, "people": ordered}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    return ordered


def _render_cards(people: list[Person], profiles: dict[str, dict], placeholder_path: str) -> str:
    if not people:
        return "<p>No active members listed right now.</p>\n"

    lines = ['<div class="people-grid">']
    for person in people:
        info = profiles.get(person.name) or {}
        image_path = str(info.get("image") or placeholder_path)
        if image_path.startswith("http://") or image_path.startswith("https://"):
            image_src = image_path
        else:
            image_src = "{{ '" + image_path + "' | relative_url }}"
        lines.extend(
            [
                '  <article class="person-card">',
                f'    <img src="{image_src}" alt="{html.escape(person.name)}">',
                f"    <h3>{html.escape(person.name)}</h3>",
                f"    <p>{html.escape(person.role)}</p>",
                "  </article>",
            ]
        )
    lines.append("</div>")
    return "\n".join(lines) + "\n"


def _render_former_table(profiles: dict[str, dict]) -> str:
    former = []
    for name, info in profiles.items():
        if info.get("active"):
            continue
        former.append(
            (
                name,
                info.get("role_in_group"),
                info.get("years_in_group"),
                info.get("role_after_group"),
                info.get("current_role"),
            )
        )

    if not former:
        return "<p>No former group members listed yet.</p>\n"

    def show(v: str | None) -> str:
        return html.escape(v) if v else "&mdash;"

    lines = [
        '<table class="former-members-table">',
        "  <thead>",
        "    <tr>",
        "      <th>Name</th>",
        "      <th>Role in Group</th>",
        "      <th>Years in Group</th>",
        "      <th>Role After Group</th>",
        "      <th>Current Role</th>",
        "    </tr>",
        "  </thead>",
        "  <tbody>",
    ]
    for name, role_in_group, years_in_group, role_after_group, current_role in former:
        lines.extend(
            [
                "    <tr>",
                f"      <td>{html.escape(name)}</td>",
                f"      <td>{show(role_in_group)}</td>",
                f"      <td>{show(years_in_group)}</td>",
                f"      <td>{show(role_after_group)}</td>",
                f"      <td>{show(current_role)}</td>",
                "    </tr>",
            ]
        )
    lines.extend(["  </tbody>", "</table>"])
    return "\n".join(lines) + "\n"


def render_page(
    grads: list[Person],
    postdocs: list[Person],
    undergrads: list[Person],
    profiles: dict[str, dict],
    placeholder_path: str,
) -> str:
    front_matter = """---
layout: page
title: Group
permalink: "group.html"
group: basepages
nav_order: 3
hlgroup: group
tagline: Supporting tagline
show_title: false
---
"""

    body = ["## Research Group\n"]

    if grads:
        body.extend([f"### Graduate Students ({len(grads)})\n", _render_cards(grads, profiles, placeholder_path)])
    if postdocs:
        body.extend(
            [f"### Postdoctoral Scholars ({len(postdocs)})\n", _render_cards(postdocs, profiles, placeholder_path)]
        )
    if undergrads:
        body.extend(
            [f"### Undergraduate Students ({len(undergrads)})\n", _render_cards(undergrads, profiles, placeholder_path)]
        )

    body.extend(
        [
            "## Former Group Members\n",
            _render_former_table(profiles),
            "## Collaborators\n",
            "Collaborator list coming soon.\n",
        ]
    )
    return front_matter + "\n".join(body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cv-source", default="cv/source/myresume_master.tex")
    parser.add_argument("--out", default="05-index_group.md")
    parser.add_argument("--placeholder", default="/assets/images/person-placeholder.svg")
    parser.add_argument("--profile-map", default="data/group_profiles.json")
    parser.add_argument("--photo-map", default=None, help="Deprecated alias for --profile-map")
    args = parser.parse_args()

    profile_map_path = Path(args.profile_map or args.photo_map or "data/group_profiles.json")
    legacy_map_path = Path("data/group_photos.json")

    tex = Path(args.cv_source).read_text(encoding="utf-8")
    grads, postdocs, undergrads = collect_people(tex)
    former_seeds = collect_former_seeds(tex)
    all_people = grads + postdocs + undergrads

    if not profile_map_path.exists() and legacy_map_path.exists():
        legacy_images = _load_legacy_photo_map(legacy_map_path)
        migrated = {
            "schema_version": 2,
            "people": {
                name: {
                    "image": img,
                    "active": False,
                    "role_in_group": None,
                    "years_in_group": None,
                    "role_after_group": None,
                    "current_role": None,
                }
                for name, img in sorted(legacy_images.items())
            },
        }
        profile_map_path.parent.mkdir(parents=True, exist_ok=True)
        profile_map_path.write_text(json.dumps(migrated, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    profiles = _sync_profile_map(profile_map_path, all_people, former_seeds, args.placeholder)
    out_text = render_page(grads, postdocs, undergrads, profiles, args.placeholder)
    Path(args.out).write_text(out_text, encoding="utf-8")

    print(f"Wrote {args.out}")
    print(f"Wrote/updated {profile_map_path}")
    print(
        "Counts: "
        f"grads={len(grads)}, postdocs={len(postdocs)}, undergrads={len(undergrads)}, "
        f"former_seed_candidates={len(former_seeds)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
