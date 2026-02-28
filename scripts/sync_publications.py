#!/usr/bin/env python3
"""Sync publications from canonical ADS JSON into 02-index_publications.md.

Usage:
  python scripts/sync_publications.py --preview
  python scripts/sync_publications.py --write
"""

from __future__ import annotations

import argparse
import html
import json
import re
from pathlib import Path

from ads_data import AdsPaper, read_papers_json
from topic_styles import topic_style_attr

DEFAULT_PAGE = "02-index_publications.md"
DEFAULT_ADS_JSON = "data/ads_publications.json"
DEFAULT_TOPICS_JSON = "data/topics.json"

def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "topic"


def load_topics(path: Path) -> list[str]:
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    topics = payload.get("topics") or []
    out: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        t = str(topic).strip()
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(t)
    return out


def _format_author(name: str) -> str:
    if "," in name:
        last, first = [part.strip() for part in name.split(",", 1)]
    else:
        chunks = name.split()
        last = chunks[-1]
        first = " ".join(chunks[:-1])
    initials = "".join(f"{x[0]}." for x in re.split(r"[\s\-]+", first) if x)
    out = f"{last}, {initials}" if initials else last
    if last.lower() == "venumadhav" and first.lower().startswith("tejaswi"):
        return f"<strong>{html.escape(out)}</strong>"
    return html.escape(out)


def _is_tejaswi_name(name: str) -> bool:
    if "," in name:
        last, first = [part.strip().lower() for part in name.split(",", 1)]
    else:
        chunks = name.lower().split()
        if not chunks:
            return False
        last = chunks[-1]
        first = " ".join(chunks[:-1])
    return last == "venumadhav" and first.startswith("tejaswi")


def _tejaswi_author_label(authors: list[str]) -> str:
    for author in authors:
        if _is_tejaswi_name(author):
            return _format_author(author)
    return "<strong>Venumadhav, T.</strong>"


def _format_author_list(authors: list[str]) -> str:
    if not authors:
        return ""
    formatted = [_format_author(author) for author in authors]
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]} & {formatted[1]}"
    return f"{', '.join(formatted[:-1])}, & {formatted[-1]}"


def _paper_topics(paper: AdsPaper, allowed_topics: list[str]) -> list[str]:
    allowed = set(allowed_topics)
    topics = [t for t in (paper.topics or []) if t in allowed]
    if topics:
        return topics
    return []


def _render_entry(paper: AdsPaper, idx: int, entry_id: str, topics: list[str], nth_mode: bool) -> list[str]:
    topic_attr = "|".join(topics)
    lines = [f'<article id="{entry_id}" class="pub-entry" data-topics="{topic_attr}">']

    if nth_mode:
        first_author = _format_author(paper.authors[0]) if paper.authors else "Unknown"
        teja_label = _tejaswi_author_label(paper.authors)
        lines.append(
            f'<p class="pub-citation">{idx}. {first_author} et al. ({paper.year}; incl. {teja_label})</p>',
        )
    else:
        lines.append(f'<p class="pub-citation">{idx}. {_format_author_list(paper.authors)} ({paper.year})</p>')

    lines.append(f'<p class="pub-title"><em>{html.escape(paper.title)}</em></p>')
    links = [f'<a href="{paper.ads_url}">ADS</a>']
    if paper.arxiv_url:
        links.append(f'<a href="{paper.arxiv_url}">arxiv</a>')
    if paper.inspire_url:
        links.append(f'<a href="{paper.inspire_url}">INSPIRE</a>')
    lines.append(f'<p class="pub-links">{" ".join(links)}</p>')

    if topics:
        topic_badges = " ".join(
            f'<span class="pub-topic-chip"{topic_style_attr(topic)}>{html.escape(topic)}</span>' for topic in topics
        )
        lines.append(f'<div class="pub-entry-topics">{topic_badges}</div>')

    lines.append("</article>")
    lines.append("")
    return lines


