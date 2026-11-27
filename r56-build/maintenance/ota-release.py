"""Validate OTA version tags and select previously published app releases."""

import json
from pathlib import Path
import re
import sys


def release_version(tag):
    match = re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]?)\.(0|[1-9][0-9]?)(?:-test\.(0|[1-9][0-9]*))?", tag)
    if not match:
        raise ValueError(f"Invalid OTA tag: {tag}")
    major, minor, patch = map(int, match.groups()[:3])
    test = int(match[4]) if match[4] is not None else None
    code = (major * 10000 + minor * 100 + patch) * 10000
    if not 0 < code <= 2100000000 or (test is not None and test > 2147483647):
        raise ValueError(f"OTA version out of range: {tag}")
    return f"{major}.{minor}.{patch}", code, (major, minor, patch, test is None, test or 0)


def stamp(root, tag):
    base, code, order = release_version(tag)
    gradle = root / "app/build.gradle.kts"
    original = gradle.read_text(encoding="utf-8")
    pattern = r'^val appVersionName = "([^"]+)"$'
    matches = re.findall(pattern, original, flags=re.MULTILINE)
    if len(matches) != 1 or order[:3] < release_version("v" + matches[0])[2][:3]:
        raise ValueError("Expected exactly one source version no newer than the OTA version")
    gradle.write_text(re.sub(pattern, f'val appVersionName = "{base}"', original, flags=re.MULTILINE), encoding="utf-8")
    print(f"base={base}\ncode={code}")


def previous_release(pages, requested_tag):
    _, _, requested = release_version(requested_tag)
    releases = []
    for page in pages:
        for release in page:
            tag = release["tag_name"]
            if release["draft"]:
                continue
            try:
                base, _, order = release_version(tag)
            except ValueError:
                continue
            names = {f"mcarplay-{base}.apk", f"mcarplay-{tag[1:]}.apk"}
            apks = [a["name"] for a in release["assets"] if a["name"] in names and a["state"] == "uploaded"]
            if len(apks) > 1:
                raise ValueError(f"Ambiguous APK assets in {tag}")
            if apks:
                releases.append((order, tag, apks[0]))
    if releases:
        order, tag, apk = max(releases)
        if requested <= order:
            raise ValueError(f"OTA tag must advance beyond {tag}")
        print(f"{tag}\t{apk}")


if __name__ == "__main__":
    try:
        if sys.argv[1] == "stamp":
            stamp(Path(sys.argv[2]), sys.argv[3])
        elif sys.argv[1] == "previous":
            previous_release(json.load(sys.stdin), sys.argv[2])
        else:
            raise ValueError("Expected stamp or previous")
    except (OSError, ValueError) as error:
        sys.exit(str(error))
