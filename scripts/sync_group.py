#!/usr/bin/env python3
"""Generate Group page from CV source sections.

Rules:
- Graduate students: Graduate Committees rows with role Chair and degree In progress
- Postdocs: Postdoctoral Scholars Supervised rows with years containing Present
  - if note contains KITP Fellow => role "Postdoc (KITP)", else "Postdoc"
- Undergrads: Undergraduate Students Supervised rows with years containing Present
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
        if not line:
            continue
        if line.startswith("%"):
            continue
        if not line.endswith("\\\\"):
            continue
        if line.startswith("\\"):
            continue
        body = line[:-2].strip()
        if not body or "&" not in body:
            continue
        cols = [_clean_cell(c) for c in body.split("&")]
        # Skip header-like rows
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


def _load_photo_map(path: Path) -> dict:
    if not path.exists():
        return {"schema_version": 1, "people": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {"schema_version": 1, "people": {}}
    data.setdefault("schema_version", 1)
    people = data.get("people")
    if not isinstance(people, dict):
        data["people"] = {}
    return data


def _sync_photo_map(path: Path, people: list[Person], placeholder_path: str) -> dict[str, str]:
    data = _load_photo_map(path)
    people_map: dict = data["people"]
    changed = False

    for person in people:
        if person.name not in people_map:
            people_map[person.name] = {"image": placeholder_path}
            changed = True
        else:
            entry = people_map[person.name]
            if not isinstance(entry, dict):
                people_map[person.name] = {"image": placeholder_path}
                changed = True
            elif "image" not in entry or not str(entry.get("image") or "").strip():
                entry["image"] = placeholder_path
                changed = True

    if changed or not path.exists():
        ordered = {name: people_map[name] for name in sorted(people_map)}
        out = {"schema_version": 1, "people": ordered}
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out, indent=2, sort_keys=False) + "\n", encoding="utf-8")

    return {
        name: str((info.get("image") if isinstance(info, dict) else "") or placeholder_path)
        for name, info in people_map.items()
    }


def _render_cards(people: list[Person], photo_map: dict[str, str], placeholder_path: str) -> str:
    if not people:
        return "<p>No active members listed right now.</p>\n"
    lines = ['<div class="people-grid">']
    for person in people:
        image_path = photo_map.get(person.name) or placeholder_path
        lines.extend(
            [
                '  <article class="person-card">',
                f'    <img src="{{{{ \'{image_path}\' | relative_url }}}}" alt="{html.escape(person.name)}">',
                f"    <h3>{html.escape(person.name)}</h3>",
                f"    <p>{html.escape(person.role)}</p>",
                "  </article>",
            ]
        )
    lines.append("</div>")
    return "\n".join(lines) + "\n"


def render_page(
    grads: list[Person],
    postdocs: list[Person],
    undergrads: list[Person],
    photo_map: dict[str, str],
    placeholder_path: str,
) -> str:
    front_matter = """---
layout: page
title: Group
permalink: "group.html"
group: basepages
nav_order: 6
hlgroup: group
tagline: Supporting tagline
---
"""

    body = [
        "This page is updated automatically from the private CV source.\n",
        "## Research Group\n",
        f"### Graduate Students ({len(grads)})\n",
        _render_cards(grads, photo_map, placeholder_path),
        f"### Postdoctoral Scholars ({len(postdocs)})\n",
        _render_cards(postdocs, photo_map, placeholder_path),
        f"### Undergraduate Students ({len(undergrads)})\n",
        _render_cards(undergrads, photo_map, placeholder_path),
        "## Collaborators\n",
        "Collaborator list coming soon.\n",
    ]
    return front_matter + "\n".join(body)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cv-source", default="cv/source/myresume_master.tex")
    parser.add_argument("--out", default="05-index_group.md")
    parser.add_argument("--placeholder", default="/assets/images/person-placeholder.svg")
    parser.add_argument("--photo-map", default="data/group_photos.json")
    args = parser.parse_args()

    tex = Path(args.cv_source).read_text(encoding="utf-8")
    grads, postdocs, undergrads = collect_people(tex)
    all_people = grads + postdocs + undergrads
    photo_map = _sync_photo_map(Path(args.photo_map), all_people, args.placeholder)
    out_text = render_page(grads, postdocs, undergrads, photo_map, args.placeholder)
    Path(args.out).write_text(out_text, encoding="utf-8")

    print(f"Wrote {args.out}")
    print(f"Wrote/updated {args.photo_map}")
    print(f"Counts: grads={len(grads)}, postdocs={len(postdocs)}, undergrads={len(undergrads)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
