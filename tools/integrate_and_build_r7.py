#!/usr/bin/env python3
"""Fail-closed sender-side R5 telemetry integration and Android debug APK build."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile

PINNED = "8e25e0f69ab7a3bec14649542adea6eb22f74f9a"
UPSTREAM = Path("upstream")
SENDER = Path("app/src/main/java/com/mcarplay/app/video/VideoSender.kt")
METER = Path("app/src/main/java/com/mcarplay/app/video/VideoFrameCadenceMeter.kt")
TEST = Path("app/src/test/java/com/mcarplay/app/video/R6ForwardCadenceTest.kt")
APK = Path("app/build/outputs/apk/standard/debug/app-standard-debug.apk")


class Blocked(Exception):
    pass


def replace_once(src, original, replacement, label):
    count = src.count(original)
    if count != 1:
        raise Blocked(f"{label}: expected one exact insertion point; saw {count}")
    return src.replace(original, replacement, 1)


def integrate(src):
    patch = [
        (
            "    private val streamStats = PassthroughStreamStats()\n",
            "    private val streamStats = PassthroughStreamStats()\n"
            "    private val r5Cadence = VideoFrameCadenceMeter(nominalFps = targetFps.coerceIn(1, 120))\n"
            "    private val r5StallLogged = AtomicBoolean(false)\n",
            "cadence fields",
        ),
        (
            "    val framesSentTotal: Long get() = framesSent\n",
            "    val framesSentTotal: Long get() = framesSent\n"
            "\n"
            "    /** Sender-only socket write cadence; not head-unit display FPS. */\n"
            "    private fun r5CadenceSummary(): String {\n"
            "        val s = r5Cadence.snapshot()\n"
            "        return \"outFps=${s.forwardedFps} p95GapMs=${s.p95IntervalMs} \" +\n"
            "            \"longGaps=${s.longGaps} idleMs=${s.idleMs} \" +\n"
            "            \"ptsRegressions=${s.nonMonotonicPts} stalled=${s.stalled}\"\n"
            "    }\n"
            "\n"
            "    private fun maybeReportR5Stall() {\n"
            "        val s = r5Cadence.snapshot()\n"
            "        if (s.stalled && r5StallLogged.compareAndSet(false, true)) {\n"
            "            log(\"VIDEO: R5 发帧停顿 ${s.idleMs}ms（仅发送端）\")\n"
            "        }\n"
            "    }\n",
            "summary",
        ),
        (
            "            ScreenOutputGate.Transition.PAUSED -> {\n",
            "            ScreenOutputGate.Transition.PAUSED -> {\n"
            "                r5Cadence.reset()\n"
            "                r5StallLogged.set(false)\n",
            "pause reset",
        ),
        (
            "            ScreenOutputGate.Transition.RESUMING -> {\n",
            "            ScreenOutputGate.Transition.RESUMING -> {\n"
            "                r5Cadence.reset()\n"
            "                r5StallLogged.set(false)\n",
            "resume reset",
        ),
        (
            "                            // 转码输出顶替了 CarWith 透传：诊断时间线的帧数 / 字节 / 时间戳照常更新，\n",
            "                            if (sent > 0) {\n"
            "                                r5Cadence.recordForwardedFrame(bufferInfo.presentationTimeUs, System.nanoTime())\n"
            "                                r5StallLogged.set(false)\n"
            "                                if (framesSent % 150L == 0L) log(\"VIDEO: R5 ${r5CadenceSummary()}\")\n"
            "                            }\n"
            "                            // 转码输出顶替了 CarWith 透传：诊断时间线的帧数 / 字节 / 时间戳照常更新，\n",
            "encoder send success",
        ),
        (
            "                if (!sendPlainFrame(packed, frame.keyFrame, output)) continue\n",
            "                if (!sendPlainFrame(packed, frame.keyFrame, output)) continue\n"
            "                r5Cadence.recordForwardedFrame(frame.timestampUs, System.nanoTime())\n"
            "                r5StallLogged.set(false)\n",
            "passthrough send success",
        ),
        (
            '                    log("VIDEO: 透传码流统计（前 $framesSent 帧）${streamStats.summary()}")\n',
            '                    log("VIDEO: 透传码流统计（前 $framesSent 帧）${streamStats.summary()} R5 ${r5CadenceSummary()}")\n',
            "early report",
        ),
        (
            '                    log("VIDEO: 透传码流统计（第 $framesSent 帧）${streamStats.summary()}")\n',
            '                    log("VIDEO: 透传码流统计（第 $framesSent 帧）${streamStats.summary()} R5 ${r5CadenceSummary()}")\n',
            "periodic report",
        ),
        (
            "                    index == MediaCodec.INFO_TRY_AGAIN_LATER -> {\n"
            "                        maybeSendKeepAlive(output)\n"
            "                        continue\n",
            "                    index == MediaCodec.INFO_TRY_AGAIN_LATER -> {\n"
            "                        maybeSendKeepAlive(output)\n"
            "                        maybeReportR5Stall()\n"
            "                        continue\n",
            "encoder idle monitor",
        ),
        (
            "                if (frame == null) {\n"
            "                    maybeSendKeepAlive(output)\n"
            "                    continue\n",
            "                if (frame == null) {\n"
            "                    maybeSendKeepAlive(output)\n"
            "                    maybeReportR5Stall()\n"
            "                    continue\n",
            "passthrough idle monitor",
        ),
    ]
    for old, new, label in patch:
        src = replace_once(src, old, new, label)
    assert src.count("r5Cadence.recordForwardedFrame(") == 2
    assert src.count("r5Cadence.reset()") == 2
    return src


def apply_ui(base: Path):
    """R6: Apple-inspired contrast/accessibility without changing layout IDs."""
    panel = base / "app/src/main/res/layout/fragment_panel_display.xml"
    settings = base / "app/src/main/res/layout/activity_settings_content.xml"
    main = base / "app/src/main/res/layout/activity_main.xml"
    content = panel.read_text(encoding="utf-8")
    invisible = 'android:textColor="#FFF5F5F7"'
    if content.count(invisible) != 1:
        raise Blocked("light-mode settings label changed")
    content = content.replace(invisible, 'android:textColor="@color/ui_text"')
    content = content.replace('android:textColor="#FF8E8E93"', 'android:textColor="@color/ui_text_secondary"')
    names = re.findall(r'android:id="@\+id/(btn(?:ScreenOff|AutoConnect|HidRaw|PlainFallback|AudioBaseline|Passat)[A-Za-z0-9]+)"', content)
    if len(names) < 10 or len(names) != len(set(names)):
        raise Blocked("settings segmented controls changed")
    for name in names:
        anchor = 'android:id="@+id/' + name + '"'
        content = content.replace(anchor, anchor + '\n            android:minHeight="48dp"', 1)
    panel.write_text(content, encoding="utf-8")
    src = settings.read_text(encoding="utf-8")
    anchor = 'android:layout_width="38dp"\n            android:layout_height="38dp"'
    if src.count(anchor) != 1:
        raise Blocked("settings back button changed")
    settings.write_text(src.replace(anchor, 'android:layout_width="48dp"\n            android:layout_height="48dp"'), encoding="utf-8")
    if not main.is_file():
        raise Blocked("main layout missing")
    print("R6 UI: improved", len(names), "segmented tap targets", flush=True)


def integrate_r7(base: Path, kit: Path):
    """Keep video IDR-rejoin wiring; never evict already queued priority audio events."""
    video = base / "app/src/main/java/com/mcarplay/app/video/VideoSender.kt"
    controller = base / "app/src/main/java/com/mcarplay/app/SessionController.kt"
    audio = base / "app/src/main/java/com/mcarplay/app/audio/CarLifeAudioBridge.kt"
    sender = base / "app/src/main/java/com/mcarplay/app/audio/AudioSender.kt"
    if "if (!sender.submitExternalFrame(frame.toExternalVideoFrame())) output.gate.reset()" not in controller.read_text(encoding="utf-8"):
        raise Blocked("IDR recovery wiring missing")
    text = video.read_text(encoding="utf-8")
    text = replace_once(text,
        "    private val externalQueue = java.util.concurrent.LinkedBlockingQueue<ExternalVideoFrame>(64)",
        "    private val externalQueue = java.util.concurrent.LinkedBlockingQueue<ExternalVideoFrame>(\n"
        "        VideoQueueBudget.capacity(if (receiverMaxFps > 0) minOf(targetFps, receiverMaxFps) else targetFps),\n"
        "    )",
        "video queue budget")
    video.write_text(text, encoding="utf-8")
    text = audio.read_text(encoding="utf-8")
    text = replace_once(text,
        "    private val queue = LinkedBlockingQueue<Pair<CarLifeChannel, CarLifeAudioEvent>>(QUEUE_LIMIT)",
        "    private val queue = PriorityDropQueue<Pair<CarLifeChannel, CarLifeAudioEvent>>(QUEUE_LIMIT) { item ->\n"
        "        item.first == CarLifeChannel.MEDIA && item.second is CarLifeAudioEvent.Pcm\n"
        "    }",
        "audio priority queue")
    text = replace_once(text, "    private var dropped = 0L\n", "", "audio obsolete drop counter")
    text = replace_once(text,
        "        if (!queue.offer(channel to event)) {\n"
        "            queue.poll()\n"
        "            dropped++\n"
        "            queue.offer(channel to event)\n"
        "        }",
        "        if (!queue.offer(channel to event)) {\n"
        "            val count = queue.rejectedTotal\n"
        "            if (count <= 3L || count % 50L == 0L) {\n"
        "                log(\"AUDIO: 控制/导航优先队列已满，新事件拒绝（累计 $count）\")\n"
        "            }\n"
        "        }",
        "audio event overflow")
    text = replace_once(text, "nonzero=${pcm.any { it != 0.toByte() }} dropped=$dropped ",
        "nonzero=${pcm.any { it != 0.toByte() }} evictedMusic=${queue.evictedTotal} rejected=${queue.rejectedTotal} ",
        "audio priority counters")
    audio.write_text(text, encoding="utf-8")
    text = sender.read_text(encoding="utf-8")
    text = replace_once(text,
        "        private const val READ_TIMEOUT_QUIET_MILLIS = 500L",
        "        private const val READ_TIMEOUT_QUIET_MILLIS = 500L\n"
        "        private const val MAX_EXTERNAL_PCM_CHUNK_BYTES = 128 * 1024",
        "audio chunk size limit")
    text = replace_once(text,
        "    private val externalPcm = java.util.concurrent.LinkedBlockingQueue<ByteArray>(64)",
        "    private val externalPcm = java.util.concurrent.LinkedBlockingQueue<ByteArray>(64)\n"
        "    private val externalPcmOverflowDrops = java.util.concurrent.atomic.AtomicLong(0L)\n"
        "    private val externalPcmOversizeDrops = java.util.concurrent.atomic.AtomicLong(0L)",
        "audio PCM drop counters")
    text = replace_once(text,
        "        val copy = pcm.copyOf()\n"
        "        if (!externalPcm.offer(copy)) {\n"
        "            externalPcm.poll()\n"
        "            externalPcm.offer(copy)\n"
        "        }",
        "        if (pcm.size > MAX_EXTERNAL_PCM_CHUNK_BYTES) {\n"
        "            val dropped = externalPcmOversizeDrops.incrementAndGet()\n"
        "            if (dropped <= 3L || dropped % 50L == 0L) log(\"AUDIO: 异常超大 PCM 块 ${pcm.size}B 丢弃 #$dropped\")\n"
        "            return\n"
        "        }\n"
        "        val copy = pcm.copyOf()\n"
        "        if (!externalPcm.offer(copy)) {\n"
        "            if (externalPcm.poll() != null) {\n"
        "                val dropped = externalPcmOverflowDrops.incrementAndGet()\n"
        "                if (dropped <= 3L || dropped % 50L == 0L) log(\"AUDIO: PCM 队列溢出，丢旧块 #$dropped\")\n"
        "            }\n"
        "            if (!externalPcm.offer(copy)) {\n"
        "                val dropped = externalPcmOverflowDrops.incrementAndGet()\n"
        "                if (dropped <= 3L || dropped % 50L == 0L) log(\"AUDIO: PCM 队列仍满，丢新块 #$dropped\")\n"
        "            }\n"
        "        }",
        "audio PCM overflow guards")
    text = replace_once(text,
        '        log("AUDIO: 已停止（共发 $packetsSent 包 / ${bytesSent / 1024}KB）")',
        '        log("AUDIO: 已停止（共发 $packetsSent 包 / ${bytesSent / 1024}KB；" +\n'
        '            "PCM 丢块=${externalPcmOverflowDrops.get()} 超大块=${externalPcmOversizeDrops.get()}）")',
        "audio stop statistics")
    sender.write_text(text, encoding="utf-8")
    for name, dest in [
        ("VideoQueueBudget.kt", "app/src/main/java/com/mcarplay/app/video/VideoQueueBudget.kt"),
        ("VideoQueueBudgetTest.kt", "app/src/test/java/com/mcarplay/app/video/VideoQueueBudgetTest.kt"),
        ("PriorityDropQueue.kt", "app/src/main/java/com/mcarplay/app/audio/PriorityDropQueue.kt"),
        ("PriorityDropQueueTest.kt", "app/src/test/java/com/mcarplay/app/audio/PriorityDropQueueTest.kt"),
    ]:
        destination = base / dest
        if destination.exists():
            raise Blocked("conflicting upstream R7 source " + dest)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(kit / "src" / name, destination)
    print("R7 video/audio backpressure hooks integrated", flush=True)


def main():
    kit = Path(__file__).resolve().parent.parent
    base = Path(os.environ.get("R7_UPSTREAM", "upstream")).resolve()
    out = Path(os.environ.get("R7_OUTPUT", "apk-output")).resolve()
    required = ["gradlew", "settings.gradle.kts", "app/build.gradle.kts", "app/src/main/AndroidManifest.xml"]
    if any(not (base / p).is_file() for p in required):
        raise Blocked("complete Gradle Android upstream project required")
    sha = subprocess.check_output(["git", "-C", str(base), "rev-parse", "HEAD"], text=True).strip()
    if sha != PINNED:
        raise Blocked(f"upstream commit mismatch: {sha}")
    if subprocess.check_output(["git", "-C", str(base), "status", "--porcelain"], text=True).strip():
        raise Blocked("upstream checkout is not clean")
    src = base / SENDER
    if not src.is_file():
        raise Blocked("expected upstream VideoSender missing")
    modified = integrate(src.read_text(encoding="utf-8"))
    if (base / METER).exists() or (base / TEST).exists():
        raise Blocked("upstream has conflicting cadence files")
    sdk = os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT")
    if not sdk or not (Path(sdk) / "platforms/android-35/android.jar").is_file():
        raise Blocked("Android SDK Platform 35 missing")
    if not shutil.which("java"):
        raise Blocked("Java runtime missing")
    src.write_text(modified, encoding="utf-8")
    apply_ui(base)
    integrate_r7(base, kit)
    for relative, name in [(METER, "VideoFrameCadenceMeter.kt"), (TEST, "R6ForwardCadenceTest.kt")]:
        destination = base / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(kit / "src" / name, destination)

    cmd = ["bash", "./gradlew", "--no-daemon", "spotlessApply", "spotlessCheck",
           ":app:testStandardDebugUnitTest", ":app:lintStandardDebug", ":app:assembleStandardDebug"]
    print("+", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=base, check=True)
    apk = base / APK
    if not apk.is_file() or apk.stat().st_size < 10_000 or not zipfile.is_zipfile(apk):
        raise Blocked("Gradle did not create a valid APK")
    with zipfile.ZipFile(apk) as file:
        names = set(file.namelist())
        if not {"AndroidManifest.xml", "classes.dex"}.issubset(names):
            raise Blocked("APK is missing Android manifest or DEX")
        if file.testzip() is not None:
            raise Blocked("APK checksum/ZIP failed")
    out.mkdir(parents=True, exist_ok=True)
    target = out / "mcarplay-LaCrosse-R7-queue-priority-debug.apk"
    if target.exists():
        raise Blocked("APK destination already exists")
    shutil.copy2(apk, target)
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    (out / "SHA256SUMS.txt").write_text(checksum + "  " + target.name + "\n")
    (out / "SCOPE.txt").write_text(
        "DEBUG APK. Pinned upstream at " + PINNED +
        ". R7 R6 cadence/UI plus video budget and protected navigation audio queue. NOT vehicle-tested; NOT certified 60 FPS.\n"
    )
    print("APK CREATED:", target, "SHA256:", checksum, flush=True)


if __name__ == "__main__":
    try:
        main()
    except (Blocked, subprocess.CalledProcessError, OSError, AssertionError) as e:
        sys.exit(f"BLOCKED; NO VERIFIED APK: {e}")
