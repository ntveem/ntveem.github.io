"""Shared topic color/style helpers for site generators."""

from __future__ import annotations

import hashlib

BASE_TOPIC_COLORS = {
    "cosmology": ("hsl(214 55% 47%)", "hsl(214 57% 40%)"),
    "gravitational lensing": ("hsl(195 52% 45%)", "hsl(195 56% 38%)"),
    "gravitational waves": ("hsl(226 56% 48%)", "hsl(226 58% 40%)"),
    "black holes": ("hsl(252 35% 44%)", "hsl(252 38% 36%)"),
    "neutron stars": ("hsl(281 43% 46%)", "hsl(281 47% 38%)"),
    "gamma ray bursts": ("hsl(102 43% 40%)", "hsl(102 47% 33%)"),
    "reionization": ("hsl(168 43% 40%)", "hsl(168 45% 33%)"),
    "dark matter": ("hsl(336 46% 46%)", "hsl(336 49% 38%)"),
    "recombination": ("hsl(26 54% 47%)", "hsl(26 58% 40%)"),
}


def topic_colors(topic: str) -> tuple[str, str]:
    key = topic.strip().lower()
    preset = BASE_TOPIC_COLORS.get(key)
    if preset:
        return preset
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    hue = int(digest[:6], 16) % 360
    bg = f"hsl({hue} 44% 46%)"
    active = f"hsl({hue} 49% 38%)"
    return bg, active


def topic_style_attr(topic: str) -> str:
    bg, active = topic_colors(topic)
    return f' style="--topic-bg:{bg};--topic-active:{active};"'
