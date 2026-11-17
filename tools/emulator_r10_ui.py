#!/usr/bin/env python3
"""Real Android 15 UI smoke: complete user consent and click all three tabs.

The test emulator is disposable. This does not grant permissions on any user device.
"""
from __future__ import annotations

import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

OUT = Path(sys.argv[1]).resolve()
OUT.mkdir(parents=True, exist_ok=True)
PKG = "com.mcarplay.app"


def adb(*args: str, timeout: int = 45) -> str:
    p = subprocess.run(["adb", *args], text=True, capture_output=True, timeout=timeout)
    if p.returncode:
        raise AssertionError(f"adb {' '.join(args)} failed: {p.stderr[-500:]}")
    return p.stdout


def dump(label: str) -> list[ET.Element]:
    remote = "/sdcard/r10-current-ui.xml"
    adb("shell", "uiautomator", "dump", remote, timeout=45)
    destination = OUT / f"{label}.xml"
    adb("pull", remote, str(destination), timeout=45)
    return list(ET.parse(destination).iter("node"))


def find(nodes: list[ET.Element], resource: str) -> ET.Element | None:
    for node in nodes:
        if node.get("resource-id") == resource:
            return node
    return None


def coord(node: ET.Element) -> tuple[int, int]:
    bounds = node.get("bounds", "")
    nums = [int(x) for x in re.findall(r"\d+", bounds)]
    if len(nums) != 4:
        raise AssertionError(f"Invalid UI bounds {bounds}")
    x1, y1, x2, y2 = nums
    return (x1 + x2) // 2, (y1 + y2) // 2


def tap(node: ET.Element) -> None:
    x, y = coord(node)
    print("tap", node.get("resource-id"), node.get("text"), x, y, flush=True)
    adb("shell", "input", "tap", str(x), str(y))
    time.sleep(1.2)


def screenshot(label: str) -> None:
    file = OUT / f"{label}.png"
    with file.open("wb") as f:
        p = subprocess.run(["adb", "exec-out", "screencap", "-p"], stdout=f, timeout=30)
        if p.returncode:
            raise AssertionError(f"Screenshot failed: {label}")
    if file.stat().st_size < 8000:
        raise AssertionError(f"Screenshot is too small: {file}")
    print("saved", file, file.stat().st_size, flush=True)


def settle_system_permissions() -> list[ET.Element]:
    for attempt in range(5):
        nodes = dump(f"initial-{attempt}")
        allow = find(nodes, "com.android.permissioncontroller:id/permission_allow_button")
        if allow is None:
            return nodes
        print("Granting an emulator-only runtime permission", flush=True)
        tap(allow)
    return dump("initial-final")


print("R10 interactive first-launch UI", flush=True)
nodes = settle_system_permissions()
accept_id = f"{PKG}:id/btnAccept"
accept = find(nodes, accept_id)
if accept is None:
    raise AssertionError("The first-run disclaimer is missing; UI test cannot establish consent state")

# This is the real on-device interaction, not a direct prefs write. Respect the
# app's mandatory 10s timer + scroll-to-bottom before accepting.
for attempt in range(9):
    nodes = dump(f"disclaimer-step-{attempt}")
    accept = find(nodes, accept_id)
    if accept is None:
        raise AssertionError("Disclaimer disappeared without pressing Accept")
    if accept.get("enabled") == "true":
        break
    viewport = find(nodes, f"{PKG}:id/disclaimerScroll")
    if viewport is None:
        raise AssertionError("Disclaimer ScrollView not found")
    nums = [int(x) for x in re.findall(r"\d+", viewport.get("bounds", ""))]
    if len(nums) != 4:
        raise AssertionError("Disclaimer scroll geometry unavailable")
    left, top, right, bottom = nums
    mid = (left + right) // 2
    start = top + int((bottom - top) * 0.85)
    end = top + int((bottom - top) * 0.2)
    adb("shell", "input", "swipe", str(mid), str(start), str(mid), str(end), "330")
    time.sleep(1.5)
    print("swiped disclaimer", attempt + 1, flush=True)
    if attempt == 0:
        time.sleep(11)
else:
    raise AssertionError("Accept stayed disabled after scroll and countdown")
tap(accept)
time.sleep(2)

nodes = dump("post-disclaimer")
if find(nodes, accept_id) is not None:
    raise AssertionError("Disclaimer did not close after clicking Accept")
if find(nodes, f"{PKG}:id/tabConnect") is None:
    raise AssertionError("Main navigation tabs not visible after consent")
screenshot("portrait-main")

for key, label in [("tabSettings", "portrait-settings"), ("tabDiagnostics", "portrait-diagnostics"), ("tabConnect", "portrait-return-connect")]:
    nodes = dump(f"before-{key}")
    tab = find(nodes, f"{PKG}:id/{key}")
    if tab is None:
        raise AssertionError(f"Expected tab {key} missing from UI tree")
    tap(tab)
    dump(f"after-{key}")
    screenshot(label)

(OUT / "ui-result.txt").write_text(
    "PASS: first-run disclaimer scrolled and accepted after countdown; main UI visible; "
    "Connect, Settings and Diagnostics tabs opened; screenshots captured.\n",
    encoding="utf-8",
)
print("PASS: first-run real UI interactions", flush=True)
