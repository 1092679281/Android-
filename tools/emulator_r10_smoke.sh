#!/usr/bin/env bash
# R10 Android 15 emulator smoke test: no CarWith or physical receiver installed.
set -Eeuo pipefail
APK="$1"
REPORT="$2"
mkdir -p "$REPORT"
exec > >(tee "$REPORT/smoke.txt") 2>&1
trap 'adb logcat -d -v threadtime > "$REPORT/logcat.txt" 2>/dev/null || true; adb shell dumpsys activity activities > "$REPORT/activities.txt" 2>/dev/null || true; adb shell dumpsys window > "$REPORT/windows.txt" 2>/dev/null || true' EXIT
note() { printf '\n[SMOKE] %s\n' "$*"; }
assert_alive() {
  local process
  process="$(adb shell pidof com.mcarplay.app | tr -d '\r' || true)"
  test -n "$process" || { echo "FAIL: app process not alive"; return 1; }
  echo "app pid: $process"
}
assert_png() {
  python3 - "$1" <<'PY'
import os, struct, sys
f = sys.argv[1]
with open(f,"rb") as handle: header=handle.read(24)
assert header[:8] == bytes.fromhex("89504e470d0a1a0a"), "Invalid PNG"
w,h=struct.unpack(">II",header[16:24])
assert w >= 600 and h >= 600 and os.path.getsize(f) > 8000, "Screenshot invalid or empty"
print("screenshot",os.path.basename(f),w,h,os.path.getsize(f))
PY
}
note "Device fingerprint and APK"
adb wait-for-device
adb shell getprop ro.build.version.release | tee "$REPORT/android-release.txt"
adb shell getprop ro.build.version.sdk | tee "$REPORT/android-api.txt"
test "$(tr -d '\r' < "$REPORT/android-api.txt")" = "35"
unzip -t "$APK" >/dev/null
sha256sum "$APK" | tee "$REPORT/apk-sha256.txt"

note "Install the same R10 APK built by this workflow"
adb install -r -t "$APK"
# Test-only pregrant: exercise the app UI instead of stopping at a system permission prompt.
for p in android.permission.BLUETOOTH_CONNECT android.permission.BLUETOOTH_SCAN android.permission.NEARBY_WIFI_DEVICES android.permission.POST_NOTIFICATIONS; do
  adb shell pm grant com.mcarplay.app "$p" || true
done
adb shell pm path com.mcarplay.app | tee "$REPORT/installed-package.txt"
grep -q 'com.mcarplay.app' "$REPORT/installed-package.txt"

note "Launch portrait UI"
adb shell settings put system accelerometer_rotation 0
adb shell settings put system user_rotation 0
adb shell wm user-rotation lock 0 || true
adb logcat -c || true
adb shell am start -W -n com.mcarplay.app/.MainActivity | tee "$REPORT/launch-portrait.txt"
sleep 4
assert_alive
# Complete the actual first-use disclaimer and exercise all three UI tabs.
python3 kit/tools/emulator_r10_ui.py "$REPORT"
assert_alive
adb exec-out screencap -p > "$REPORT/portrait.png"
assert_png "$REPORT/portrait.png"
timeout 35s adb shell uiautomator dump /sdcard/r10-ui-portrait.xml > "$REPORT/ui-portrait-command.txt" 2>&1 || true
adb pull /sdcard/r10-ui-portrait.xml "$REPORT/ui-portrait.xml" >/dev/null 2>&1 || true

note "Landscape UI and process survival"
adb shell settings put system user_rotation 1
adb shell wm user-rotation lock 1 || true
sleep 6
assert_alive
adb exec-out screencap -p > "$REPORT/landscape.png"
assert_png "$REPORT/landscape.png"
adb shell am start -W -n com.mcarplay.app/.MainActivity | tee "$REPORT/launch-landscape.txt"
sleep 3
assert_alive
timeout 35s adb shell uiautomator dump /sdcard/r10-ui-landscape.xml > "$REPORT/ui-landscape-command.txt" 2>&1 || true
adb pull /sdcard/r10-ui-landscape.xml "$REPORT/ui-landscape.xml" >/dev/null 2>&1 || true

note "Inspect Android fatal crash logs"
adb logcat -d -v threadtime > "$REPORT/logcat-check.txt"
if grep -E 'Process: com\.mcarplay\.app(,|$)' "$REPORT/logcat-check.txt" > "$REPORT/fatal.txt"; then
  echo "FAIL: uncaught Android runtime error from app"
  cat "$REPORT/fatal.txt"
  exit 33
fi
if ! adb shell dumpsys activity activities | grep -q 'com.mcarplay.app'; then
  echo "FAIL: app not visible in ActivityManager"
  exit 34
fi
printf 'PASS Android 15 emulator: installed R10 APK, MainActivity survived portrait and landscape, screenshots saved, no app fatal error found.\n' > "$REPORT/result.txt"
note "PASS: emulator smoke test"
