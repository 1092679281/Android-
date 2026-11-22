#!/usr/bin/env python3
"""R9 guarded one-tap CarWith-to-CarPlay bridge connection on R8."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile
import integrate_and_build_r8 as r8

def change(src, old, new, label):
    return r8.checked(src, old, new, label)

def quick_connect(base: Path, kit: Path) -> None:
    for name, dest in (
        ("QuickConnectPrefs.kt", "app/src/main/java/com/mcarplay/app/bt/QuickConnectPrefs.kt"),
        ("QuickConnectMode.kt", "app/src/main/java/com/mcarplay/app/bt/QuickConnectMode.kt"),
        ("QuickConnectModeTest.kt", "app/src/test/java/com/mcarplay/app/bt/QuickConnectModeTest.kt"),
    ):
        r8.copy_new(kit, base, name, dest)
    main = base / "app/src/main/java/com/mcarplay/app/MainActivity.kt"
    src = main.read_text(encoding="utf-8")
    src = change(src, "import com.mcarplay.app.bt.AutoReconnectGuard\n",
        "import com.mcarplay.app.bt.AutoReconnectGuard\nimport com.mcarplay.app.bt.QuickConnectMode\nimport com.mcarplay.app.bt.QuickConnectPrefs\n", "R9 imports")
    src = change(src, "    private fun showAudioChoiceDialog() {\n",
        "    /** After a deliberate first choice, one tap reuses it. */\n"
        "    private fun startQuickConnection() {\n"
        "        val previous = QuickConnectPrefs.lastAudioEnabled(this)\n"
        "        if (QuickConnectMode.needsFirstTimeChoice(previous)) {\n"
        "            showAudioChoiceDialog()\n"
        "        } else {\n"
        "            beginWithAudio(QuickConnectMode.forAutomatic(previous))\n"
        "        }\n"
        "    }\n\n"
        "    private fun showAudioChoiceDialog() {\n", "first start choice")
    src = change(src,
        "    private fun beginWithAudio(enabled: Boolean) {\n        SessionController.audioEnabledForSession = enabled\n",
        "    private fun beginWithAudio(enabled: Boolean) {\n"
        "        // Only an explicit first choice can establish the initial preference.\n"
        "        QuickConnectPrefs.remember(this, enabled)\n"
        "        SessionController.audioEnabledForSession = enabled\n", "remember mode")
    src = change(src, "                    ensureBluetoothReady { showAudioChoiceDialog() }\n",
        "                    ensureBluetoothReady { startQuickConnection() }\n", "one-tap connect")
    src = change(src, "        // ---- 连接准备 ----\n",
        "        // One long press reopens audio/video selection; no resetting pairing.\n"
        "        ctaButton.setOnLongClickListener {\n"
        "            if (heroState == HeroState.IDLE) {\n"
        "                pendingDetectionTarget = null\n"
        "                ensureBluetoothReady { showAudioChoiceDialog() }\n"
        "            }\n"
        "            true\n"
        "        }\n\n"
        "        // ---- 连接准备 ----\n", "change mode with long press")
    src = change(src,
        "                    } else {\n                        getString(R.string.main_hero_idle_hint)\n                    }\n                styleCta(R.drawable.bg_cta_fill",
        "                    } else {\n"
        "                        QuickConnectPrefs.lastAudioEnabled(this)?.let { lastAudio ->\n"
        "                            getString(\n"
        "                                R.string.ma_quick_connect_hint,\n"
        "                                getString(if (lastAudio) R.string.ma_audio_enable else R.string.ma_audio_video_only),\n"
        "                            )\n"
        "                        } ?: getString(R.string.main_hero_idle_hint)\n"
        "                    }\n                styleCta(R.drawable.bg_cta_fill", "hint")
    main.write_text(src, encoding="utf-8")
    controller = base / "app/src/main/java/com/mcarplay/app/SessionController.kt"
    src = controller.read_text(encoding="utf-8")
    src = change(src,
        "import com.mcarplay.app.bt.AutoConnectPrefs\n",
        "import com.mcarplay.app.bt.AutoConnectPrefs\nimport com.mcarplay.app.bt.QuickConnectMode\nimport com.mcarplay.app.bt.QuickConnectPrefs\n", "auto imports")
    src = change(src,
        "        val alreadyRunning = isSessionRunning()\n        if (!alreadyRunning) {\n",
        "        val alreadyRunning = isSessionRunning()\n"
        "        if (automatic && !alreadyRunning) {\n"
        "            audioEnabledForSession = QuickConnectMode.forAutomatic(QuickConnectPrefs.lastAudioEnabled(context))\n"
        "            audioPreferCompat = false\n"
        "            appendLog(\"AUTO: 已读取快捷连接声音选择（开启=\" + audioEnabledForSession + \")\")\n"
        "        }\n"
        "        if (!alreadyRunning) {\n", "auto-mode on new session")
    controller.write_text(src, encoding="utf-8")
    for lang in ("values", "values-en"):
        file = base / f"app/src/main/res/{lang}/strings_ma.xml"
        src = file.read_text(encoding="utf-8")
        new = ('<string name="ma_quick_connect_hint">快捷连接：%1$s · 点按直连，长按切换声音</string>' if lang == "values"
            else '<string name="ma_quick_connect_hint">Quick connect: %1$s · tap to connect, hold to change audio</string>')
        src = change(src, "</resources>", "    " + new + "\n</resources>", "translation " + lang)
        file.write_text(src, encoding="utf-8")
    print("R9: first explicit audio choice, then one tap / long press / BT auto reuse", flush=True)

def main() -> None:
    kit = Path(__file__).resolve().parent.parent
    output = Path(os.environ.get("R9_OUTPUT", "apk-output-r9")).resolve()
    staging = output.parent / (output.name + "-staging")
    if output.exists() or staging.exists():
        raise r8.r7.Blocked("R9 output/staging exists")
    old = r8.integrate_r8
    def with_r9(base: Path, selected_kit: Path) -> None:
        old(base, selected_kit)
        quick_connect(base, selected_kit)
    r8.integrate_r8 = with_r9
    os.environ["R8_OUTPUT"] = str(staging)
    r8.main()
    if os.environ.get("R19_SOURCE_ONLY") == "1":
        return
    apk = staging / "mcarplay-LaCrosse-R8-ios-latency-touch-debug.apk"
    if not apk.is_file() or not zipfile.is_zipfile(apk):
        raise r8.r7.Blocked("R9 APK missing or invalid")
    output.mkdir(parents=True, exist_ok=False)
    dest = output / "mcarplay-LaCrosse-R9-quick-connect-debug.apk"
    shutil.copy2(apk, dest)
    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(digest + "  " + dest.name + "\n", encoding="utf-8")
    (output / "SCOPE.txt").write_text(
        "R9: remembered audio/video preference, one-tap manual start and BT auto. "
        "Long-press idle Connect to reselect. Original permissions, safety and CarLife/CarPlay "
        "protocol remain intact. On-car UI remains CarWith, not iOS. "
        "Not vehicle-tested; head unit compatibility and 60fps unverified.\n",
        encoding="utf-8",
    )
    shutil.rmtree(staging)
    print("R9 VERIFIED BUILD:", dest, digest, flush=True)

if __name__ == "__main__":
    try:
        main()
    except (r8.r7.Blocked, subprocess.CalledProcessError, OSError, AssertionError, ValueError) as err:
        sys.exit(f"BLOCKED; NO VERIFIED R9 APK: {err}")