def render_entries(papers: list[AdsPaper], allowed_topics: list[str]) -> tuple[str, list[dict], dict[str, list[tuple[str, str]]]]:
    main_papers: list[AdsPaper] = []
    nth_author_papers: list[AdsPaper] = []
    for paper in papers:
        if len(paper.authors) > 12:
            nth_author_papers.append(paper)
        else:
            main_papers.append(paper)

    lines: list[str] = []
    topic_counts: dict[str, int] = {topic: 0 for topic in allowed_topics}
    topic_index: dict[str, list[tuple[str, str]]] = {topic: [] for topic in allowed_topics}

    for idx, paper in enumerate(main_papers, start=1):
        topics = _paper_topics(paper, allowed_topics)
        entry_id = f"paper-{idx}"
        for topic in topics:
            topic_counts[topic] += 1
            topic_index[topic].append((entry_id, paper.title))
        lines.extend(_render_entry(paper, idx, entry_id, topics, nth_mode=False))

    if nth_author_papers:
        lines.append("<br>")
        lines.append("n-th author papers:")
        lines.append("")
        for idx, paper in enumerate(nth_author_papers, start=1):
            topics = _paper_topics(paper, allowed_topics)
            entry_id = f"paper-nth-{idx}"
            for topic in topics:
                topic_counts[topic] += 1
                topic_index[topic].append((entry_id, paper.title))
            lines.extend(_render_entry(paper, idx, entry_id, topics, nth_mode=True))

    chips = [{"topic": t, "count": topic_counts.get(t, 0), "slug": _slugify(t)} for t in allowed_topics]
    return "\n".join(lines).rstrip() + "\n", chips, topic_index


def render_topic_filter(chips: list[dict]) -> str:
    lines = [
        '<section class="pub-topic-filter" aria-label="Filter publications by topic">',
        "<p>Select one or more topics:</p>",
        '<div class="pub-topic-filter-controls">',
    ]
    for chip in chips:
        style_attr = topic_style_attr(chip["topic"])
        lines.append(
            f'<a class="topic-filter" href="#topic-{chip["slug"]}" data-topic="{chip["topic"]}"{style_attr}>{html.escape(chip["topic"])} <span>({chip["count"]})</span></a>'
        )
    lines.append('<button type="button" id="pub-filter-clear" class="topic-filter-clear">Clear</button>')
    lines.append("</div>")
    lines.append('<p id="pub-filter-status" class="pub-filter-status">Showing all papers.</p>')
    lines.append("</section>")
    return "\n".join(lines) + "\n"


def render_topic_fallback(chips: list[dict], topic_index: dict[str, list[tuple[str, str]]]) -> str:
    lines = [
        '<section class="pub-topic-fallback">',
        "<h3>Browse by topic</h3>",
        "<p>If filtering is unavailable, jump to a topic section:</p>",
        "<ul>",
    ]
    for chip in chips:
        lines.append(f'<li><a href="#topic-{chip["slug"]}">{chip["topic"]}</a> ({chip["count"]})</li>')
    lines.extend(["</ul>", "</section>"])

    for chip in chips:
        topic = chip["topic"]
        slug = chip["slug"]
        lines.append(f'<section class="pub-topic-section" id="topic-{slug}">')
        lines.append(f"<h3>{topic}</h3>")
        items = topic_index.get(topic) or []
        if not items:
            lines.append("<p>No papers currently tagged with this topic.</p>")
        else:
            lines.append("<ul>")
            for entry_id, title in items:
                lines.append(f'<li><a href="#{entry_id}">{title}</a></li>')
            lines.append("</ul>")
        lines.append("</section>")

    return "\n".join(lines) + "\n"


