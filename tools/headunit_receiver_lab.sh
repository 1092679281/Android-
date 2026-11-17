#!/usr/bin/env bash
# R11: Linux simulated CarPlay head-unit receiver, NOT the Android phone app.
set -Eeuo pipefail
ALLPLAY="$(realpath "$1")"
REPORT="$(realpath -m "$2")"
mkdir -p "$REPORT"
cd "$ALLPLAY"
exec > >(tee "$REPORT/headunit-test.txt") 2>&1
export SDL_AUDIODRIVER=dummy SDL_RENDER_DRIVER=software LIBGL_ALWAYS_SOFTWARE=1
export ALLPLAY_STATE_DIR="$REPORT/state"
mkdir -p "$ALLPLAY_STATE_DIR"

echo "[HEADUNIT] pinned AllPlay receiver: $(git rev-parse HEAD)"
echo "[HEADUNIT] Generate ephemeral SELF-SIGNED identity for mock tests only (never OEM/MFi)"
bash scripts/make-test-identity.sh "$ALLPLAY/identity" > "$REPORT/identity-generation.txt" 2>&1
test -s "$ALLPLAY/identity/identity.pk8"
test -s "$ALLPLAY/identity/certificate.p7b"
echo "[HEADUNIT] Cryptography + iAP2 protocol tests"
./build/iap2_test > "$REPORT/iap2.txt" 2>&1
./build/m3_test > "$REPORT/m3.txt" 2>&1
./build/aa_wire_test > "$REPORT/aa.txt" 2>&1
echo "[HEADUNIT] RTSP OPTIONS + GET /info and binary plist"
ALLPLAY_SELFTEST="$ALLPLAY/build/core_selftest" M1_PORT=17093 \
  ALLPLAY_STATE_DIR="$REPORT/receiver-selftest" bash scripts/m1-check.sh \
  > "$REPORT/rtsp.txt" 2>&1

echo "[HEADUNIT] Synthetic source: H264 1920x720 at 60 fps / 180 frames"
ffmpeg -hide_banner -loglevel error -f lavfi \
 -i "testsrc2=size=1920x720:rate=60:duration=3" \
 -frames:v 180 -c:v libx264 -preset ultrafast -tune zerolatency \
 -g 60 -bf 0 -pix_fmt yuv420p -f h264 -y "$REPORT/synthetic60.h264"
ffprobe -v error -f h264 -count_frames \
 -show_entries stream=width,height,nb_read_frames -of default=noprint_wrappers=1 \
 "$REPORT/synthetic60.h264" > "$REPORT/video-source.txt"

echo "[HEADUNIT] H264 software decode / letterbox / displayed screenshot"
timeout 70s xvfb-run -a -s "-screen 0 1920x1080x24" \
 ./build/video_probe --h264 "$REPORT/synthetic60.h264" --fps 60 \
 --frames 180 --window 1920x720 --dump "$REPORT/car-screen.ppm" \
 > "$REPORT/video-probe.txt" 2>&1
grep -q 'decoded first frame' "$REPORT/video-probe.txt"
grep -q 'decoder OK' "$REPORT/video-probe.txt"
test -s "$REPORT/car-screen.ppm"
ffmpeg -hide_banner -loglevel error -y -i "$REPORT/car-screen.ppm" "$REPORT/car-screen.png"

echo "[HEADUNIT] RTSP encrypted H264 and touch: fake CarPlay phone -> receiver"
set +e
timeout 65s xvfb-run -a -s "-screen 0 1920x1080x24" \
 bash -c '
 set -Eeuo pipefail
 host="$1"; phone="$2"; report="$3"; h264="$4"
 "$host" --port 17094 --screen 1920x720 --no-avahi --no-audio \
    --statusbar --inject-touch 0.5,0.5 --frames 700 \
    > "$report/receiver-session.txt" 2>&1 &
 pid=$!
 trap "kill $pid 2>/dev/null || true" EXIT
 sleep 2
 "$phone" --host 127.0.0.1 --port 17094 --h264 "$h264" \
    --fps 60 --frames 180 --loop --seconds 4 \
    > "$report/fake-phone.txt" 2>&1
 wait "$pid"
 ' bash "$ALLPLAY/build/allplay_host" "$ALLPLAY/build/fake_phone" \
 "$REPORT" "$REPORT/synthetic60.h264"
rc="$?"
set -e
printf '%s\n' "$rc" > "$REPORT/receiver-session-exit.txt"
if [ "$rc" -ne 0 ]; then
  echo "FAIL: simulated sender-to-head-unit RTSP stream; inspect receiver-session.txt / fake-phone.txt"
  exit "$rc"
fi
echo "[HEADUNIT] Inspecting receiver-side frame counters"
python3 - "$REPORT" <<'PY'
from pathlib import Path
import sys,re,json
p=Path(sys.argv[1])
log=(p/"video-probe.txt").read_text(errors="replace")
match=re.search(r"decoded (\d+) frames, shallow queue dropped (\d+), presented (\d+), ([^,]+), took (\d+) ms",log)
assert match, "decoder counters not found"
decoded,dropped,presented,state,elapsed=match.groups()
assert state.strip()=="decoder OK" and int(decoded)>0 and int(presented)>0
data=(p/"car-screen.ppm").read_bytes()
assert data.startswith(b"P6\n") and len(data)>100000
rates=re.search(r"decode ([\d.]+) fps .*?present ([\d.]+) fps",log)
summary={
 "target":"AllPlay Linux virtual CarPlay head unit, NOT OEM 2023 Buick LaCrosse",
 "input":"Synthetic 1920x720 60fps H264; not user's R10 APK",
 "decoded_frames":int(decoded),
 "dropped_from_shallow_queue":int(dropped),
 "present_calls":int(presented),
 "synthetic_input_fps":60,
 "software_decode_fps":float(rates.group(1)) if rates else None,
 "software_present_fps":float(rates.group(2)) if rates else None,
 "actual_LaCrosse_display_fps":"not measured",
 "car_screen_screenshot":"car-screen.png",
 "full_android_to_vehicle_compatibility":"not tested",
 "test_result":"virtual receiver protocol, decode, screen and mock sender tests passed"
}
(p/"headunit-result.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n")
print(json.dumps(summary,ensure_ascii=False,indent=2))
PY
echo "PASS: virtual head-unit receiver testing"
