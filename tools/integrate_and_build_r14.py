#!/usr/bin/env python3
"""R14: guard AirPlay SETUP and RECORD with actual parsed responses and screen TCP."""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
import integrate_and_build_r13 as r13


class PatchMismatch(RuntimeError):
    pass


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    content = path.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise PatchMismatch(f"{label}: expected exactly one match in {path}, found {count}")
    path.write_text(content.replace(old, new, 1), encoding="utf-8")


def patch(base: Path, kit: Path) -> None:
    copy = r13.r12.r10.r9.r8.copy_new
    for name, target in (
        ("AirPlayActivationState.kt", "app/src/main/java/com/mcarplay/app/airplay/AirPlayActivationState.kt"),
        ("AirPlayActivationStateTest.kt", "app/src/test/java/com/mcarplay/app/airplay/AirPlayActivationStateTest.kt"),
    ):
        copy(kit, base, name, target)

    client = base / "app/src/main/java/com/mcarplay/app/airplay/AirPlayClient.kt"
    def c(old: str, new: str, name: str) -> None:
        replace_once(client, old, new, "AirPlayClient " + name)

    c(
        "    @Volatile\n    private var screenStreamUuid: String? = null\n",
        "    @Volatile\n    private var screenStreamUuid: String? = null\n"
        "\n    private val activation = AirPlayActivationState()\n"
        "    @Volatile private var activationGateEnabled = false\n",
        "activation state field",
    )
    c(
        "        sessionSetupAccepted = false\n"
        "        screenStreamUuid = null\n"
        "        // 会话结束前记下 MIB3",
        "        sessionSetupAccepted = false\n"
        "        screenStreamUuid = null\n"
        "        activation.reset()\n"
        "        // 会话结束前记下 MIB3",
        "close discards stale session state",
    )
    c(
        "        modesAckCounts.clear()\n        val deviceId = setupDeviceId()\n",
        "        modesAckCounts.clear()\n"
        "        activation.reset()\n"
        "        sessionSetupAccepted = false\n"
        "        screenStreamUuid = null\n"
        "        recordAccepted = false\n"
        "        val deviceId = setupDeviceId()\n",
        "new setup resets stale session readiness",
    )
    c(
        '        if (!statusLine.contains("200")) {\n            log("AIRPLAY: SETUP 应答 [$statusLine]（自报 deviceID=$deviceId）")',
        '        if (!AirPlayRtspStatus.accepted(statusLine)) {\n            log("AIRPLAY: SETUP 应答 [$statusLine]（自报 deviceID=$deviceId）")',
        "initial RTSP response exact code",
    )
    c(
        "        sessionSetupAccepted = true\n"
        "        milestone(ConnectionMilestone.SESSION_SETUP)\n"
        "        val root =\n",
        "        // A 200 without a parseable SETUP plist must NOT count as session activation.\n"
        "        val root =\n",
        "do not mark malformed response as successful",
    )
    c(
        '        log(\n            "AIRPLAY: ✓ SETUP 完成 eventPort=${info.eventPort}',
        '        sessionSetupAccepted = true\n'
        '        activation.sessionSetupAccepted()\n'
        '        milestone(ConnectionMilestone.SESSION_SETUP)\n'
        '        log(\n            "AIRPLAY: ✓ SETUP 完成 eventPort=${info.eventPort}',
        "milestone after validated session response",
    )
    c(
        "    ): ScreenStreamInfo? {\n"
        "        // 对照 catplay（真车验证）：streamConnectionID = 随机 u64（+1 保证非零）\n",
        "    ): ScreenStreamInfo? {\n"
        "        if (activationGateEnabled && (!sessionSetupAccepted || !activation.canSetupScreen())) {\n"
        '            log("AIRPLAY: 初始 SETUP 尚未确认——拒绝提前发送屏幕流 SETUP")\n'
        "            return null\n"
        "        }\n"
        "        // 对照 catplay（真车验证）：streamConnectionID = 随机 u64（+1 保证非零）\n",
        "screen SETUP ordered after session SETUP",
    )
    c(
        '        if (!statusLine.contains("200")) {\n'
        '            log(\n                "AIRPLAY: 流协商应答 [$statusLine]',
        '        if (!AirPlayRtspStatus.accepted(statusLine)) {\n'
        '            log(\n                "AIRPLAY: 流协商应答 [$statusLine]',
        "screen stream SETUP exact status",
    )
    c(
        "        if (screen == null || dataPort == 0) {\n",
        "        if (screen == null || dataPort !in 1..65535) {\n",
        "screen dataPort valid range",
    )
    c(
        "        screenStreamUuid = streamUuid\n"
        "        return ScreenStreamInfo(connectionId, dataPort, cipher)\n",
        "        screenStreamUuid = streamUuid\n"
        "        if (activationGateEnabled && !activation.screenSetupAccepted()) {\n"
        '            log("AIRPLAY: 屏幕流 SETUP 时序冲突——拒绝后续 RECORD")\n'
        "            return null\n"
        "        }\n"
        "        return ScreenStreamInfo(connectionId, dataPort, cipher)\n",
        "screen setup stage after valid endpoint",
    )
    c(
        "        if (success && screenStreamUuid == uuid) screenStreamUuid = null\n"
        "        return success\n",
        "        if (success && screenStreamUuid == uuid) {\n"
        "            screenStreamUuid = null\n"
        "            recordAccepted = false\n"
        "            activation.screenTornDown()\n"
        "        }\n"
        "        return success\n",
        "force RECORD needs fresh video port after screen teardown",
    )
    c(
        "        if (sessionStopped) sessionSetupAccepted = false\n",
        "        if (sessionStopped) {\n"
        "            sessionSetupAccepted = false\n"
        "            recordAccepted = false\n"
        "            activation.reset()\n"
        "        }\n",
        "teardown resets activation",
    )
    c(
        "    fun record(\n        timeoutMillis: Int = 10_000,\n",
        "    /** Activate strict SETUP/RECORD gating for the real SessionController pipeline. */\n"
        "    fun enableActivationGate() {\n"
        "        activationGateEnabled = true\n"
        "        activation.reset()\n"
        "    }\n\n"
        "    /** Called only when VideoSender.openDataPort() actually succeeded for THIS screen stream. */\n"
        "    fun confirmVideoDataPortConnected(): Boolean {\n"
        "        val confirmed = synchronized(this) {\n"
        "            !sessionStopping && socket?.isClosed == false && sessionSetupAccepted &&\n"
        "                screenStreamUuid != null && activation.videoDataConnected()\n"
        "        }\n"
        '        log("AIRPLAY: 视频 TCP dataPort ${if (confirmed) "已连通，可进入 RECORD" else "未确认，不得 RECORD"}")\n'
        "        return confirmed\n"
        "    }\n\n"
        "    fun record(\n        timeoutMillis: Int = 10_000,\n",
        "callback for verified data port connection",
    )
    c(
        "            if (sessionStopping || socket?.isClosed != false) return false\n"
        "            epoch = connectionEpoch\n",
        "            if (sessionStopping || socket?.isClosed != false ||\n"
        "                (activationGateEnabled && (!sessionSetupAccepted ||\n"
        "                    screenStreamUuid == null || !activation.canRecord()))\n"
        "            ) {\n"
        '                log("AIRPLAY: RECORD 被阻止：初始 SETUP / 屏幕流 SETUP / 视频 TCP 连接尚未全部确认")\n'
        "                return false\n"
        "            }\n"
        "            epoch = connectionEpoch\n",
        "no RECORD without two setups and TCP data port",
    )
    c(
        '                    if (statusLine.contains("200") && connectionEpoch == epoch && !sessionStopping) {\n'
        "                        recordAccepted = true\n",
        "                    if (AirPlayRtspStatus.accepted(statusLine) && connectionEpoch == epoch && !sessionStopping &&\n"
        "                        (!activationGateEnabled || activation.onRecordReply(statusLine, true))\n"
        "                    ) {\n"
        "                        recordAccepted = true\n",
        "record requires exact RTSP 200 plus live epoch",
    )

    controller = base / "app/src/main/java/com/mcarplay/app/SessionController.kt"
    replace_once(
        controller,
        "                        ).also { created ->\n"
        "                            created.onMilestone = { reached, detail ->\n",
        "                        ).also { created ->\n"
        "                            created.enableActivationGate()\n"
        "                            created.onMilestone = { reached, detail ->\n",
        "strict activation on the production AirPlay client, preserving protocol-level test harness",
    )
    source = controller.read_text(encoding="utf-8")
    tunnel_start = "                                // iAP 隧道（type-130）：车机→手机的 iAP2 EA 数据（触摸 HID 载体）。\n"
    tunnel_end = "                                // 关键时序（2026-10-17 奥迪定谳）：屏幕 SETUP 后必须尽快连上\n"
    if source.count(tunnel_start) != 1 or source.count(tunnel_end) != 1:
        raise PatchMismatch("SessionController iAP tunnel original block missing")
    block = source[source.index(tunnel_start):source.index(tunnel_end)]
    if "client.runIapTunnel(sessionKey)" not in block or "tunnel?.onIapMessage" not in block:
        raise PatchMismatch("SessionController unexpected tunnel block")
    replace_once(controller, block, "", "move optional iAP tunnel AFTER video TCP connection")
    replace_once(
        controller,
        "                                    videoSender?.openDataPort()\n"
        "                                    screenStreamRecovery = recover@{\n",
        "                                    // The TCP connect is an essential precondition, not a best-effort side effect.\n"
        "                                    if (!sessionVideoSender.openDataPort() || !client.confirmVideoDataPortConnected()) {\n"
        '                                        appendLog("AIRPLAY: 主屏 SETUP 已被接受，但视频 dataPort 未连通——不发送 RECORD")\n'
        "                                        ConnectionDiagnostics.timeline.finish(diagnosticAttempt, DiagnosticCode.SETUP_FAILED, true)\n"
        "                                        sessionVideoSender.stop()\n"
        "                                        if (ownsConnection() && currentClient === client) retireSession() else client.close()\n"
        "                                        return@run\n"
        "                                    }\n"
        "                                    screenStreamRecovery = recover@{\n",
        "record must be blocked if video TCP failed",
    )
    replace_once(
        controller,
        "                                            if (!replacement.openDataPort() ||\n"
        "                                                wasCancelled() ||\n",
        "                                            if (!replacement.openDataPort() ||\n"
        "                                                !client.confirmVideoDataPortConnected() ||\n"
        "                                                wasCancelled() ||\n",
        "screen restore requires fresh TCP confirmation before forced RECORD",
    )
    # Keep the old tunnel setup timing relative to RECORD, but place it AFTER
    # connecting video TCP. This shortens screen-SETUP-to-dataPort latency.
    relocated = "".join("    " + line if line.strip() else line for line in block.splitlines(keepends=True))
    replace_once(
        controller,
        "                                // 先 RECORD 激活会话并起视频，再协商音频（2026-10-17 奥迪定谳）：\n",
        "                                // Optional iAP tunnel must never hold up the mandatory video TCP connect.\n"
        + relocated
        + "                                // 先 RECORD 激活会话并起视频，再协商音频（2026-10-17 奥迪定谳）：\n",
        "run optional iAP tunnel after video TCP but before RECORD",
    )
    # Exercise the real AirPlayClient strict gate over the upstream loopback RTSP peer,
    # not just the pure policy enum. No new test-only network transport is introduced.
    record_test = base / "app/src/test/java/com/mcarplay/app/airplay/AirPlayRecordLifecycleTest.kt"
    replace_once(
        record_test,
        "    @Test\n    fun observedCheryStackSendsOnlyOneRecordPerSession() {\n",
        "    @Test\n"
        "    fun productionActivationGateRefusesPrematureRecordOnLiveRtspSocket() {\n"
        "        Peer().use { peer ->\n"
        "            val client = client(peer.port)\n"
        "            try {\n"
        "                client.enableActivationGate()\n"
        "                assertTrue(client.reconnect())\n"
        "                assertFalse(client.record())\n"
        "                assertNull(peer.next(300)) // RECORD must not reach the receiver\n"
        "            } finally {\n"
        "                client.close()\n"
        "            }\n"
        "        }\n"
        "    }\n\n"
        "    @Test\n    fun observedCheryStackSendsOnlyOneRecordPerSession() {\n",
        "strict client gate rejects RECORD before SETUP without wire activity",
    )

    print("R14: session/stream SETUP, data TCP and RECORD evidence gates integrated", flush=True)