def render_filter_script() -> str:
    return (
        "<script>\n"
        "(() => {\n"
        "  const filters = Array.from(document.querySelectorAll('.topic-filter[data-topic]'));\n"
        "  const entries = Array.from(document.querySelectorAll('.pub-entry'));\n"
        "  const status = document.getElementById('pub-filter-status');\n"
        "  const clear = document.getElementById('pub-filter-clear');\n"
        "  if (!filters.length || !entries.length) return;\n"
        "  const selected = new Set();\n"
        "  const update = () => {\n"
        "    let visible = 0;\n"
        "    for (const entry of entries) {\n"
        "      const topics = (entry.dataset.topics || '').split('|').filter(Boolean);\n"
        "      const show = Array.from(selected).every(t => topics.includes(t));\n"
        "      entry.hidden = !show;\n"
        "      if (show) visible += 1;\n"
        "    }\n"
        "    for (const f of filters) {\n"
        "      f.classList.toggle('is-active', selected.has(f.dataset.topic));\n"
        "      f.setAttribute('aria-pressed', selected.has(f.dataset.topic) ? 'true' : 'false');\n"
        "    }\n"
        "    if (!status) return;\n"
        "    if (!selected.size) {\n"
        "      status.textContent = `Showing all ${entries.length} papers.`;\n"
        "      return;\n"
        "    }\n"
        "    status.textContent = `Showing ${visible} papers for: ${Array.from(selected).join(', ')}.`;\n"
        "  };\n"
        "  for (const f of filters) {\n"
        "    f.addEventListener('click', (ev) => {\n"
        "      ev.preventDefault();\n"
        "      const topic = f.dataset.topic;\n"
        "      if (!topic) return;\n"
        "      if (selected.has(topic)) selected.delete(topic);\n"
        "      else selected.add(topic);\n"
        "      update();\n"
        "    });\n"
        "  }\n"
        "  if (clear) {\n"
        "    clear.addEventListener('click', () => {\n"
        "      selected.clear();\n"
        "      update();\n"
        "    });\n"
        "  }\n"
        "  update();\n"
        "})();\n"
        "</script>\n"
    )


def render_full_page(front_matter: str, entries: str, topic_filter: str, topic_fallback: str, filter_script: str) -> str:
    header = (
        "List of my publications on online databases:\n\n"
        "* [ADS](https://ui.adsabs.harvard.edu/search/q=author%3A%22Venumadhav%2C%20Tejaswi%22&sort=date%20desc%2C%20bibcode%20desc&p_=0)\n"
        "* [arxiv](https://arxiv.org/a/venumadhav_t_1.html)\n"
        "* [INSPIRE](https://inspirehep.net/authors/1321339)\n\n"
        "<!-- AUTOGENERATED PUBLICATIONS: START -->\n"
    )
    footer = "<!-- AUTOGENERATED PUBLICATIONS: END -->\n"
    body = (
        "Individual links to articles and manuscripts, in reverse chronological order:\n\n"
        f"{topic_filter}\n"
        f"{entries}\n"
        f"{topic_fallback}\n"
        f"{filter_script}"
    )
    return f"{front_matter}\n{header}{body}{footer}"


def parse_front_matter(text: str) -> tuple[str, str]:
    match = re.match(r"(?s)\A(---\n.*?\n---)\n?(.*)\Z", text)
    if not match:
        raise ValueError("Expected YAML front matter in publications page.")
    return match.group(1), match.group(2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default=DEFAULT_PAGE)
    parser.add_argument("--ads-json", default=DEFAULT_ADS_JSON)
    parser.add_argument("--topics-file", default=DEFAULT_TOPICS_JSON)
    parser.add_argument("--preview", action="store_true", help="Print generated list and exit.")
    parser.add_argument("--write", action="store_true", help="Write updates to publications page.")
    args = parser.parse_args()

    ads_json_path = Path(args.ads_json)
    if not ads_json_path.exists():
        raise SystemExit(f"Missing ADS data file: {ads_json_path}. Run python scripts/sync_ads_data.py first.")

    papers = read_papers_json(ads_json_path)
    allowed_topics = load_topics(Path(args.topics_file))
    entries, chips, topic_index = render_entries(papers, allowed_topics)
    topic_filter = render_topic_filter(chips)
    topic_fallback = render_topic_fallback(chips, topic_index)
    filter_script = render_filter_script()

    if args.preview or not args.write:
        print(entries)
        if not args.write:
            return 0

    target = Path(args.file)
    original = target.read_text(encoding="utf-8")
    front_matter, _ = parse_front_matter(original)
    updated = render_full_page(front_matter, entries, topic_filter, topic_fallback, filter_script)
    if updated != original:
        target.write_text(updated, encoding="utf-8")
        print(f"Updated {target}")
    else:
        print(f"No changes in {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
