#!/usr/bin/env python3
"""R15: adapt upstream's signed, user-confirmed OTA updater to private-source/public-binary releases."""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
import integrate_and_build_r14 as r14

CHANNEL_REPOSITORY = "1092679281/CarPlay-Updates"
BASE_VERSION = "0.1.8"


class PatchMismatch(RuntimeError):
    pass


def replace_once(file: Path, old: str, new: str, reason: str) -> None:
    content = file.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise PatchMismatch(f"{reason}: expected one occurrence, found {count}: {file}")
    file.write_text(content.replace(old, new, 1), encoding="utf-8")


def patch(base: Path, kit: Path) -> None:
    # Preserve all of upstream's existing update protections: SHA-256,
    # PackageManager signature checks, versionCode, minSdk, FileProvider, and
    # Android's explicit install confirmation / unknown-apps settings.
    update = base / "app/src/main/java/com/mcarplay/app/update"
    replace_once(
        update / "GitHubRelease.kt",
        '    const val REPOSITORY = "wangxso/mcarplay"',
        f'    const val REPOSITORY = "{CHANNEL_REPOSITORY}"',
        "select project-owned public release channel, never the private source",
    )
    replace_once(
        base / "app/build.gradle.kts",
        'val appVersionName = "0.1.7"',
        f'val appVersionName = "{BASE_VERSION}"',
        "monotonically bump versionCode for R15 update-capable APK",
    )
    # The upstream unit test correctly asserts the page belongs to the
    # configured release channel. Update its single hardcoded original URL.
    replace_once(
        base / "app/src/test/java/com/mcarplay/app/update/GitHubReleaseTest.kt",
        '"https://github.com/wangxso/mcarplay/releases/tag/v0.1.2-test.1"',
        f'"https://github.com/{CHANNEL_REPOSITORY}/releases/tag/v0.1.2-test.1"',
        "adapt upstream release URL regression",
    )
    # The upstream URL rejection test replaces the original owner name.
    # Once the repository changes, it must mutate the NEW owner, or the
    # "invalid" URL is identical to the valid URL and produces a false failure.
    replace_once(
        base / "app/src/test/java/com/mcarplay/app/update/UpdateHttpTest.kt",
        'release.apk.url.replace("wangxso", "other")',
        'release.apk.url.replace("1092679281", "other")',
        "adapt repository-owner spoofing regression to public update channel",
    )
    # Explicitly reject the original upstream and other untrusted release
    # locations; accepting a foreign URL would break checksum trust binding.
    release_test = base / "app/src/test/java/com/mcarplay/app/update/GitHubReleaseTest.kt"
    replace_once(
        release_test,
        '    @Test\n    fun requiresDigestOrChecksumAsset() {\n',
        '    @Test\n'
        '    fun projectUpdaterRefusesOriginalUpstreamReleaseUrls() {\n'
        '        val json = releaseJson()\n'
        '        json.getJSONArray("assets").getJSONObject(0).put(\n'
        '            "browser_download_url",\n'
        '            "https://github.com/wangxso/mcarplay/releases/download/v0.1.2-test.1/mcarplay-0.1.2.apk",\n'
        '        )\n'
        '        assertNull(UpdateSource.latest(JSONArray().put(json).toString(), true))\n'
        '    }\n\n'
        '    @Test\n    fun requiresDigestOrChecksumAsset() {\n',
        "regression: refuse upstream repo or arbitrary APK host",
    )
    # App's update page is already wired from the home UI, auto-checks on
    # open, displays progress/cancel, verifies signer and prompts installer.
    # Make the source/channel and limitations explicit in both shipped locales.
    strings = {
        "values/strings.xml": (
            "请停车并断开车机后操作。仅从本仓库 GitHub Releases 下载；安装前检查哈希、包名、版本和签名，仍需系统确认。不会自动卸载或清数据。",
            "请停车并断开车机后操作。仅从 CarPlay-Updates 公开发行页下载正式签名的 APK；校验 SHA-256、包名、版本和签名后调用 Android 系统安装界面。不会自动卸载或清除数据。",
        ),
        "values-en/strings.xml": (
            "Updates are downloaded only from this repository\\'s GitHub Releases",
            "Updates are downloaded only from the public CarPlay-Updates GitHub Releases",
        ),
    }
    for path, (old, new) in strings.items():
        target = base / "app/src/main/res" / path
        if old in target.read_text(encoding="utf-8"):
            replace_once(target, old, new, "explain public binary release channel")
    print(
        f"R15: update page now checks https://github.com/{CHANNEL_REPOSITORY}/releases "
        f"(application base version {BASE_VERSION})",
        flush=True,
    )