def main() -> None:
    kit = Path(__file__).resolve().parent.parent
    output = Path(os.environ.get("R14_OUTPUT", "apk-output-r14")).resolve()
    stage = output.parent / (output.name + "-staging")
    if output.exists() or stage.exists():
        raise PatchMismatch("R14 output already exists")
    original = r13.patch

    def with_r14(base: Path, patchkit: Path) -> None:
        original(base, patchkit)
        patch(base, patchkit)

    r13.patch = with_r14
    os.environ["R13_OUTPUT"] = str(stage)
    r13.main()
    if os.environ.get("R19_SOURCE_ONLY") == "1":
        return
    previous = stage / "mcarplay-LaCrosse-R13-handshake-state-debug.apk"
    if not previous.is_file() or not zipfile.is_zipfile(previous):
        raise PatchMismatch("R14 APK did not build")
    output.mkdir(parents=True, exist_ok=False)
    target = output / "mcarplay-LaCrosse-R14-airplay-setup-record-debug.apk"
    shutil.copy2(previous, target)
    sha = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(sha + "  " + target.name + "\n", encoding="utf-8")
    (output / "SCOPE.txt").write_text(
        "R14 retains R12-R13 and pinned upstream. Initial SETUP only succeeds on a parsed "
        "200 response; video stream SETUP requires valid TCP dataPort; RECORD is gated on "
        "successful video data socket connection and exact RTSP 200. Optional iAP tunnel "
        "moved after data TCP connection. APK build does NOT demonstrate real-car playback.\n",
        encoding="utf-8",
    )
    shutil.rmtree(stage)
    print("R14 built:", target, sha, flush=True)


if __name__ == "__main__":
    try:
        main()
    except (PatchMismatch, r13.PatchMismatch, r13.r12.r10.r9.r8.r7.Blocked,
            subprocess.CalledProcessError, OSError, AssertionError, ValueError) as exc:
        sys.exit("R14 BUILD BLOCKED: " + str(exc))
