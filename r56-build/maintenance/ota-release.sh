#!/usr/bin/env bash
set -euo pipefail

source_dir="$1"
tag="$2"
output="$3"
helper="$(dirname "${BASH_SOURCE[0]}")/ota-release.py"
sdk_tools="$ANDROID_HOME/build-tools/35.0.0"
signer="$sdk_tools/apksigner"

version="$(python3 "$helper" stamp "$source_dir" "$tag")"
base="$(sed -n 's/^base=//p' <<< "$version")"
code="$(sed -n 's/^code=//p' <<< "$version")"
mkdir -p "$output"
(
    cd "$source_dir"
    ./gradlew --no-daemon --console=plain --dependency-verification strict \
        "-Pmcarplay.releaseTag=$tag" -Pmcarplay.requireReleaseSigning=true -Pmcarplay.minifyRelease=true \
        :app:assembleStandardRelease
)
apk="mcarplay-$base.apk"
cp "$source_dir/app/build/outputs/apk/standard/release/app-standard-release.apk" "$output/$apk"
"$sdk_tools/aapt" dump badging "$output/$apk" > "$output/APK-metadata.txt"
grep -F "package: name='com.mcarplay.app' versionCode='$code' versionName='$base'" "$output/APK-metadata.txt"
"$signer" verify --verbose --print-certs "$output/$apk" > "$output/APK-signature.txt"
certificate="$(sed -n 's/^Signer #[0-9]* certificate SHA-256 digest: //p' "$output/APK-signature.txt")"
[[ "$certificate" =~ ^[a-fA-F0-9]{64}$ && "${certificate,,}" == "${OTA_SIGNER_SHA256,,}" ]] || {
    echo "APK signer does not match the configured OTA certificate." >&2
    exit 1
}
(
    cd "$output"
    sha256sum "$apk" > SHA256SUMS.txt
)
