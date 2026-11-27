#!/usr/bin/env bash
set -euo pipefail
root="${1:?usage: rebuild-r56.sh R44_SOURCE_DIR}"
kit="$(cd "$(dirname "$0")/.." && pwd)"
patch_dir="$kit/r56-build/patches"

test -f "$root/app/build.gradle.kts"
test -f "$root/r44-source-fingerprint.tsv"

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
