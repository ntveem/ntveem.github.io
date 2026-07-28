#!/usr/bin/env python3
"""Generate a compact reusable CV from ADS-backed publication data.

Outputs:
  - private/cv/Tejaswi_CV_compact.tex
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from ads_data import AdsPaper, read_papers_json
from sync_cv import compute_h_index, split_papers, tex_escape

DEFAULT_ADS_JSON = "data/ads_publications.json"
DEFAULT_OUT = "private/cv/Tejaswi_CV_compact.tex"
DEFAULT_SELECTED_LIMIT = 20

RECENT_SELECTED_BIBCODES = [
    "2026PhRvL.136g1401H",
    "2026PhRvD.113b3003C",
    "2025PhRvD.112j4025M",
    "2025PhRvD.112d4070I",
]


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
    initials = "".join(f"{bit[0]}." for bit in re.split(r"[\s\-]+", first) if bit)
    core = f"{tex_escape(last)}, {initials}" if initials else tex_escape(last)
    return rf"\textbf{{{core}}}" if is_tejaswi(name) else core


def format_authors(authors: list[str], max_authors: int = 8) -> str:
    if not authors:
        return "Unknown"
    if len(authors) > max_authors:
        shown = ", ".join(format_author(author) for author in authors[: max_authors - 1])
        return f"{shown}, et al."
    return ", ".join(format_author(author) for author in authors)


def venue(paper: AdsPaper) -> str:
    if paper.pub and paper.volume and paper.page:
        return f"{tex_escape(paper.pub)}, {tex_escape(paper.volume)}, {tex_escape(paper.page)}"
    if paper.pub and "arxiv e-prints" not in paper.pub.lower():
        return tex_escape(paper.pub)
    if paper.arxiv_id:
        return f"arXiv:{tex_escape(paper.arxiv_id)}"
    return tex_escape(paper.bibcode)


def selected_papers(refereed: list[AdsPaper], limit: int) -> list[AdsPaper]:
    by_bibcode = {paper.bibcode: paper for paper in refereed}
    selected: list[AdsPaper] = []
    for bibcode in RECENT_SELECTED_BIBCODES:
        paper = by_bibcode.get(bibcode)
        if paper:
            selected.append(paper)

    for paper in sorted(refereed, key=lambda p: (p.citation_count, p.pubdate), reverse=True):
        if paper not in selected:
            selected.append(paper)
        if len(selected) >= limit:
            break
    return selected[:limit]


def render_paper_item(paper: AdsPaper) -> str:
    return (
        rf"\item {format_authors(paper.authors)} ({paper.year}). "
        rf"\emph{{{tex_escape(paper.title)}}}. {venue(paper)}."
    )


def render_compact_cv(papers: list[AdsPaper], selected_limit: int) -> str:
    refereed, preprints, nth = split_papers(papers, nth_threshold=12)
    h_index = compute_h_index(papers)
    selected = selected_papers(refereed, selected_limit)

    lines = [
        r"\documentclass[11pt]{article}",
        r"\usepackage[letterpaper,margin=0.72in]{geometry}",
        r"\usepackage[T1]{fontenc}",
        r"\usepackage{lmodern}",
        r"\usepackage{microtype}",
        r"\usepackage{enumitem}",
        r"\usepackage[hidelinks]{hyperref}",
        r"\pagestyle{empty}",
        r"\setlength{\parindent}{0pt}",
        r"\setlength{\parskip}{2pt}",
        r"\setlist[itemize]{leftmargin=1.25em,itemsep=1pt,topsep=2pt,parsep=0pt}",
        r"\setlist[enumerate]{leftmargin=1.45em,itemsep=2pt,topsep=2pt,parsep=0pt}",
        r"\newcommand{\cvsection}[1]{\vspace{5pt}\noindent{\large\bfseries #1}\par\vspace{1pt}\hrule\vspace{3pt}}",
        r"\newcommand{\entry}[3]{\textbf{#1}\hfill #2\\#3\par}",
        r"\begin{document}",
        r"{\LARGE \textbf{Tejaswi Venumadhav Nerella}}\hfill \textbf{Compact Curriculum Vitae}\\",
        r"Associate Professor, Department of Physics, University of California, Santa Barbara\\",
        r"Broida Hall, Santa Barbara, CA 93106-9530 \hfill \href{mailto:teja@ucsb.edu}{teja@ucsb.edu} \quad +1 (626) 826-3571",
        "",
        r"\cvsection{Appointments and Education}",
        r"\entry{University of California, Santa Barbara}{2020--present}{Associate Professor, Department of Physics}",
        r"\entry{International Center for Theoretical Sciences, Bangalore}{2020--present}{Visiting Professor}",
        r"\entry{Institute for Advanced Study, Princeton}{2015--2020}{Member; Schmidt Fellow and John Bahcall Fellow}",
        r"\entry{California Institute of Technology}{2010--2015}{Ph.D. in Physics; advisor: Christopher M. Hirata}",
        r"\entry{Indian Institute of Technology, Kanpur}{2005--2010}{Integrated M.Sc. in Physics}",
        "",
        r"\cvsection{Research Profile}",
        r"\begin{itemize}",
        r"\item Theoretical astrophysics and gravitational-wave data analysis, with emphasis on compact-binary searches, parameter estimation, waveform modeling, strong lensing, neutron-star physics, and early-universe cosmology.",
        r"\item Developer and user of large-scale computational methods for gravitational-wave inference and searches in non-Gaussian, non-stationary detector data.",
        rf"\item Publications: {len(refereed)} refereed papers, {len(preprints)} preprints, {len(nth)} large-collaboration papers; total h-index {h_index} from ADS-backed publication data.",
        r"\end{itemize}",
        "",
        r"\cvsection{Computational Methods and Codes}",
        r"\begin{itemize}",
        r"\item Co-developer of a full gravitational-wave compact-binary search code for LIGO/Virgo data, including matched filtering, template-bank methods, ranking statistics, background estimation, and follow-up of candidates in non-Gaussian detector noise.",
        r"\item Developer of \emph{cogwheel}, a gravitational-wave parameter-estimation code for compact-binary inference, designed for efficient likelihood evaluation, sampling, and post-processing of detector data.",
        r"\item Developer of additional open research codes for cosmological thermal history, sterile-neutrino dark matter, early-universe recombination physics, and related gravitational-wave/cosmology calculations.",
        r"\item Experience designing large ensembles of independent analyses, validating scientific workflows across heterogeneous compute resources, and turning production-scale runs into reproducible publications and public data products.",
        r"\end{itemize}",
        "",
        r"\cvsection{Selected Funding, Honors, and Awards}",
        r"\begin{itemize}",
        r"\item NSF, \emph{WoU-MMA: Targeted Search for Binary Mergers with Multiple Harmonics in Gravitational Wave Data}, PI, 2023--2026.",
        r"\item NSF, \emph{WoU-MMA: Expanding the Horizons of Gravitational Wave Searches and Parameter Estimation}, PI, 2020--2024.",
        r"\item Alfred P. Sloan Research Fellowship, 2023; Hellman Family Faculty Fellowship, 2023.",
        r"\item John Bahcall Fellowship, Institute for Advanced Study, 2019; Schmidt Fellowship, Institute for Advanced Study, 2015--2018.",
        r"\item International Fulbright Science and Technology Award, 2010; President's Gold Medal, IIT Kanpur, 2010.",
        r"\end{itemize}",
        "",
        r"\cvsection{Mentoring, Leadership, and Service}",
        r"\begin{itemize}",
        r"\item Research mentor to graduate students, postdoctoral scholars, undergraduate researchers, and KITP fellows in gravitational-wave astrophysics, compact-object inference, waveform modeling, and cosmology; current group projects include search pipelines, higher harmonics, eccentricity, neutron-star tides, and fast inference.",
        r"\item Organizer: Prospects in Theoretical Physics 2025 program on \emph{Gravitational Waves from Theory to Observation}; KITP 2025 program \emph{Stellar-Mass Black Holes at the Nexus of Optical, X-ray, and Gravitational Wave Surveys}; KITP 2025 conference \emph{The Lifecycle of Stellar Black Holes}.",
        r"\item Referee for Astrophysical Journal, Astrophysical Journal Letters, Monthly Notices of the Royal Astronomical Society, Astroparticle Physics, and Physical Review D; panel reviewer for ERC, BSF, and NSF.",
        r"\end{itemize}",
        "",
        r"\cvsection{Selected Publications}",
        r"\begin{enumerate}",
    ]
    lines.extend(render_paper_item(paper) for paper in selected)
    lines.extend(
        [
            r"\end{enumerate}",
            "",
            r"\cvsection{Selected Recent Preprints}",
            r"\begin{enumerate}",
        ]
    )
    lines.extend(render_paper_item(paper) for paper in preprints[:4])
    lines.extend(
        [
            r"\end{enumerate}",
            r"\vfill",
            r"\footnotesize Full publication list: \url{https://ui.adsabs.harvard.edu/search/q=author%3A%22Venumadhav%2C%20Tejaswi%22&sort=date%20desc%2C%20bibcode%20desc&p_=0}",
            r"\end{document}",
            "",
        ]
    )
    return "\n".join(lines)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ads-json", default=DEFAULT_ADS_JSON)
    parser.add_argument("--out", default=DEFAULT_OUT)
    parser.add_argument("--selected-limit", type=int, default=DEFAULT_SELECTED_LIMIT)
    args = parser.parse_args()

    ads_json_path = Path(args.ads_json)
    if not ads_json_path.exists():
        raise SystemExit(f"Missing ADS data file: {ads_json_path}. Run python scripts/sync_ads_data.py first.")

    tex = render_compact_cv(read_papers_json(ads_json_path), args.selected_limit)
    write_text(Path(args.out), tex)
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
