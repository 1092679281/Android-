# 2023 LaCrosse / HyperOS · mcarplay R5

This private repository builds an experimental mcarplay **debug APK** using GitHub Actions. It checks out upstream `wangxso/mcarplay` at fixed commit `8e25e0f69ab7a3bec14649542adea6eb22f74f9a` and instruments only **sender-side video cadence**.

It **does not** activate all earlier R3 components, certify actual vehicle display FPS, or guarantee stable 60 FPS. The telemetry counts frames written to the sending socket; a passing Android build only proves package compilation, not vehicle compatibility.

## Build

GitHub → Actions → **LaCrosse R5 guarded APK** → **Run workflow** (or push to `main`). Only a successful Gradle unit test, lint and `assembleStandardDebug` produces an artifact.

Artifact: `LaCrosse-R5-debug-apk`. Download it under the successful workflow run's **Artifacts** section. This is a debug-signed build, which may conflict with existing APK signatures.

`tools/integrate_and_build.py` fails closed if the pinned upstream sources change, mandatory injection points disappear, SDK is missing, or the compiled APK lacks AndroidManifest.xml/classes.dex.
