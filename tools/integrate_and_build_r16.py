#!/usr/bin/env python3
"""R16: diagnose real GM E2LB SETUP 500 and wait for a fresh receiver invite before retrying."""
from pathlib import Path
import hashlib
import os
import shutil
import sys
import zipfile
import integrate_and_build_r15 as r15


class PatchMismatch(RuntimeError):
    pass


def replace_once(path: Path, old: str, new: str, name: str) -> None:
    data = path.read_text(encoding="utf-8")
    n = data.count(old)
    if n != 1:
        raise PatchMismatch(f"{name}: expected one anchor in {path}, found {n}")
    path.write_text(data.replace(old, new, 1), encoding="utf-8")


def patch(base: Path, kit: Path) -> None:
    copy = r15.r14.r13.r12.r10.r9.r8.copy_new
    copy(kit, base, "InitialSetupRecoveryPolicy.kt",
         "app/src/main/java/com/mcarplay/app/airplay/InitialSetupRecoveryPolicy.kt")
    copy(kit, base, "InitialSetupRecoveryPolicyTest.kt",
         "app/src/test/java/com/mcarplay/app/airplay/InitialSetupRecoveryPolicyTest.kt")

    client = base / "app/src/main/java/com/mcarplay/app/airplay/AirPlayClient.kt"
    replace_once(
        client,
        "    private val activation = AirPlayActivationState()\n",
        "    private val activation = AirPlayActivationState()\n"
        "\n    /** Exact initial SETUP response code; null for transport failures or no attempt. */\n"
        "    @Volatile\n"
        "    var lastInitialSetupStatusCode: Int? = null\n"
        "        private set\n"
        "\n    /** Identity observation only; no device identifier or private bytes are logged. */\n"
        "    @Volatile\n"
        "    var lastInitialSetupUsedPlaceholderId: Boolean = false\n"
        "        private set\n",
        "R16 initial SETUP failure evidence fields",
    )
    replace_once(
        client,
        "        val deviceId = setupDeviceId()\n"
        "        val policy = receiverCompatibility()\n",
        "        val deviceId = setupDeviceId()\n"
        "        lastInitialSetupStatusCode = null\n"
        "        lastInitialSetupUsedPlaceholderId = deviceId == DeviceIdentity.PLACEHOLDER_MAC\n"
        "        val policy = receiverCompatibility()\n",
        "R16 reset per-attempt setup evidence",
    )
    replace_once(
        client,
        '        if (!AirPlayRtspStatus.accepted(statusLine)) {\n'
        '            log("AIRPLAY: SETUP 应答 [$statusLine]（自报 deviceID=$deviceId）")\n',
        '        lastInitialSetupStatusCode = AirPlayRtspStatus.code(statusLine)\n'
        '        if (!AirPlayRtspStatus.accepted(statusLine)) {\n'
        '            log("AIRPLAY: SETUP 应答 [$statusLine]（自报 deviceID=$deviceId）")\n'
        '            if (lastInitialSetupStatusCode == 500) {\n'
        '                log(\n'
        '                    "AIRPLAY: SETUP500 诊断：bodyBytes=${responseBody.size} " +\n'
        '                        "gatewayEndpoint=${endpoint.portIsFallback} " +\n'
        '                        "placeholderBluetoothId=$lastInitialSetupUsedPlaceholderId " +\n'
        '                        "ctrl/0x4301 信号请对照上一阶段日志；此错误是接收端拒绝，不能当作会话已激活",\n'
        '                )\n'
        '                if (lastInitialSetupUsedPlaceholderId) {\n'
        '                    log("AIRPLAY: 本机蓝牙 MAC 未取得：请通过 Shizuku 或设置页手动填写真实地址再测试；不能断定 500 仅由此造成")\n'
        '                }\n'
        '            }\n',
        "R16 log bounded evidence on RTSP500, no unsolicited auto success",
    )

    controller = base / "app/src/main/java/com/mcarplay/app/SessionController.kt"
    replace_once(
        controller,
        "                        } else {\n"
        "                            // 会话级 SETUP 被拒（典型：接收端按设备过滤回 403，见\n",
        "                        } else {\n"
        "                            val recovery = com.mcarplay.app.airplay.InitialSetupRecoveryPolicy.afterRejectedSetup(\n"
        "                                statusCode = client.lastInitialSetupStatusCode,\n"
        "                                gatewayPortWasGuessed = client.currentEndpoint.portIsFallback,\n"
        "                                ctrlInvitesObserved = ctrlAdvertiser?.inviteCount ?: 0,\n"
        "                            )\n"
        "                            if (recovery == com.mcarplay.app.airplay.InitialSetupRecoveryAction.WAIT_FOR_FRESH_CTRL_INVITE) {\n"
        "                                appendLog(\n"
        '                                    "AIRPLAY: SETUP 500（无 0x4301、无 mDNS，且网关:7000 是猜测端点）——" +\n'
        '                                        "不会在这条无邀请连接上盲目重发 SETUP；只在车机发出新 ctrl 邀请时有限重试",\n'
        "                                )\n"
        "                                scheduleInviteRetry(endpoint, \"SETUP 500/等待正式车机邀请\")\n"
        "                            }\n"
        "                            // 会话级 SETUP 被拒（典型：接收端按设备过滤回 403，见\n",
        "R16 retry only after fresh receiver invite on guessed endpoint",
    )
    print("R16: exact SETUP500 and placeholder ID evidence, invitation-bounded retry installed", flush=True)


def main() -> None:
    output = Path(os.environ.get("R16_OUTPUT", "apk-output-r16")).resolve()
    stage = output.parent / (output.name + "-staging")
    if output.exists() or stage.exists():
        raise PatchMismatch("R16 output already exists")
    original = r15.patch

    def with_r16(base: Path, kit: Path) -> None:
        original(base, kit)
        patch(base, kit)

    r15.patch = with_r16
    os.environ["R15_OUTPUT"] = str(stage)
    r15.main()
    previous = stage / "mcarplay-LaCrosse-R15-online-update-debug.apk"
    if not previous.is_file() or not zipfile.is_zipfile(previous):
        raise PatchMismatch("R16 build failed to produce a valid staged APK")

    output.mkdir(parents=True, exist_ok=False)
    target = output / "mcarplay-LaCrosse-R16-buick-setup500-diagnostics-debug.apk"
    shutil.copy2(previous, target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(f"{digest}  {target.name}\n", encoding="utf-8")
    (output / "SCOPE.txt").write_text(
        "R16 retains R15 in-app update code and R14 SETUP/RECORD gating. "
        "It diagnoses actual RTSP 500, placeholder Bluetooth deviceID, "
        "and guessed AirPlay gateway endpoint. A new ctrl invitation can "
        "trigger a bounded retry. Does not claim vehicle acceptance or bypass "
        "MFi validation. The R16 debug APK is NOT a signed OTA release.\n",
        encoding="utf-8",
    )
    shutil.rmtree(stage)
    print("R16 debug APK:", target, digest, flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        sys.exit("R16 BUILD BLOCKED: " + str(error))
