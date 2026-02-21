#!/usr/bin/env python3
"""Shared ADS publication fetch/filter/dedupe utilities."""

from __future__ import annotations

import json
import os
import re
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

ADS_API_URL = "https://api.adsabs.harvard.edu/v1/search/query"
BLOCKED_PUB_PATTERNS = [
    r"aps meeting abstracts",
    r"bulletin of the american physical society",
]
EXCLUDED_BIBCODES = {
    # Known false positive from a same-name ADS match.
    "2012IJCA...38h..22V",
}

ENRICHMENT_FIELDS = {
    "abstract",
    "topics",
    "topic_source",
    "topic_confidence",
    "topics_classified_with",
}


@dataclass
class AdsPaper:
    title: str
    authors: list[str]
    year: int
    bibcode: str
    doctype: str
    pub: str
    pub_raw: str
    pubdate: str
    volume: str
    page: str
    arxiv_id: str | None
    doi: str | None
    inspire_recid: str | None
    citation_count: int
    abstract: str | None = None
    topics: list[str] = field(default_factory=list)
    topic_source: str | None = None
    topic_confidence: float | None = None
    topics_classified_with: str | None = None

    @property
    def ads_url(self) -> str:
        return f"https://ui.adsabs.harvard.edu/abs/{urllib.parse.quote(self.bibcode, safe='')}/abstract"

    @property
    def arxiv_url(self) -> str | None:
        if not self.arxiv_id:
            return None
        return f"https://arxiv.org/abs/{self.arxiv_id}"

    @property
    def inspire_url(self) -> str | None:
        if not self.inspire_recid:
            return None
        return f"https://inspirehep.net/record/{self.inspire_recid}"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


