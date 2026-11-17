#!/usr/bin/env python3
"""R18: distinguish saved Bluetooth MAC from immutable active iAP2/ctrl identity."""
from pathlib import Path
import hashlib
import os
import shutil
import sys
import zipfile
import integrate_and_build_r16 as r16


class PatchMismatch(RuntimeError):
    pass


def replace_once(path: Path, old: str, new: str, purpose: str) -> None:
    src = path.read_text(encoding="utf-8")
    count = src.count(old)
    if count != 1:
        raise PatchMismatch(f"{purpose}: expected one anchor in {path}, got {count}")
    path.write_text(src.replace(old, new, 1), encoding="utf-8")


def patch(base: Path, kit: Path) -> None:
    copy = r16.r15.r14.r13.r12.r10.r9.r8.copy_new
    copy(kit, base, "BluetoothIdentitySessionPolicy.kt", "app/src/main/java/com/mcarplay/app/util/BluetoothIdentitySessionPolicy.kt")
    copy(kit, base, "BluetoothIdentitySessionPolicyTest.kt", "app/src/test/java/com/mcarplay/app/util/BluetoothIdentitySessionPolicyTest.kt")

    # Always emit a source-backed Bluetooth identity diagnostic for BOTH the
    # cached and fallback branches, without making a slow Shizuku shell query
    # on the time-critical RFCOMM handshake.
    bt_session = base / "app/src/main/java/com/mcarplay/app/bt/BtSession.kt"
    replace_once(
        bt_session,
        "    val cached = DeviceIdentity.cachedBluetoothMac()\n"
        "    if (cached != null) return cached\n"
        "    val resolved = DeviceIdentity.resolve(context, forceRetry = true)\n",
        "    val resolved = DeviceIdentity.cachedResolution() ?: DeviceIdentity.resolve(context, forceRetry = true)\n",
        "always log cached/manual identity actually used by 0x4300",
    )

    controller = base / "app/src/main/java/com/mcarplay/app/SessionController.kt"
    replace_once(
        controller,
        "import com.mcarplay.app.util.Bg\n",
        "import com.mcarplay.app.util.Bg\n"
        "import com.mcarplay.app.util.DeviceIdentity\n"
        "import com.mcarplay.app.util.BluetoothIdentitySessionPolicy\n",
        "import identity consistency rules",
    )
    replace_once(
        controller,
        "    private var activePeerAddress: String? = null\n",
        "    private var activePeerAddress: String? = null\n"
        "\n    /** Stable BLE identity snapshot at the start of the current attempt. */\n"
        "    @Volatile\n"
        "    private var bluetoothIdentityAtStart: String? = null\n"
        "\n    /** True when a manually saved MAC differs from what the current connection sent. */\n"
        "    fun onBluetoothIdentitySaved(context: Context): Boolean {\n"
        "        val identity = DeviceIdentity.peek(context.applicationContext)\n"
        "        val needsRestart = BluetoothIdentitySessionPolicy.requiresReconnect(bluetoothIdentityAtStart, identity.mac)\n"
        "        if (needsRestart) {\n"
        "            appendLog(\n"
        '                "IDENTITY: 新蓝牙地址已保存，但正在运行的 iAP2 0x4300 / ctrl TXT 仍是本轮启动时的旧值；" +\n'
        '                    "请点击「取消连接」，再重新启动连接。无需卸载应用或清除设置",\n'
        "            )\n"
        "        } else {\n"
        '            appendLog("IDENTITY: 蓝牙地址设置已更新，下一轮连接从保存值重新读取")\n'
        "        }\n"
        "        return needsRestart\n"
        "    }\n",
        "capture session identity and warn when settings differ",
    )
    replace_once(
        controller,
        "        // 后台发布：start() 首次要向 Shizuku 解析真实蓝牙 MAC（shell），不能在主线程做\n",
        "        if (!alreadyRunning) {\n"
        "            // Single source of truth: manual value is read synchronously before\n"
        "            // starting BOTH ctrl advertisement and RFCOMM sessions. Never\n"
        "            // confuse a later green UI badge with an earlier 0x4300 payload.\n"
        "            val identity = DeviceIdentity.peek(context.applicationContext)\n"
        "            bluetoothIdentityAtStart = identity.mac\n"
        '            appendLog("IDENTITY: 本轮启动地址 source=${DeviceIdentity.sourceLabel(identity.source)} " +\n'
        '                "placeholder=${BluetoothIdentitySessionPolicy.sessionUsedPlaceholder(identity.mac)} " +\n'
        '                "（会话开始后修改地址需取消并重连才能更新 0x4300/TXT id）")\n'
        "        }\n"
        "        // 后台发布：start() 首次要向 Shizuku 解析真实蓝牙 MAC（shell），不能在主线程做\n",
        "capture source before async ctrl and BT initialization",
    )
    replace_once(
        controller,
        "        handoffOwnership.blockNewHandoffs()\n        connectCancelled = true\n",
        "        handoffOwnership.blockNewHandoffs()\n"
        "        connectCancelled = true\n"
        "        bluetoothIdentityAtStart = null\n",
        "clear stale connection identity on disconnect",
    )

    activity = base / "app/src/main/java/com/mcarplay/app/MainActivity.kt"
    replace_once(
        activity,
        "                            updateReadyRow()\n"
        "                            // 填好后接着走原来的连接流程；清除或未保存时不自动连接\n",
        "                            updateReadyRow()\n"
        "                            if (SessionController.onBluetoothIdentitySaved(this)) {\n"
        "                                snack(getString(R.string.ma_bt_identity_restart_needed))\n"
        "                            }\n"
        "                            // 填好后接着走原来的连接流程；清除或未保存时不自动连接\n",
        "show identity mismatch after guided entry",
    )
    replace_once(
        activity,
        "            BtIdentityDialog.show(this) { updateReadyRow() }\n",
        "            BtIdentityDialog.show(this) {\n"
        "                updateReadyRow()\n"
        "                if (SessionController.onBluetoothIdentitySaved(this)) {\n"
        "                    snack(getString(R.string.ma_bt_identity_restart_needed))\n"
        "                }\n"
        "            }\n",
        "show identity mismatch after settings-row edit",
    )
    for locale, suffix in (
        ("values", "蓝牙地址已保存；当前连接仍使用旧身份，请取消连接后重新连接"),
        ("values-en", "Bluetooth address saved. Disconnect and reconnect to use it in the current CarPlay handshake."),
    ):
        strings = base / "app/src/main/res" / locale / "strings_sc.xml"
        data = strings.read_text(encoding="utf-8")
        close = "</resources>"
        if data.count(close) != 1:
            raise PatchMismatch(f"cannot append localized restart hint in {strings}")
        strings.write_text(
            data.replace(close, f'    <string name="ma_bt_identity_restart_needed">{suffix}</string>\n{close}'),
            encoding="utf-8",
        )
    print("R18: manual Bluetooth MAC vs active iAP2/ctrl snapshot consistency integrated", flush=True)