def main() -> None:
    output = Path(os.environ.get("R15_OUTPUT", "apk-output-r15")).resolve()
    stage = output.parent / (output.name + "-staging")
    if output.exists() or stage.exists():
        raise PatchMismatch("R15 output or staging already exists")
    original = r14.patch

    def with_r15(base: Path, patchkit: Path) -> None:
        original(base, patchkit)
        patch(base, patchkit)

    r14.patch = with_r15
    os.environ["R14_OUTPUT"] = str(stage)
    r14.main()
    debug = stage / "mcarplay-LaCrosse-R14-airplay-setup-record-debug.apk"
    if not debug.is_file() or not zipfile.is_zipfile(debug):
        raise PatchMismatch("full Android test/build did not create R14 staging APK")

    # Release publishing must use a persistent user-owned signing key.
    # Debug signing keys generated in ephemeral CI runners cannot support
    # seamless Android package updates and MUST NOT be published as releases.
    signed = os.environ.get("R15_SIGNED_RELEASE", "0") == "1"
    if signed:
        expected_tag = f"v{BASE_VERSION}"
        if os.environ.get("R15_RELEASE_TAG") != expected_tag:
            raise PatchMismatch(f"signed releases require tag {expected_tag}")
        for variable in ("MCARPLAY_KEYSTORE_FILE", "KEYSTORE_PASSWORD", "KEY_ALIAS", "KEY_PASSWORD"):
            if not os.environ.get(variable):
                raise PatchMismatch(f"missing persistent signing input: {variable}")
        base = Path(os.environ["R7_UPSTREAM"]).resolve()
        subprocess.run(
            [
                "bash", "./gradlew", "--no-daemon", "spotlessCheck",
                ":app:lintStandardRelease", ":app:assembleStandardRelease",
                "-Pmcarplay.requireReleaseSigning=true",
                f"-Pmcarplay.releaseTag={expected_tag}",
            ],
            cwd=base,
            check=True,
        )
        built = base / "app/build/outputs/apk/standard/release/app-standard-release.apk"
        name = f"mcarplay-{BASE_VERSION}.apk"
        if not built.is_file() or not zipfile.is_zipfile(built):
            raise PatchMismatch("signed release APK not produced")
        # A second Android package signature validation is performed by
        # the client before installation.
        sdk = os.environ.get("ANDROID_HOME", os.environ.get("ANDROID_SDK_ROOT", ""))
        tools = sorted((Path(sdk) / "build-tools").glob("*/apksigner")) if sdk else []
        if not tools:
            raise PatchMismatch("apksigner unavailable for release signature verification")
        subprocess.run([str(tools[-1]), "verify", "--verbose", str(built)], check=True)
    else:
        built = debug
        name = "mcarplay-LaCrosse-R15-online-update-debug.apk"

    output.mkdir(parents=True, exist_ok=False)
    destination = output / name
    shutil.copy2(built, destination)
    sha = hashlib.sha256(destination.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(f"{sha}  {name}\n", encoding="utf-8")
    (output / "SCOPE.txt").write_text(
        f"R15 update channel: https://github.com/{CHANNEL_REPOSITORY}/releases\n"
        f"APK flavor: {'SIGNED RELEASE' if signed else 'DEBUG TEST ONLY'}\n"
        "Android updater is user-initiated; HTTPS, checksums, package and signer "
        "checks remain enforced. Distribution requires an existing PUBLIC binary "
        "release repository and a persistent app signing key. The private source "
        "repository's GitHub Actions artifacts are NOT an anonymous update feed.\n",
        encoding="utf-8",
    )
    shutil.rmtree(stage)
    print(f"R15 {'SIGNED RELEASE' if signed else 'DEBUG TEST'} APK: {destination} sha256={sha}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.exit(f"R15 BUILD BLOCKED: {exc}")
