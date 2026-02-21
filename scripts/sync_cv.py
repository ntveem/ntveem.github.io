#!/usr/bin/env python3
"""Generate private/public CV TeX files from canonical ADS JSON publication data.

Outputs:
  - private/cv/Tejaswi_CV_private.tex
  - cv/generated/Tejaswi_CV_public.tex
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from ads_data import AdsPaper, read_papers_json

PUBLIC_REMOVE_SECTIONS = {
    "Current and Pending Support",
    "Graduate Committees",
    "Undergraduate Students Supervised",
    "Postdoctoral Scholars Supervised",
    "Other Supervision/Mentoring",
    "University Service",
}

SECTION_BLOCK_RE = re.compile(
    r"(?:"
    r"\\noindent\\underline\{\s*"
    r"\\begin\{minipage\}\[c\]\[14pt\]\{\\textwidth\}\s*"
    r"\\bf \\Large\{(?P<title_old>.*?)\}\s*"
    r"\\end\{minipage\}\s*"
    r"\}"
    r"|"
    r"\\cvsection(?:\[[^\]]*\])?\{(?P<title_new>.*?)\}"
    r")",
    re.MULTILINE | re.DOTALL,
)


def tex_escape(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    out = text
    for k, v in replacements.items():
        out = out.replace(k, v)
    return out


def is_tejaswi(name: str) -> bool:
    if "," in name:
        last, first = [x.strip().lower() for x in name.split(",", 1)]
    else:
        bits = name.strip().lower().split()
        if not bits:
            return False
        last = bits[-1]
        first = " ".join(bits[:-1])
    return last == "venumadhav" and first.startswith("tejaswi")


def format_author(name: str) -> str:
    if "," in name:
        last, first = [x.strip() for x in name.split(",", 1)]
    else:
        bits = name.split()
        last, first = bits[-1], " ".join(bits[:-1])
    initials = "".join(f"{b[0]}." for b in re.split(r"[\s\-]+", first) if b)
    core = f"{tex_escape(last)}, {initials}" if initials else tex_escape(last)
    return r"\textbf{" + core + "}" if is_tejaswi(name) else core


def format_author_list(authors: list[str]) -> str:
    if not authors:
        return ""
    formatted = [format_author(a) for a in authors]
    if len(formatted) == 1:
        return formatted[0]
    if len(formatted) == 2:
        return f"{formatted[0]}, {formatted[1]}"
    return f"{', '.join(formatted[:-1])}, {formatted[-1]}"


def split_papers(papers: list[AdsPaper], nth_threshold: int) -> tuple[list[AdsPaper], list[AdsPaper], list[AdsPaper]]:
    nth = [paper for paper in papers if len(paper.authors) > nth_threshold]
    non_nth = [paper for paper in papers if len(paper.authors) <= nth_threshold]
    preprints = [
        paper
        for paper in non_nth
        if paper.doctype == "eprint" or "arxiv e-prints" in paper.pub.lower()
    ]
    preprint_keys = {paper.bibcode for paper in preprints}
    refereed = [paper for paper in non_nth if paper.bibcode not in preprint_keys]
    return refereed, preprints, nth


def compute_h_index(papers: list[AdsPaper]) -> int:
    cites = sorted((max(0, paper.citation_count) for paper in papers), reverse=True)
    h = 0
    for i, c in enumerate(cites, start=1):
        if c >= i:
            h = i
        else:
            break
    return h


def format_citation_line(paper: AdsPaper) -> str:
    if paper.pub and paper.volume and paper.page:
        return f"{tex_escape(paper.pub)}, {tex_escape(paper.volume)}, {tex_escape(paper.page)}"
    if paper.pub:
        return tex_escape(paper.pub)
    if paper.arxiv_id:
        return f"arXiv:{tex_escape(paper.arxiv_id)}"
    return ""


def render_highlights(refereed: list[AdsPaper], total_h_index: int) -> str:
    top = sorted(refereed, key=lambda paper: paper.citation_count, reverse=True)[:5]
    lines = [
        r"\begin{cvlist}",
        r"\cvsectionstart",
        rf"\textbf{{Total h-index: {total_h_index}}} \\",
        r"\\",
        r"\textbf{Top five cited published papers (not counting $n^{\rm th}$ author papers):} \\",
        r"\begin{enumerate}[leftmargin=*,itemsep=0.35em,topsep=0.35em]",
    ]
    for paper in top:
        lines.append(
            rf"\item {format_author_list(paper.authors)}, \ ({paper.year}), {format_citation_line(paper)} \\",
        )
        lines.append(rf"Title: {tex_escape(paper.title)} \\")
        lines.append(rf"Citation count: {paper.citation_count} \\")
    lines.extend([r"\end{enumerate}", r"\end{cvlist}", r"\cvsectionend"])
    return "\n".join(lines) + "\n"


def render_refereed(refereed: list[AdsPaper]) -> str:
    lines = [
        r"\begin{cvlist}",
        r"\cvsectionstart",
        r"\begin{enumerate}[leftmargin=*,itemsep=0.32em,topsep=0.3em]",
    ]
    for paper in refereed:
        lines.append(rf"\item {format_author_list(paper.authors)}, \ ({paper.year}), {format_citation_line(paper)} \\")
        lines.append(rf"Title: {tex_escape(paper.title)}")
    lines.extend([r"\end{enumerate}", r"\end{cvlist}", r"\cvsectionend"])
    return "\n".join(lines) + "\n"


def render_preprints(preprints: list[AdsPaper]) -> str:
    lines = [
        r"\begin{cvlist}",
        r"\cvsectionstart",
        r"\begin{enumerate}[leftmargin=*,itemsep=0.32em,topsep=0.3em]",
    ]
    for paper in preprints:
        arxiv_part = f"arXiv:{tex_escape(paper.arxiv_id)}" if paper.arxiv_id else tex_escape(paper.bibcode)
        lines.append(rf"\item {format_author_list(paper.authors)}, \ ({paper.year}), {arxiv_part} \\")
        lines.append(rf"Title: {tex_escape(paper.title)}")
    lines.extend([r"\end{enumerate}", r"\end{cvlist}", r"\cvsectionend"])
    return "\n".join(lines) + "\n"


def render_nth(nth: list[AdsPaper]) -> str:
    lines = [
        r"\begin{cvlist}",
        r"\cvsectionstart",
        r"\begin{enumerate}[leftmargin=*,itemsep=0.32em,topsep=0.3em]",
    ]
    for paper in nth:
        first = format_author(paper.authors[0]) if paper.authors else tex_escape("Unknown")
        lines.append(rf"\item {first}, et. al., ({paper.year}), {format_citation_line(paper)} \\")
        lines.append(rf"Title: {tex_escape(paper.title)}")
    lines.extend([r"\end{enumerate}", r"\end{cvlist}", r"\cvsectionend"])
    return "\n".join(lines) + "\n"


def find_sections(tex: str) -> list[tuple[str, int, int]]:
    matches = list(SECTION_BLOCK_RE.finditer(tex))
    out: list[tuple[str, int, int]] = []
    for i, match in enumerate(matches):
        title = (match.group("title_new") or match.group("title_old") or "").strip()
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(tex)
        out.append((title, start, end))
    return out


def replace_section_body(tex: str, section_title: str, new_body: str) -> str:
    sections = find_sections(tex)
    for title, start, end in sections:
        if title == section_title:
            header_match = SECTION_BLOCK_RE.search(tex, start, end)
            if not header_match:
                break
            body_start = header_match.end()
            return tex[:body_start] + "\n\n" + new_body + "\n" + tex[end:]
    raise ValueError(f"Section '{section_title}' not found in TeX template.")


def remove_sections(tex: str, remove_titles: set[str]) -> str:
    sections = find_sections(tex)
    kept_chunks: list[str] = []
    cursor = 0
    for title, start, end in sections:
        if title in remove_titles:
            kept_chunks.append(tex[cursor:start])
            cursor = end
    kept_chunks.append(tex[cursor:])
    return "".join(kept_chunks)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ads-json", default="data/ads_publications.json")
    parser.add_argument("--template", default="cv/source/myresume_master.tex")
    parser.add_argument("--out-private", default="private/cv/Tejaswi_CV_private.tex")
    parser.add_argument("--out-public", default="cv/generated/Tejaswi_CV_public.tex")
    parser.add_argument("--nth-threshold", type=int, default=12)
    args = parser.parse_args()

    ads_json_path = Path(args.ads_json)
    if not ads_json_path.exists():
        raise SystemExit(f"Missing ADS data file: {ads_json_path}. Run python scripts/sync_ads_data.py first.")

    template = Path(args.template).read_text(encoding="utf-8")
    papers = read_papers_json(ads_json_path)
    refereed, preprints, nth = split_papers(papers, args.nth_threshold)
    total_h_index = compute_h_index(papers)

    private_tex = template
    private_tex = replace_section_body(private_tex, "Publication Highlights", render_highlights(refereed, total_h_index))
    private_tex = replace_section_body(private_tex, "Refereed Publications", render_refereed(refereed))
    private_tex = replace_section_body(private_tex, "Preprints on the Arxiv", render_preprints(preprints))
    private_tex = replace_section_body(private_tex, "N-th Author Papers", render_nth(nth))

    public_tex = remove_sections(private_tex, PUBLIC_REMOVE_SECTIONS)

    write_text(Path(args.out_private), private_tex)
    write_text(Path(args.out_public), public_tex)

    print(f"Wrote {args.out_private}")
    print(f"Wrote {args.out_public}")
    print(f"Counts: refereed={len(refereed)}, preprints={len(preprints)}, nth_author={len(nth)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