def main() -> None:
    output = Path(os.environ.get("R18_OUTPUT", "apk-output-r18")).resolve()
    stage = output.parent / (output.name + "-staging")
    if output.exists() or stage.exists():
        raise PatchMismatch("R18 output already exists")

    previous_patch = r16.patch

    def with_r18(base: Path, kit: Path) -> None:
        previous_patch(base, kit)
        patch(base, kit)

    r16.patch = with_r18
    os.environ["R16_OUTPUT"] = str(stage)
    r16.main()

    previous = stage / "mcarplay-LaCrosse-R16-buick-setup500-diagnostics-debug.apk"
    if not previous.is_file() or not zipfile.is_zipfile(previous):
        raise PatchMismatch("R18 Android test / APK build failed")
    output.mkdir(parents=True, exist_ok=False)
    target = output / "mcarplay-LaCrosse-R18-identity-snapshot-debug.apk"
    shutil.copy2(previous, target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(f"{digest}  {target.name}\n", encoding="utf-8")
    (output / "SCOPE.txt").write_text(
        "R18 layers R16/R15/R14. Verifies MAC snapshot before BT/ctrl start and "
        "warns when manually saved MAC differs from the identity already sent "
        "over 0x4300. No automatic disconnection or reconnect without user "
        "consent; no Apple hardware or Buick firmware emulation. "
        "Debug APK is not a continuously updatable signed release.\n",
        encoding="utf-8",
    )
    shutil.rmtree(stage)
    print("R18 APK:", target, digest, flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        sys.exit("R18 BUILD BLOCKED: " + str(error))
