#!/usr/bin/env python3
"""R8 guarded integration: bounded audio delay, video queue dwell, touch release and iOS grouping.

Builds the exact pinned upstream through the previously validated R7 pipeline.
An Android build is NOT evidence of head-unit display FPS or end-to-end A/V latency.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

import integrate_and_build_r7 as r7

ANDROID = "{http://schemas.android.com/apk/res/android}"
ET.register_namespace("android", "http://schemas.android.com/apk/res/android")
ET.register_namespace("app", "http://schemas.android.com/apk/res-auto")
ET.register_namespace("tools", "http://schemas.android.com/tools")


def checked(old: str, needle: str, replacement: str, label: str) -> str:
    return r7.replace_once(old, needle, replacement, "R8 " + label)


def copy_new(kit: Path, base: Path, name: str, dest: str) -> None:
    source = kit / "src" / name
    target = base / dest
    if not source.is_file() or target.exists():
        raise r7.Blocked("R8 source missing or conflicting: " + name)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def improve_audio(base: Path, kit: Path) -> None:
    sender = base / "app/src/main/java/com/mcarplay/app/audio/AudioSender.kt"
    data = sender.read_text(encoding="utf-8")
    data = checked(
        data,
        "    private val externalPcm = java.util.concurrent.LinkedBlockingQueue<ByteArray>(64)",
        "    private val externalPcm = PcmLatencyQueue(sampleRate, budgetMs = 120)",
        "millisecond budget queue",
    )
    start_marker = "        val copy = pcm.copyOf()\n"
    end_marker = "\n    }\n\n    fun stopExternalSource()"
    if data.count(start_marker) != 1 or data.count(end_marker) != 1:
        raise r7.Blocked("R8 PCM submit shape changed")
    start = data.index(start_marker)
    end = data.index(end_marker, start)
    snippet = data[start:end]
    if snippet.count("externalPcm.offer(copy)") != 2 or "externalPcm.poll()" not in snippet:
        raise r7.Blocked("R8 existing overflow handling no longer matches R7")
    data = (
        data[:start]
        + "        val discarded = externalPcm.offer(pcm)\n"
        + "        if (discarded > 0) {\n"
        + "            val total = externalPcmOverflowDrops.addAndGet(discarded.toLong())\n"
        + "            if (total <= 3L || total % 50L == 0L) {\n"
        + '                log("AUDIO: PCM 时长预算 120ms，丢弃旧缓存 $discarded 块（累计 $total）")\n'
        + "            }\n"
        + "        }"
        + data[end:]
    )
    data = checked(
        data,
        '"PCM 丢块=${externalPcmOverflowDrops.get()} 超大块=${externalPcmOversizeDrops.get()}）"',
        '"PCM 丢块=${externalPcmOverflowDrops.get()} 超大块=${externalPcmOversizeDrops.get()} " +\n'
        '            "最长发送排队=${externalPcm.maxQueueAgeMs}ms（不含车机缓存））"',
        "PCM queue age diagnostics",
    )
    sender.write_text(data, encoding="utf-8")
    copy_new(kit, base, "PcmLatencyQueue.kt", "app/src/main/java/com/mcarplay/app/audio/PcmLatencyQueue.kt")
    copy_new(kit, base, "PcmLatencyQueueTest.kt", "app/src/test/java/com/mcarplay/app/audio/PcmLatencyQueueTest.kt")
    copy_new(kit, base, "PriorityDropQueueR8Test.kt", "app/src/test/java/com/mcarplay/app/audio/PriorityDropQueueR8Test.kt")
    # This file was copied by the R7 integration; replace it with its R8 reviewed revision.
    updated = base / "app/src/main/java/com/mcarplay/app/audio/PriorityDropQueue.kt"
    original = updated.read_text(encoding="utf-8")
    if "LinkedBlockingQueue" not in original or "firstOrNull(disposable)" not in original:
        raise r7.Blocked("R8 queue upgrade cannot match previous version")
    updated.write_text((kit / "src/PriorityDropQueue.kt").read_text(encoding="utf-8"), encoding="utf-8")


def improve_video(base: Path, kit: Path) -> None:
    path = base / "app/src/main/java/com/mcarplay/app/video/VideoSender.kt"
    data = path.read_text(encoding="utf-8")
    data = checked(
        data,
        "    private val externalQueue = java.util.concurrent.LinkedBlockingQueue<ExternalVideoFrame>(\n",
        "    private data class R8QueuedFrame(val frame: ExternalVideoFrame, val queuedAtNs: Long)\n"
        "    private val r8QueueDelay = VideoQueueDelayMeter()\n"
        "    private val externalQueue = java.util.concurrent.LinkedBlockingQueue<R8QueuedFrame>(\n",
        "sender queue timestamp",
    )
    data = checked(
        data,
        "            externalQueue.offer(frame).also { accepted ->",
        "            externalQueue.offer(R8QueuedFrame(frame, System.nanoTime())).also { accepted ->",
        "enqueue timestamp",
    )
    data = checked(
        data,
        "                val frame = externalQueue.poll(250, java.util.concurrent.TimeUnit.MILLISECONDS)",
        "                val queued = externalQueue.poll(250, java.util.concurrent.TimeUnit.MILLISECONDS)\n"
        "                val frame = queued?.frame\n"
        "                if (queued != null) r8QueueDelay.record(queued.queuedAtNs, System.nanoTime())",
        "sender dequeue age",
    )
    data = checked(
        data,
        '"ptsRegressions=${s.nonMonotonicPts} stalled=${s.stalled}"',
        '"ptsRegressions=${s.nonMonotonicPts} stalled=${s.stalled} senderQueueP95Ms=${r8QueueDelay.p95Ms()}"',
        "honest sender-only diagnostics",
    )
    if data.count("                r5Cadence.reset()\n") != 2:
        raise r7.Blocked("R8 reset transitions changed")
    data = data.replace(
        "                r5Cadence.reset()\n",
        "                r5Cadence.reset()\n                r8QueueDelay.reset()\n",
    )
    path.write_text(data, encoding="utf-8")
    copy_new(kit, base, "VideoQueueDelayMeter.kt", "app/src/main/java/com/mcarplay/app/video/VideoQueueDelayMeter.kt")
    copy_new(kit, base, "VideoQueueDelayMeterTest.kt", "app/src/test/java/com/mcarplay/app/video/VideoQueueDelayMeterTest.kt")


def improve_touch(base: Path, kit: Path) -> None:
    path = base / "app/src/main/java/com/mcarplay/app/carlife/CarLifeTouch.kt"
    data = path.read_text(encoding="utf-8")
    data = checked(
        data,
        "    targetHeight: Int,\n): Pair<Int, Int>? {",
        "    targetHeight: Int,\n    allowOutside: Boolean = true,\n): Pair<Int, Int>? {",
        "release input parameter",
    )
    data = checked(
        data,
        "    val mappedX = (x.toLong() * targetWidth / sourceWidth).toInt().coerceIn(0, targetWidth - 1)",
        "    // Reject invalid DOWN/MOVE; allow a clamped UP so an out-of-bounds\n"
        "    // release still closes the gesture on the receiving head unit.\n"
        "    if (!allowOutside && (x !in 0 until sourceWidth || y !in 0 until sourceHeight)) return null\n"
        "    val mappedX = (x.toLong() * targetWidth / sourceWidth).toInt().coerceIn(0, targetWidth - 1)",
        "out-of-bounds touch guard",
    )
    path.write_text(data, encoding="utf-8")
    session = base / "app/src/main/java/com/mcarplay/app/SessionController.kt"
    data = session.read_text(encoding="utf-8")
    data = checked(
        data,
        "                                                        targetHeight = carLife.videoHeight,\n",
        "                                                        targetHeight = carLife.videoHeight,\n"
        "                                                        allowOutside = !contact.down,\n",
        "retain touch release event",
    )
    session.write_text(data, encoding="utf-8")
    copy_new(kit, base, "TouchMappingR8Test.kt", "app/src/test/java/com/mcarplay/app/carlife/TouchMappingR8Test.kt")


def verify_same_ids(before: str, after: str, label: str) -> None:
    import re
    pattern = r'android:id="@\+id/([A-Za-z0-9_]+)"'
    ids_before = re.findall(pattern, before)
    ids_after = re.findall(pattern, after)
    if sorted(ids_before) != sorted(ids_after):
        raise r7.Blocked("R8 layout IDs changed: " + label)


def ios_settings(base: Path) -> None:
    panel = base / "app/src/main/res/layout/fragment_panel_display.xml"
    original = panel.read_text(encoding="utf-8")
    root = ET.fromstring(original)
    column = root.find("LinearLayout")
    if column is None or len(column) != 28:
        raise r7.Blocked("R8 settings expected intro and 9 three-part controls")
    children = list(column)
    if not all(x.tag in ("TextView", "LinearLayout") for x in children):
        raise r7.Blocked("R8 unexpected settings controls")
    for child in children:
        column.remove(child)
    root.set(ANDROID + "background", "@color/ui_bg")
    column.set(ANDROID + "paddingLeft", "16dp")
    column.set(ANDROID + "paddingRight", "16dp")
    column.set(ANDROID + "paddingTop", "12dp")
    column.set(ANDROID + "paddingBottom", "24dp")
    intro = children[0]
    intro.set(ANDROID + "textSize", "14sp")
    intro.set(ANDROID + "layout_marginBottom", "18dp")
    column.append(intro)
    for start in range(1, len(children), 3):
        heading, body, note = children[start:start+3]
        if heading.tag != "TextView" or note.tag != "TextView":
            raise r7.Blocked("R8 unexpected settings group shape")
        card = ET.Element("LinearLayout", {
            ANDROID + "layout_width": "match_parent",
            ANDROID + "layout_height": "wrap_content",
            ANDROID + "layout_marginBottom": "12dp",
            ANDROID + "background": "@drawable/ui_bg_card",
            ANDROID + "orientation": "vertical",
            ANDROID + "padding": "16dp",
        })
        heading.set(ANDROID + "layout_marginTop", "0dp")
        heading.set(ANDROID + "textSize", "16sp")
        heading.set(ANDROID + "textStyle", "bold")
        heading.set(ANDROID + "textColor", "@color/ui_text")
        note.set(ANDROID + "textSize", "13sp")
        note.set(ANDROID + "textColor", "@color/ui_text_secondary")
        card.append(heading)
        if any(n.get(ANDROID + "id") == "@+id/btnPassat0" for n in body.iter()):
            horizontal = ET.Element("HorizontalScrollView", {
                ANDROID + "layout_width": "match_parent",
                ANDROID + "layout_height": "wrap_content",
                ANDROID + "fillViewport": "false",
                ANDROID + "scrollbars": "none",
            })
            horizontal.append(body)
            card.append(horizontal)
        else:
            card.append(body)
        card.append(note)
        column.append(card)
    output = ET.tostring(root, encoding="unicode", xml_declaration=False)
    verify_same_ids(original, output, "settings panel")
    panel.write_text('<?xml version="1.0" encoding="utf-8"?>\n' + output + '\n', encoding="utf-8")

    header = base / "app/src/main/res/layout/activity_settings_content.xml"
    original = header.read_text(encoding="utf-8")
    data = checked(original, 'android:textSize="18sp"', 'android:textSize="24sp"', "settings page title")
    header.write_text(data, encoding="utf-8")

    main = base / "app/src/main/res/layout/activity_main.xml"
    original = main.read_text(encoding="utf-8")
    data = checked(original, 'android:background="@color/m3_surface"', 'android:background="@color/ui_bg"', "home page background")
    data = checked(data, 'android:textSize="21sp"', 'android:textSize="26sp"', "large page heading")
    data = checked(data, 'android:layout_height="30dp"\n                    android:background="@drawable/bg_chip"',
                   'android:layout_height="40dp"\n                    android:minHeight="40dp"\n                    android:background="@drawable/bg_chip"',
                   "connection chip touch size")
    verify_same_ids(original, data, "home screen")
    main.write_text(data, encoding="utf-8")

    for lang in ("values", "values-en"):
        p = base / f"app/src/main/res/{lang}/strings_ma.xml"
        src = p.read_text(encoding="utf-8")
        if lang == "values":
            src = checked(src,
                '<string name="ma_hero_stats">分辨率 %1$d%% · %2$d/%3$d fps</string>',
                '<string name="ma_hero_stats">缩放 %1$d%% · 发送 %2$d/%3$d fps</string>',
                "Chinese sender fps terminology")
        else:
            src = checked(src,
                '<string name="ma_hero_stats">Resolution %1$d%% · %2$d/%3$d fps</string>',
                '<string name="ma_hero_stats">Scale %1$d%% · sent %2$d/%3$d fps</string>',
                "English sender fps terminology")
        p.write_text(src, encoding="utf-8")
    print("R8 iOS settings: 9 grouped cards, scrollable 4-way control, large header", flush=True)


def integrate_r8(base: Path, kit: Path) -> None:
    improve_audio(base, kit)
    improve_video(base, kit)
    improve_touch(base, kit)
    ios_settings(base)
    print("R8 latency/touch/video/UI guards integrated", flush=True)


def main() -> None:
    kit = Path(__file__).resolve().parent.parent
    output = Path(os.environ.get("R8_OUTPUT", "apk-output-r8")).resolve()
    staging = output.parent / (output.name + "-staging")
    if output.exists() or staging.exists():
        raise r7.Blocked("R8 output/staging already exists; no overwrite permitted")
    original = r7.integrate_r7

    def integrate_after_r7(base: Path, selected_kit: Path) -> None:
        original(base, selected_kit)
        integrate_r8(base, selected_kit)

    r7.integrate_r7 = integrate_after_r7
    os.environ["R7_OUTPUT"] = str(staging)
    r7.main()
    built = staging / "mcarplay-LaCrosse-R7-queue-priority-debug.apk"
    if not built.is_file() or not zipfile.is_zipfile(built):
        raise r7.Blocked("R8 compiled artifact missing")
    output.mkdir(parents=True, exist_ok=False)
    dest = output / "mcarplay-LaCrosse-R8-ios-latency-touch-debug.apk"
    shutil.copy2(built, dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(digest + "  " + dest.name + "\n", encoding="utf-8")
    (output / "SCOPE.txt").write_text(
        "R8 debug APK from pinned upstream " + r7.PINNED + "\n"
        "iOS-style grouped settings, sender audio buffer <=120ms queued PCM, protected prompt FIFO, "
        "sender video queue p95 dwell diagnostics, strict touch DOWN and clamped UP.\n"
        "Sender metrics are NOT head-unit displayed FPS. Audio queue time is NOT measured end-to-end latency. "
        "NOT vehicle-tested, display screenshots NOT verified, 60fps NOT guaranteed.\n",
        encoding="utf-8",
    )
    shutil.rmtree(staging)
    print("R8 VERIFIED BUILD:", dest, digest, flush=True)


if __name__ == "__main__":
    try:
        main()
    except (r7.Blocked, subprocess.CalledProcessError, OSError, AssertionError, ValueError, ET.ParseError) as err:
        sys.exit(f"BLOCKED; NO VERIFIED R8 APK: {err}")
