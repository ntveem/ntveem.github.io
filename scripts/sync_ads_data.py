#!/usr/bin/env python3
"""Fetch ADS publications once and persist canonical JSON for downstream generators."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.request
from pathlib import Path

from ads_data import (
    clean_and_dedupe,
    enrich_with_inspire,
    fetch_abstracts_for_bibcodes,
    fetch_ads_docs,
    load_dotenv,
    load_enrichment_map,
    write_papers_json,
)


def load_topics(path: Path) -> list[str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    topics = payload.get("topics") or []
    cleaned: list[str] = []
    seen: set[str] = set()
    for topic in topics:
        t = str(topic).strip()
        if not t:
            continue
        key = t.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(t)
    return cleaned


def topics_version(topics: list[str]) -> str:
    normalized = json.dumps(topics, ensure_ascii=True, separators=(",", ":"))
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return digest[:16]


def load_overrides(path: Path) -> dict[str, list[str]]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("overrides") or {}
    out: dict[str, list[str]] = {}
    for bibcode, topics in raw.items():
        b = str(bibcode).strip()
        if not b:
            continue
        out[b] = [str(t).strip() for t in (topics or []) if str(t).strip()]
    return out


def _extract_json_object(text: str) -> dict:
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass
    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return {}
    try:
        obj = json.loads(m.group(0))
        if isinstance(obj, dict):
            return obj
    except Exception:
        return {}
    return {}


def _extract_response_text(payload: dict) -> str:
    text = payload.get("output_text")
    if isinstance(text, str) and text.strip():
        return text

    out_chunks: list[str] = []
    for item in payload.get("output") or []:
        for content in item.get("content") or []:
            ctype = content.get("type")
            if ctype in {"output_text", "text"}:
                value = content.get("text")
                if isinstance(value, str) and value.strip():
                    out_chunks.append(value)
            elif ctype == "json_schema":
                value = content.get("json")
                if isinstance(value, dict):
                    out_chunks.append(json.dumps(value))
            elif isinstance(content.get("text"), str):
                out_chunks.append(content["text"])
    return "\n".join(out_chunks).strip()


def classify_topics_with_openai(
    *,
    api_key: str,
    model: str,
    title: str,
    abstract: str,
    allowed_topics: list[str],
) -> tuple[list[str], float | None]:
    prompt = (
        "Classify the paper into zero or more topics from the allowed list.\n"
        "Return strict JSON only with keys: topics (array of strings), confidence (0..1).\n"
        "Do not invent topics.\n\n"
        f"Allowed topics: {json.dumps(allowed_topics)}\n\n"
        f"Title: {title}\n\n"
        f"Abstract: {abstract}\n"
    )
    body = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": "You are a precise classifier. Output strict JSON only.",
                    }
                ],
            },
            {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
        ],
    }
    req = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "ads-data-sync-script",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        payload = json.loads(resp.read().decode("utf-8"))

    text = _extract_response_text(payload)
    obj = _extract_json_object(text)
    allowed_set = set(allowed_topics)
    topics = [t for t in (obj.get("topics") or []) if t in allowed_set]
    confidence = obj.get("confidence")
    try:
        confidence = float(confidence)
    except Exception:
        confidence = None
    if confidence is not None:
        confidence = max(0.0, min(1.0, confidence))
    return topics, confidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--author", default="Tejaswi Venumadhav")
    parser.add_argument("--rows", type=int, default=500)
    parser.add_argument("--token-env", default="ADS_API_TOKEN")
    parser.add_argument("--dotenv", default=".env")
    parser.add_argument("--out", default="data/ads_publications.json")
    parser.add_argument("--skip-abstracts", action="store_true")
    parser.add_argument("--refresh-abstracts", action="store_true")
    parser.add_argument("--topics-file", default="data/topics.json")
    parser.add_argument("--overrides-file", default="data/topic_overrides.json")
    parser.add_argument("--skip-topics", action="store_true")
    parser.add_argument("--refresh-topics", action="store_true")
    parser.add_argument("--openai-key-env", default="OPENAI_API_KEY")
    parser.add_argument("--openai-model", default=os.environ.get("OPENAI_MODEL", "gpt-4.1-mini"))
    args = parser.parse_args()

    load_dotenv(Path(args.dotenv))
    token = os.environ.get(args.token_env, "").strip()
    if not token:
        print(f"Missing {args.token_env} in environment.", file=sys.stderr)
        return 2

    out_path = Path(args.out)
    enrichment_by_bibcode = load_enrichment_map(out_path)
    topics = load_topics(Path(args.topics_file))
    current_topics_version = topics_version(topics)
    overrides = load_overrides(Path(args.overrides_file))

    docs = fetch_ads_docs(token=token, author_name=args.author, rows=args.rows)
    papers = clean_and_dedupe(docs)
    enrich_with_inspire(papers)

    abstracts_fetched = 0
    if not args.skip_abstracts:
        missing_bibcodes: list[str] = []
        for paper in papers:
            current = (enrichment_by_bibcode.get(paper.bibcode, {}) or {}).get("abstract")
            if args.refresh_abstracts or not current:
                missing_bibcodes.append(paper.bibcode)

        abstracts = fetch_abstracts_for_bibcodes(token=token, bibcodes=missing_bibcodes)
        abstracts_fetched = len(abstracts)
        for paper in papers:
            entry = enrichment_by_bibcode.setdefault(paper.bibcode, {})
            current = entry.get("abstract")
            if args.refresh_abstracts or not current:
                entry["abstract"] = abstracts.get(paper.bibcode, current)

    classified = 0
    classify_skipped = 0
    classify_errors = 0
    api_key = os.environ.get(args.openai_key_env, "").strip()
    do_classification = not args.skip_topics
    if do_classification:
        if not topics:
            print("Topics: empty topic list; skipping classification.")
            do_classification = False
        elif not api_key:
            print(f"Topics: {args.openai_key_env} not set; skipping classification.")
            do_classification = False

    if do_classification:
        for paper in papers:
            if paper.bibcode in overrides:
                classify_skipped += 1
                continue
            entry = enrichment_by_bibcode.setdefault(paper.bibcode, {})
            previous_topics = entry.get("topics") or []
            previous_version = entry.get("topics_classified_with")
            needs_classification = args.refresh_topics or (not previous_topics) or (
                previous_version != current_topics_version
            )
            if not needs_classification:
                classify_skipped += 1
                continue

            abstract = (entry.get("abstract") or "").strip()
            if not abstract:
                classify_skipped += 1
                continue

            ok = False
            for _ in range(2):
                try:
                    new_topics, confidence = classify_topics_with_openai(
                        api_key=api_key,
                        model=args.openai_model,
                        title=paper.title,
                        abstract=abstract,
                        allowed_topics=topics,
                    )
                    entry["topics"] = new_topics
                    entry["topic_source"] = "llm"
                    entry["topic_confidence"] = confidence
                    entry["topics_classified_with"] = current_topics_version
                    classified += 1
                    ok = True
                    break
                except Exception:
                    time.sleep(1.0)
            if not ok:
                classify_errors += 1

    overrides_applied = 0
    for paper in papers:
        if paper.bibcode not in overrides:
            continue
        entry = enrichment_by_bibcode.setdefault(paper.bibcode, {})
        topics_for_paper = [t for t in overrides[paper.bibcode] if t in set(topics)]
        entry["topics"] = topics_for_paper
        entry["topic_source"] = "manual_override"
        entry["topic_confidence"] = 1.0
        entry["topics_classified_with"] = current_topics_version
        overrides_applied += 1

    write_papers_json(out_path, papers, enrichment_by_bibcode=enrichment_by_bibcode)

    print(f"Wrote {args.out}")
    print(f"Counts: docs={len(docs)}, papers={len(papers)}")
    print(f"Topics version: {current_topics_version}")
    if args.skip_abstracts:
        print("Abstracts: skipped")
    else:
        print(f"Abstracts fetched: {abstracts_fetched}")
    if args.skip_topics:
        print("Topics: skipped")
    else:
        print(
            f"Topics classified: {classified} (skipped={classify_skipped}, errors={classify_errors}, overrides={overrides_applied})",
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