def fetch_ads_docs(token: str, author_name: str, rows: int = 500) -> list[dict]:
    query = (
        f'author:"{author_name}" AND doctype:(article OR eprint) '
        "AND -pub:(\"APS Meeting Abstracts\" OR \"Bulletin of the American Physical Society\")"
    )
    params = {
        "q": query,
        "fl": ",".join(
            [
                "title",
                "author",
                "year",
                "bibcode",
                "identifier",
                "doctype",
                "pub",
                "pub_raw",
                "pubdate",
                "volume",
                "page",
                "citation_count",
            ]
        ),
        "rows": str(rows),
        "sort": "date desc",
    }
    req = urllib.request.Request(
        f"{ADS_API_URL}?{urllib.parse.urlencode(params)}",
        headers={"Authorization": f"Bearer {token}", "User-Agent": "ads-data-sync-script"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return payload.get("response", {}).get("docs", [])


def fetch_abstracts_for_bibcodes(token: str, bibcodes: list[str], chunk_size: int = 20) -> dict[str, str]:
    abstracts: dict[str, str] = {}
    if not bibcodes:
        return abstracts

    for i in range(0, len(bibcodes), chunk_size):
        chunk = [b.strip() for b in bibcodes[i : i + chunk_size] if b and b.strip()]
        if not chunk:
            continue

        terms = " OR ".join(f"bibcode:\"{b}\"" for b in chunk)
        params = {
            "q": f"({terms})",
            "fl": "bibcode,abstract",
            "rows": str(len(chunk)),
        }
        req = urllib.request.Request(
            f"{ADS_API_URL}?{urllib.parse.urlencode(params)}",
            headers={"Authorization": f"Bearer {token}", "User-Agent": "ads-data-sync-script"},
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        docs = payload.get("response", {}).get("docs", [])
        for doc in docs:
            bibcode = (doc.get("bibcode") or "").strip()
            abstract = (doc.get("abstract") or "").strip()
            if bibcode and abstract:
                abstracts[bibcode] = abstract

    return abstracts


def _extract_arxiv_id(identifiers: Iterable[str]) -> str | None:
    for ident in identifiers:
        m = re.search(r"(?i)arxiv:([a-z\-]+/\d{7}|\d{4}\.\d{4,5}(?:v\d+)?)", ident)
        if m:
            return m.group(1)
    return None


def _extract_inspire_recid(identifiers: Iterable[str]) -> str | None:
    for ident in identifiers:
        m = re.search(r"INSPIRE[-:](\d+)", ident, flags=re.IGNORECASE)
        if m:
            return m.group(1)
    return None


def _extract_doi(identifiers: Iterable[str]) -> str | None:
    for ident in identifiers:
        m = re.search(r"(10\.\d{4,9}/\S+)", ident)
        if m:
            return m.group(1).rstrip(".,;)")
    return None


def _fetch_inspire_control_number(arxiv_id: str | None, doi: str | None) -> str | None:
    queries: list[str] = []
    if arxiv_id:
        queries.append(f"arxiv:{arxiv_id}")
    if doi:
        queries.append(f"doi:{doi}")

    for q in queries:
        url = (
            "https://inspirehep.net/api/literature?"
            + urllib.parse.urlencode({"q": q, "fields": "control_number", "size": "1"})
        )
        req = urllib.request.Request(url, headers={"User-Agent": "ads-data-sync-script"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            hits = payload.get("hits", {}).get("hits") or []
            if not hits:
                continue
            cn = hits[0].get("metadata", {}).get("control_number")
            if cn:
                return str(cn)
        except Exception:
            continue

    return None


def _skip_doc(doc: dict) -> bool:
    bibcode = (doc.get("bibcode") or "").strip()
    if bibcode in EXCLUDED_BIBCODES:
        return True

    doctype = (doc.get("doctype") or "").lower()
    if doctype not in {"article", "eprint"}:
        return True

    pub = (doc.get("pub") or "").lower()
    if any(re.search(pattern, pub) for pattern in BLOCKED_PUB_PATTERNS):
        return True

    title = ((doc.get("title") or [""])[0] or "").lower()
    if "meeting abstract" in title:
        return True

    return False


def _paper_from_doc(doc: dict) -> AdsPaper | None:
    if _skip_doc(doc):
        return None

    title = ((doc.get("title") or [""])[0] or "").strip()
    if not title:
        return None

    identifiers = doc.get("identifier") or []
    page = doc.get("page")
    if isinstance(page, list):
        page = page[0] if page else ""

    return AdsPaper(
        title=title,
        authors=doc.get("author") or [],
        year=int(str(doc.get("year") or "0") or 0),
        bibcode=(doc.get("bibcode") or "").strip(),
        doctype=(doc.get("doctype") or "").lower(),
        pub=(doc.get("pub") or "").strip(),
        pub_raw=(doc.get("pub_raw") or "").strip(),
        pubdate=(doc.get("pubdate") or "").strip(),
        volume=str(doc.get("volume") or "").strip(),
        page=str(page or "").strip(),
        arxiv_id=_extract_arxiv_id(identifiers),
        doi=_extract_doi(identifiers),
        inspire_recid=_extract_inspire_recid(identifiers),
        citation_count=int(doc.get("citation_count") or 0),
        abstract=None,
        topics=[],
        topic_source=None,
        topic_confidence=None,
        topics_classified_with=None,
    )


def _dedupe_key(paper: AdsPaper) -> str:
    if paper.arxiv_id:
        return f"arxiv:{paper.arxiv_id.lower()}"
    norm_title = re.sub(r"\W+", "", paper.title.lower())
    return f"title:{norm_title}"


def _priority(paper: AdsPaper) -> tuple[int, int, int, int, str]:
    return (
        1 if paper.doctype == "article" else 0,
        1 if paper.pub else 0,
        1 if paper.inspire_recid else 0,
        max(0, paper.citation_count),
        paper.pubdate,
    )


def clean_and_dedupe(docs: list[dict]) -> list[AdsPaper]:
    chosen: dict[str, AdsPaper] = {}
    for doc in docs:
        paper = _paper_from_doc(doc)
        if not paper:
            continue
        key = _dedupe_key(paper)
        existing = chosen.get(key)
        if existing is None or _priority(paper) > _priority(existing):
            chosen[key] = paper

    papers = list(chosen.values())
    papers.sort(key=lambda paper: (paper.pubdate, paper.year), reverse=True)
    return papers


def enrich_with_inspire(papers: list[AdsPaper]) -> None:
    inspire_cache: dict[str, str | None] = {}
    for paper in papers:
        if paper.inspire_recid:
            continue
        cache_key = f"{paper.arxiv_id or ''}|{paper.doi or ''}"
        if cache_key not in inspire_cache:
            inspire_cache[cache_key] = _fetch_inspire_control_number(paper.arxiv_id, paper.doi)
        paper.inspire_recid = inspire_cache[cache_key]


def load_enrichment_map(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    papers_data = payload.get("papers") or []
    enrichment_by_bibcode: dict[str, dict] = {}
    for raw in papers_data:
        bibcode = (raw.get("bibcode") or "").strip()
        if not bibcode:
            continue
        enriched: dict = {}
        for key in ENRICHMENT_FIELDS:
            if key in raw:
                enriched[key] = raw.get(key)
        if enriched:
            enrichment_by_bibcode[bibcode] = enriched
    return enrichment_by_bibcode


def _with_default_enrichment(raw: dict) -> dict:
    if "abstract" not in raw:
        raw["abstract"] = None
    if "topics" not in raw:
        raw["topics"] = []
    if "topic_source" not in raw:
        raw["topic_source"] = None
    if "topic_confidence" not in raw:
        raw["topic_confidence"] = None
    if "topics_classified_with" not in raw:
        raw["topics_classified_with"] = None
    return raw


def write_papers_json(path: Path, papers: list[AdsPaper], enrichment_by_bibcode: dict[str, dict] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for paper in papers:
        row = asdict(paper)
        if enrichment_by_bibcode and paper.bibcode in enrichment_by_bibcode:
            row.update(enrichment_by_bibcode[paper.bibcode])
        rows.append(_with_default_enrichment(row))

    payload = {
        "schema_version": 2,
        "papers": rows,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_papers_json(path: Path) -> list[AdsPaper]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    papers_data = payload.get("papers") or []
    papers: list[AdsPaper] = []
    for raw in papers_data:
        papers.append(
            AdsPaper(
                title=raw.get("title") or "",
                authors=list(raw.get("authors") or []),
                year=int(raw.get("year") or 0),
                bibcode=raw.get("bibcode") or "",
                doctype=(raw.get("doctype") or "").lower(),
                pub=raw.get("pub") or "",
                pub_raw=raw.get("pub_raw") or "",
                pubdate=raw.get("pubdate") or "",
                volume=str(raw.get("volume") or ""),
                page=str(raw.get("page") or ""),
                arxiv_id=raw.get("arxiv_id"),
                doi=raw.get("doi"),
                inspire_recid=raw.get("inspire_recid"),
                citation_count=int(raw.get("citation_count") or 0),
                abstract=raw.get("abstract"),
                topics=list(raw.get("topics") or []),
                topic_source=raw.get("topic_source"),
                topic_confidence=(
                    float(raw.get("topic_confidence"))
                    if raw.get("topic_confidence") is not None
                    else None
                ),
                topics_classified_with=raw.get("topics_classified_with"),
            )
        )
    papers.sort(key=lambda paper: (paper.pubdate, paper.year), reverse=True)
    return papers
