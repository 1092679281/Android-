#!/usr/bin/env python3
"""Apply guarded iOS-inspired layout refinements, preserving listener IDs."""
from __future__ import annotations
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path("app/src/main")
LAYOUT = ROOT / "res/layout/activity_main.xml"
DAY = ROOT / "res/values/colors_ui.xml"
NIGHT = ROOT / "res/values-night/colors_ui.xml"
DIMENS = ROOT / "res/values/dimens_ui.xml"
CARD = ROOT / "res/drawable/bg_card.xml"
HERO = ROOT / "res/drawable/bg_hero.xml"
ANDROID_ID = "{http://schemas.android.com/apk/res/android}id"


def once(text: str, before: str, after: str, label: str) -> str:
    count = text.count(before)
    if count != 1:
        raise ValueError(f"{label}: expected unique upstream anchor, got {count}")
    return text.replace(before, after, 1)


def tag_attr(text: str, view_id: str, before: str, after: str) -> str:
    pattern = re.compile(
        r"<[a-zA-Z][\w.]*\b[^>]*\bandroid:id=\"@\+id/"
        + re.escape(view_id) + r"\"[^>]*>", re.DOTALL
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ValueError(f"view id {view_id}: expected one, found {len(matches)}")
    match = matches[0]
    patch = once(match.group(0), before, after, view_id)
    return text[:match.start()] + patch + text[match.end():]


def view_ids(text: str) -> list[str]:
    root = ET.fromstring(text)
    ids = [n.attrib[ANDROID_ID] for n in root.iter() if ANDROID_ID in n.attrib]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate Android view ID")
    return ids


def update_layout(text: str) -> str:
    original_ids = view_ids(text)
    text = once(text, 'android:background="@color/m3_surface"',
                'android:background="@color/ui_bg"', "main background")
    text = tag_attr(text, "contentArea", 'android:paddingStart="16dp"',
                    'android:paddingStart="20dp"')
    text = tag_attr(text, "contentArea", 'android:paddingEnd="16dp"',
                    'android:paddingEnd="20dp"')
    text = tag_attr(text, "shizukuChip", 'android:layout_height="30dp"',
                    'android:layout_height="36dp"')
    text = tag_attr(text, "deviceSubtitle", 'android:textSize="11.5sp"',
                    'android:textSize="13sp"')
    text = tag_attr(text, "deviceSubtitle", 'android:gravity="center_vertical"',
                    'android:gravity="center_vertical"\n                        android:maxLines="2"\n                        android:ellipsize="end"')
    text = tag_attr(text, "ctaButton", 'android:layout_height="52dp"',
                    'android:layout_height="56dp"')
    text = tag_attr(text, "readyHeader", 'android:minHeight="48dp"',
                    'android:minHeight="52dp"')
    text = tag_attr(text, "ctaLabel", 'android:textSize="15.5sp"',
                    'android:textSize="16sp"')
    text = once(text, 'android:text="@string/app_name"\n                        android:textColor="@color/ui_text"\n                        android:textSize="21sp"',
                'android:text="@string/app_name"\n                        android:textColor="@color/ui_text"\n                        android:textSize="24sp"', "header title")
    # Keep fine print legible without altering layout IDs or interaction handlers.
    for old in ["10.5sp", "11sp", "11.5sp"]:
        text = text.replace(f'android:textSize="{old}"', 'android:textSize="12sp"')
    if view_ids(text) != original_ids:
        raise ValueError("view IDs changed")
    ET.fromstring(text)
    return text


def new_outline(text: str) -> str:
    return once(text, '    <solid android:color="@color/ui_card" />',
                '    <solid android:color="@color/ui_card" />\n'
                '    <stroke android:width="1dp" android:color="@color/ui_card_outline" />',
                "grouped card outline")


def add_color(text: str, color: str) -> str:
    if "ui_card_outline" in text:
        raise ValueError("upstream already has R6 card outline token")
    text = once(text, "</resources>",
                f'    <color name="ui_card_outline">{color}</color>\n</resources>', "color token")
    ET.fromstring(text)
    return text


def update_dimens(text: str) -> str:
    text = once(text, '<dimen name="ui_text_display">28sp</dimen>',
                '<dimen name="ui_text_display">30sp</dimen>', "type scale")
    ET.fromstring(text)
    return text


def patch_project(base: Path) -> None:
    actions = {
        LAYOUT: update_layout,
        DAY: lambda x: add_color(x, "#E5E5EA"),
        NIGHT: lambda x: add_color(x, "#38383A"),
        DIMENS: update_dimens,
        CARD: new_outline,
        HERO: new_outline,
    }
    pending = {}
    for rel, transformer in actions.items():
        path = base / rel
        if not path.is_file():
            raise ValueError(f"required source missing: {rel}")
        pending[path] = transformer(path.read_text(encoding="utf-8"))
        ET.fromstring(pending[path])
    for path, output in pending.items():
        path.write_text(output, encoding="utf-8")
    print("R6 UI refinements applied; all existing view IDs preserved")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            raise ValueError("usage: apply_r6_ui.py UPSTREAM_DIRECTORY")
        patch_project(Path(sys.argv[1]).resolve())
    except (ValueError, OSError, ET.ParseError) as exc:
        sys.exit(f"R6 UI GATE BLOCKED: {exc}")
