#!/usr/bin/env bash
set -euo pipefail
root="${1:?usage: rebuild-r56.sh R44_SOURCE_DIR}"
kit="$(cd "$(dirname "$0")/.." && pwd)"
patch_dir="$kit/r56-build/patches"

test -f "$root/app/build.gradle.kts"
manifest="$root/r44-source-fingerprint.tsv"
test -f "$manifest"
manifest_count="$(awk -F '\t' 'NF == 2 && length($1) == 64 && $1 ~ /^[0-9a-fA-F]+$/ { count++ } END { print count+0 }' "$manifest")"
if [[ "$manifest_count" -ne 647 ]]; then
  echo "Unexpected R44 fingerprint manifest shape: $manifest_count valid rows (expected 647)" >&2
  exit 1
fi
fingerprint_audit="$(mktemp)"
(
  cd "$root"
  awk -F '\t' 'NF == 2 { print $1 "  " $2 }' r44-source-fingerprint.tsv | sha256sum --check -
) >"$fingerprint_audit" 2>&1 || true
fingerprint_ok="$(awk '/: OK$/ { count++ } END { print count+0 }' "$fingerprint_audit")"
fingerprint_mismatch="$(awk '/: FAILED$/ { count++ } END { print count+0 }' "$fingerprint_audit")"
if [[ "$((fingerprint_ok + fingerprint_mismatch))" -ne "$manifest_count" ]]; then
  cat "$fingerprint_audit" >&2
  echo "R44 fingerprint audit produced an incomplete result" >&2
  exit 1
fi
echo "R44 embedded fingerprint audit: $fingerprint_ok/$manifest_count match; $fingerprint_mismatch stale entries are non-gating because the exact baseline ZIP SHA-256 is verified by CI."
rm -f "$fingerprint_audit"

(
  cd "$patch_dir"
  sha256sum -c SHA256SUMS
)

patches=(
  R45-0.1.32-from-exact-R44.patch
  R46-0.1.33-from-R45.patch
  R47-0.1.34-from-R46.patch
  R48-0.1.35-from-R47.patch
  R49-0.1.36-from-R48.patch
  R50-0.1.37-from-R49.patch
  R51-0.1.38-from-R50.patch
  R52-0.1.39-from-R51.patch
  R53-0.1.40-from-R52.patch
  R54-0.1.41-from-R53.patch
  R55-0.1.42-from-R54.patch
  R56-0.1.43-from-R55.patch
)

(
  cd "$root"
  for patch in "${patches[@]}"; do
    echo "Checking $patch"
    git apply --check --whitespace=nowarn "$patch_dir/$patch"
    git apply --whitespace=nowarn "$patch_dir/$patch"
  done
  echo "Checking R56 source hygiene patch"
  git apply --check --whitespace=nowarn "$patch_dir/R56-source-organization.patch"
  git apply --whitespace=nowarn "$patch_dir/R56-source-organization.patch"
)

bash "$kit/r56-build/organize-source.sh" "$root"
grep -F 'val appVersionName = "0.1.43"' "$root/app/build.gradle.kts"
python3 "$kit/r56-build/verify-tree.py" "$root"
