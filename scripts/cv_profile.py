#!/usr/bin/env python3
"""Shared personal and appointment metadata for all CV renderers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DEFAULT_PROFILE_JSON = "data/cv_profile.json"


def read_cv_profile(path: str | Path = DEFAULT_PROFILE_JSON) -> dict[str, Any]:
    profile_path = Path(path)
    try:
        profile = json.loads(profile_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Missing CV profile file: {profile_path}") from exc

    ucsb = profile.get("ucsb", {})
    required = ("current_title",)
    ucsb_required = ("department", "institution", "appointments")
    missing = [key for key in required if not profile.get(key)]
    missing_ucsb = [key for key in ucsb_required if not ucsb.get(key)]
    if missing or missing_ucsb:
        fields = ", ".join(missing + [f"ucsb.{key}" for key in missing_ucsb])
        raise SystemExit(f"Missing required CV profile fields: {fields}")

    appointments = ucsb["appointments"]
    if not isinstance(appointments, list) or not appointments:
        raise SystemExit("CV profile field ucsb.appointments must be a non-empty list.")
    for appointment in appointments:
        if not appointment.get("title") or not appointment.get("dates"):
            raise SystemExit("Each UCSB appointment must have title and dates.")

    return profile


def render_ucsb_work_experience(profile: dict[str, Any]) -> str:
    """Render the full CV's UCSB appointment entries."""
    ucsb = profile["ucsb"]
    lines: list[str] = []
    for appointment in ucsb["appointments"]:
        lines.extend(
            [
                rf"  \noindent \textbf{{{appointment['title']}}} \hfill {appointment['dates']} \\",
                rf"  {ucsb['institution']} \\",
                r"  \\",
            ]
        )
    return "\n".join(lines)
