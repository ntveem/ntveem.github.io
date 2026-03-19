#!/usr/bin/env python3
"""Generate an applications-style publication list TeX file from ADS JSON.

Outputs:
  - private/publist/Tejaswi_publist.tex
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from ads_data import AdsPaper, read_papers_json

DEFAULT_ADS_JSON = "data/ads_publications.json"
DEFAULT_OUT = "private/publist/Tejaswi_publist.tex"
DEFAULT_NAME = "Tejaswi Venumadhav Nerella"
DEFAULT_HIGHLIGHTS = 5

JOURNAL_MACROS = {
    "Annual Review of Nuclear and Particle Science": r"\arnps",
    "Classical and Quantum Gravity": r"\cqg",
    "Monthly Notices of the Royal Astronomical Society": r"\mnras",
    "Physical Review B": r"\prb",
    "Physical Review D": r"\prd",
    "Physical Review Letters": r"\prl",
    "Publications of the Astronomical Society of Australia": r"\pasa",
    "The Astrophysical Journal": r"\apj",
    "The Astrophysical Journal Letters": r"\apjl",
    "The Astrophysical Journal Supplement Series": r"\apjs",
}


def tex_escape(text: str) -> str:
    replacements = {
        "\u00a0": " ",
        "\u2013": "--",
        "\u2014": "---",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": "``",
        "\u201d": "''",
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
    for src, dst in replacements.items():
        out = out.replace(src, dst)
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
        if not bits:
            return tex_escape(name)
        last = bits[-1]
        first = " ".join(bits[:-1])
    initials = "".join(f"{bit[0]}." for bit in re.split(r"[\s\-]+", first) if bit)
    core = f"{tex_escape(last)}, {initials}" if initials else tex_escape(last)
    return rf"\textbf{{{core}}}" if is_tejaswi(name) else core


def format_author_list(authors: list[str]) -> str:
    if not authors:
        return ""
    return ", ".join(format_author(author) for author in authors)


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


def sort_highlights(papers: list[AdsPaper]) -> list[AdsPaper]:
    return sorted(
        papers,
        key=lambda paper: (paper.citation_count, paper.pubdate, paper.year, paper.title.lower()),
        reverse=True,
    )


def format_citation_line(paper: AdsPaper) -> str:
    if paper.arxiv_id and (paper.doctype == "eprint" or "arxiv e-prints" in paper.pub.lower()):
        return f"arXiv:{tex_escape(paper.arxiv_id)}"

    venue = JOURNAL_MACROS.get(paper.pub, tex_escape(paper.pub)) if paper.pub else ""
    parts = [venue] if venue else []
    if paper.volume:
        parts.append(tex_escape(paper.volume))
    if paper.page:
        parts.append(tex_escape(paper.page))
    if parts:
        return ", ".join(parts)
    if paper.arxiv_id:
        return f"arXiv:{tex_escape(paper.arxiv_id)}"
    return tex_escape(paper.bibcode)


def render_item(paper: AdsPaper, nth_mode: bool = False) -> list[str]:
    if nth_mode:
        first_author = format_author(paper.authors[0]) if paper.authors else "Unknown"
        citation = rf"\item {first_author}, et. al., ({paper.year}), {format_citation_line(paper)} \\"
    else:
        citation = rf"\item {format_author_list(paper.authors)}, ({paper.year}), {format_citation_line(paper)} \\"
    return [
        citation,
        rf"\textbf{{Title:}} {tex_escape(paper.title)}",
    ]


def render_section(title: str, papers: list[AdsPaper], nth_mode: bool = False, heading_suffix: str = "") -> str:
    header = rf"\noindent\underline{{\makebox[\textwidth][l]{{\bf \Large{{{title}{heading_suffix}}}}}}}"
    lines = [header, r"\\", ""]
    lines.append(r"{\addtolength{\leftskip}{10mm}")
    lines.append(r"\begin{enumerate}[leftmargin=*,itemsep=0.45em,topsep=0.35em]")
    if papers:
        for paper in papers:
            lines.extend(render_item(paper, nth_mode=nth_mode))
    else:
        lines.append(r"\item None.")
    lines.extend([r"\end{enumerate}", r"\par}", ""])
    return "\n".join(lines)


def render_document(
    name: str,
    highlights: list[AdsPaper],
    refereed: list[AdsPaper],
    preprints: list[AdsPaper],
    nth: list[AdsPaper],
) -> str:
    sections = [
        render_section("Most Significant Publications", highlights, heading_suffix=rf" \hfill {tex_escape(name)}"),
        render_section("Refereed Publications", refereed),
        render_section("Preprints", preprints),
        render_section(r"$n^{\rm th}$ Author Papers", nth, nth_mode=True),
    ]

    return "\n".join(
        [
            r"\documentclass{article}",
            r"\usepackage[utf8]{inputenc}",
            r"\usepackage[T1]{fontenc}",
            r"\usepackage{lmodern}",
            r"\usepackage{microtype}",
            r"\usepackage{fullpage}",
            r"\usepackage{enumitem}",
            r"\usepackage{url,longtable}",
            r"\setlist[enumerate]{leftmargin=*,itemsep=0.45em,topsep=0.35em}",
            r"\addtolength{\oddsidemargin}{-.2in}",
            r"\newcommand{\apj}{Astrophysical Journal}",
            r"\newcommand{\apjl}{Astrophys. J. Lett.}",
            r"\newcommand{\apjs}{Astrophys. J. Suppl. Ser.}",
            r"\newcommand{\arnps}{Annu. Rev. Nucl. Part. Sci.}",
            r"\newcommand{\cqg}{Classical and Quantum Gravity}",
            r"\newcommand{\mnras}{Mon. Not. R. Astron. Soc.}",
            r"\newcommand{\pasa}{Publ. Astron. Soc. Aust.}",
            r"\newcommand{\prb}{Physical Review B}",
            r"\newcommand{\prd}{Physical Review D}",
            r"\newcommand{\prl}{Physical Review Letters}",
            r"\begin{document}",
            r"\pagestyle{empty}",
            "",
            *sections,
            r"\end{document}",
            "",
        ]
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ads-json", default=DEFAULT_ADS_JSON)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--name", default=DEFAULT_NAME)
    parser.add_argument("--highlights", type=int, default=DEFAULT_HIGHLIGHTS)
    parser.add_argument("--nth-threshold", type=int, default=12)
    args = parser.parse_args()

    ads_json_path = Path(args.ads_json)
    if not ads_json_path.exists():
        raise SystemExit(f"Missing ADS data file: {ads_json_path}. Run python scripts/sync_ads_data.py first.")

    papers = read_papers_json(ads_json_path)
    refereed, preprints, nth = split_papers(papers, args.nth_threshold)
    highlights = sort_highlights(refereed)[: max(0, args.highlights)]
    tex = render_document(args.name, highlights, refereed, preprints, nth)
    write_text(Path(args.out), tex)

    print(f"Wrote {args.out}")
    print(
        "Counts: "
        f"highlights={len(highlights)}, refereed={len(refereed)}, "
        f"preprints={len(preprints)}, nth_author={len(nth)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
