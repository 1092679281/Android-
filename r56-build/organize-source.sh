#!/usr/bin/env bash
set -euo pipefail
root="${1:?usage: organize-source.sh SOURCE_DIR}"
[[ -d "$root" && -f "$root/app/build.gradle.kts" ]]
mkdir -p "$root/docs/provenance/source-fingerprints" "$root/archive/legacy-build-scripts" "$root/archive/test-evidence"
shopt -s nullglob
for f in "$root"/r*-source-fingerprint.tsv; do mv -n "$f" "$root/docs/provenance/source-fingerprints/"; done
for f in "$root"/build-r27-signed.ps1 "$root"/build-r28-signed.ps1; do [[ ! -f "$f" ]] || mv -n "$f" "$root/archive/legacy-build-scripts/"; done
for d in carplay-simulation-evidence lacrosse-test-evidence; do [[ ! -d "$root/$d" ]] || mv -n "$root/$d" "$root/archive/test-evidence/"; done
find "$root" -type d -name __pycache__ -prune -exec rm -rf {} +
[[ ! -e "$root/docs/CARWITH-ENTRY-FINDINGS.md-e" ]]
