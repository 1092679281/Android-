#!/usr/bin/env python3
"""R10 guarded native CarWith source FPS negotiation. No display-FPS guarantee."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import integrate_and_build_r9 as r9

def checked(src, old, new, label):
    return r9.change(src, old, new, "R10 " + label)

def improve_fps(base: Path, kit: Path) -> None:
    for name, dest in [
        ("SourceFpsPolicy.kt", "app/src/main/java/com/mcarplay/app/video/SourceFpsPolicy.kt"),
        ("SourceFpsPolicyTest.kt", "app/src/test/java/com/mcarplay/app/video/SourceFpsPolicyTest.kt"),
        ("VideoInitFpsR10Test.kt", "app/src/test/java/com/mcarplay/app/carlife/VideoInitFpsR10Test.kt"),
    ]:
        r9.r8.copy_new(kit, base, name, dest)

    sm = base / "app/src/main/java/com/mcarplay/app/carlife/CarLifeStateMachine.kt"
    data = sm.read_text(encoding="utf-8")
    data = checked(data,
        "        height: Int = CarLifeProtocol.DEFAULT_HEIGHT,\n    ): List<Action> {\n",
        "        height: Int = CarLifeProtocol.DEFAULT_HEIGHT,\n"
        "        fps: Int = CarLifeProtocol.DEFAULT_FPS,\n"
        "    ): List<Action> {\n",
        "source FPS parameter")
    data = checked(data,
        "Action(CarLifeProtocol.VIDEO_ENCODER_INIT, CarLifeProtocol.videoInitPayload(width, height))",
        "Action(CarLifeProtocol.VIDEO_ENCODER_INIT, CarLifeProtocol.videoInitPayload(width, height, fps))",
        "actual protocol request FPS")
    sm.write_text(data, encoding="utf-8")

    carlife = base / "app/src/main/java/com/mcarplay/app/carlife/CarLifeSession.kt"
    data = carlife.read_text(encoding="utf-8")
    data = checked(data,
        "    private val requestedVideoSize: Pair<Int, Int>? = null,\n",
        "    private val requestedVideoSize: Pair<Int, Int>? = null,\n"
        "    private val requestedVideoFps: Int = CarLifeProtocol.DEFAULT_FPS,\n",
        "pass source FPS into session")
    data = checked(data,
        "            stateMachine.requestVideoInit(width, height).forEach(::sendAction)\n",
        "            log(\"CARLIFE: 源帧率请求 \" + requestedVideoFps + \"fps；以协商响应为准\")\n"
        "            stateMachine.requestVideoInit(width, height, requestedVideoFps).forEach(::sendAction)\n",
        "native fps negotiation")
    data = checked(data,
        "            videoWidth = format.width\n            videoHeight = format.height\n",
        "            videoWidth = format.width\n"
        "            videoHeight = format.height\n"
        "            log(\"CARLIFE: 原生源 VIDEO_INIT_DONE \" + format.width + \"x\" + format.height + \"@\" +\n"
        "                format.fps + \"fps（请求 \" + requestedVideoFps + \"fps；非车机显示帧率）\")\n",
        "truthful source reply")
    carlife.write_text(data, encoding="utf-8")

    controller = base / "app/src/main/java/com/mcarplay/app/SessionController.kt"
    data = controller.read_text(encoding="utf-8")
    data = checked(data,
        "import com.mcarplay.app.video.VideoSender\n",
        "import com.mcarplay.app.video.VideoSender\nimport com.mcarplay.app.video.SourceFpsPolicy\n",
        "import source policy")
    data = checked(data,
        "        requestedVideoSize: Pair<Int, Int>? = null,\n    ): CarLifeSession {",
        "        requestedVideoSize: Pair<Int, Int>? = null,\n"
        "        requestedVideoFps: Int = CarLifeProtocol.DEFAULT_FPS,\n"
        "    ): CarLifeSession {",
        "bind source FPS")
    data = checked(data,
        "                requestedVideoSize = requestedVideoSize,\n",
        "                requestedVideoSize = requestedVideoSize,\n"
        "                requestedVideoFps = requestedVideoFps,\n",
        "constructor fps")
    data = checked(data,
        "                                var pendingVideoW = 0\n                                var pendingVideoH = 0\n",
        "                                var pendingVideoW = 0\n"
        "                                var pendingVideoH = 0\n"
        "                                var pendingVideoFps = CarLifeProtocol.DEFAULT_FPS\n",
        "hold FPS across record")
    data = checked(data,
        "                                    val fps =\n"
        "                                        appContext\n"
        "                                            ?.let {\n"
        "                                                DisplayPrefs\n"
        "                                                    .fps(it)\n"
        "                                            } ?: 30\n",
        "                                    val fps = SourceFpsPolicy.effective(\n"
        "                                        requested = appContext?.let(DisplayPrefs::fps) ?: 30,\n"
        "                                        receiverMax = setup.maxFps,\n"
        "                                    )\n"
        "                                    pendingVideoFps = fps\n",
        "receiver FPS bound")
    data = checked(data,
        "                                            CarLifeProtocol.videoRequestFor(setup.displayWidth, setup.displayHeight),\n"
        "                                        )",
        "                                            CarLifeProtocol.videoRequestFor(setup.displayWidth, setup.displayHeight),\n"
        "                                            requestedVideoFps = pendingVideoFps,\n"
        "                                        )",
        "native source request")
    controller.write_text(data, encoding="utf-8")
    print("R10 requests source native FPS capped by receiver /info maxFPS", flush=True)

def main() -> None:
    kit = Path(__file__).resolve().parent.parent
    output = Path(os.environ.get("R10_OUTPUT", "apk-output-r10")).resolve()
    staging = output.parent / (output.name + "-staging")
    if output.exists() or staging.exists():
        raise r9.r8.r7.Blocked("R10 output/staging already exists")
    original = r9.quick_connect
    def with_r10(base: Path, selected_kit: Path) -> None:
        original(base, selected_kit)
        improve_fps(base, selected_kit)
    r9.quick_connect = with_r10
    os.environ["R9_OUTPUT"] = str(staging)
    r9.main()
    if os.environ.get("R19_SOURCE_ONLY") == "1":
        return
    apk = staging / "mcarplay-LaCrosse-R9-quick-connect-debug.apk"
    if not apk.is_file() or not zipfile.is_zipfile(apk):
        raise r9.r8.r7.Blocked("R10 APK missing or invalid")
    output.mkdir(parents=True, exist_ok=False)
    dest = output / "mcarplay-LaCrosse-R10-source60-debug.apk"
    shutil.copy2(apk, dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(digest + "  " + dest.name + "\n", encoding="utf-8")
    (output / "SCOPE.txt").write_text(
        "R10 native CarWith source FPS request 30/60 capped to valid car maxFPS, "
        "log source response. No claimed stable car 60fps or native iOS UI. "
        "Unchanged protocol security. Not vehicle-tested.\n", encoding="utf-8")
    shutil.rmtree(staging)
    print("R10 VERIFIED BUILD:", dest, digest, flush=True)

if __name__ == "__main__":
    try:
        main()
    except (r9.r8.r7.Blocked, subprocess.CalledProcessError, OSError, AssertionError, ValueError) as err:
        sys.exit(f"BLOCKED; NO VERIFIED R10 APK: {err}")
