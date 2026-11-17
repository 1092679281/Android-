#!/usr/bin/env python3
"""R13: evidence-driven CarPlay bring-up, explicit MFi outcomes and endpoint gating.

Applies AFTER R12; retains the pinned upstream CarWith, video and audio pipeline.
"""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
import integrate_and_build_r12 as r12


class PatchMismatch(RuntimeError):
    pass


def replace_once(path: Path, old: str, new: str, label: str) -> None:
    content = path.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise PatchMismatch(f"{label}: expected one anchor in {path}, found {count}")
    path.write_text(content.replace(old, new, 1), encoding="utf-8")


def patch(base: Path, kit: Path) -> None:
    copy = r12.r10.r9.r8.copy_new
    for source, destination in (
        ("CarPlayBringupState.kt", "app/src/main/java/com/mcarplay/app/iap2/CarPlayBringupState.kt"),
        ("CarPlayBringupStateTest.kt", "app/src/test/java/com/mcarplay/app/iap2/CarPlayBringupStateTest.kt"),
    ):
        copy(kit, base, source, destination)

    sender = base / "app/src/main/java/com/mcarplay/app/iap2/Iap2SenderSession.kt"
    def s(old: str, new: str, label: str) -> None:
        replace_once(sender, old, new, "Iap2SenderSession " + label)

    s(
        "import com.mcarplay.app.diagnostics.ConnectionMilestone\n",
        "import com.mcarplay.app.diagnostics.ConnectionMilestone\nimport com.mcarplay.app.net.EndpointHosts\n",
        "endpoint host import",
    )
    s(
        "    private val parser = Iap2Csm.Parser()\n",
        "    private val parser = Iap2Csm.Parser()\n    private val bringup = CarPlayBringupState()\n",
        "initialize state machine",
    )
    s(
        "        reached(ConnectionMilestone.BT_LINK)\n",
        "        bringup.onLinkReady()\n        reached(ConnectionMilestone.BT_LINK)\n",
        "link evidence",
    )
    s(
        "        reached(ConnectionMilestone.IAP2_IDENTIFIED)\n",
        "        bringup.onIdentified()\n        reached(ConnectionMilestone.IAP2_IDENTIFIED)\n",
        "identity evidence",
    )
    s(
        "        runMfiChallenge(\n",
        "        val mfiEvidence = runMfiChallenge(\n",
        "challenge returns evidence",
    )
    s(
        "        send(Iap2MessageIds.MFI_AUTHENTICATION_SUCCEEDED)\n"
        "        log(\"iap2 tx=0xaa05 authentication-succeeded（自报）\")\n"
        "        reached(ConnectionMilestone.IAP2_AUTHENTICATED)\n",
        "        val mfiAction = bringup.onMfiEvidence(mfiEvidence, channel.isAlive)\n"
        "        if (mfiAction == MfiNextAction.ABORT) {\n"
        "            throw IOException(\"MFi challenge explicitly rejected or link dropped: \" + mfiEvidence)\n"
        "        }\n"
        "        send(Iap2MessageIds.MFI_AUTHENTICATION_SUCCEEDED)\n"
        "        bringup.onAuthSignalSent()\n"
        "        log(\"iap2 tx=0xaa05 compatibility signal; evidence=\" + mfiEvidence +\n"
        "            \"; certificate/signature NOT verified; peer acceptance NOT established\")\n"
        "        reached(ConnectionMilestone.IAP2_AUTHENTICATED) // Legacy timeline means LOCAL 0xAA05 only.\n",
        "no false verified auth",
    )
    s(
        "        pinnedLength: Int? = null,\n    ) {\n        val baselineLengths =\n",
        "        pinnedLength: Int? = null,\n    ): MfiChallengeEvidence {\n        var sawExplicitRejection = false\n        val baselineLengths =\n",
        "MFi evidence return type",
    )
    s(
        "                        receiverKey?.let { MfiLengthMemory.recordHardRejected(context, it, size) }\n"
        "                        return\n",
        "                        receiverKey?.let { MfiLengthMemory.recordHardRejected(context, it, size) }\n"
        "                        return MfiChallengeEvidence.LINK_LOST\n",
        "link loss cannot be auth success",
    )
    s(
        "                if (position == 0) receiverKey?.let { MfiLengthMemory.recordSuccess(context, it, size) }\n"
        "                return\n",
        "                if (position == 0) receiverKey?.let { MfiLengthMemory.recordSuccess(context, it, size) }\n"
        "                return MfiChallengeEvidence.RESPONSE_UNVERIFIED\n",
        "response unverified not authenticated",
    )
    s(
        "            if (gotFailure) {\n                receiverKey?.let { MfiLengthMemory.recordRejected(context, it, size) }\n",
        "            if (gotFailure) {\n                sawExplicitRejection = true\n"
        "                receiverKey?.let { MfiLengthMemory.recordRejected(context, it, size) }\n",
        "record explicit rejection",
    )
    s(
        "            } else {\n                log(\"iap2 MFi 挑战全部无应答——跳过校验直接发 0xaa05（由 0x5702 判定车机是否放行）\")\n"
        "            }\n"
        "        }\n"
        "    }\n\n"
        "    /** 设备状态问候只发一次；",
        "            } else {\n                log(\"iap2 MFi 挑战结束：未观察到有效 0xaa03，不能视为认证成功\")\n"
        "            }\n"
        "        }\n"
        "        return if (sawExplicitRejection) MfiChallengeEvidence.EXPLICITLY_REJECTED\n"
        "        else MfiChallengeEvidence.TIMED_OUT\n"
        "    }\n\n"
        "    /** 设备状态问候只发一次；",
        "final MFi evidence",
    )
    s(
        "            airPlayPort = params[2]?.value?.asU32() ?: 0,\n",
        "            airPlayPort = (params[2]?.value?.asU32() ?: 0)\n"
        "                .takeIf(CarPlayEndpointRoutePolicy::validPort) ?: 0,\n",
        "reject out-of-range AirPlay ports",
    )
    s(
        "        return endpoint.copy(receiverSignals = receiverSignals)\n",
        "        val result = endpoint.copy(receiverSignals = receiverSignals)\n"
        "        val route = CarPlayEndpointRoutePolicy.classify(\n"
        "            result.ssid, result.wifiCredentialSource != WifiCredentialSource.NONE,\n"
        "            result.airPlayPort, EndpointHosts.hasUsable(result.ipAddresses),\n"
        "        )\n"
        "        bringup.observeEndpoint(result.ssid, route)\n"
        "        log(\"iap2 bring-up route=\" + route + \" MFi=\" + mfiEvidence +\n"
        "            \" (route is not network authorization or successful CarPlay display)\")\n"
        "        return result\n",
        "classify initial endpoint",
    )
    s(
        "        onEndpointUpdate?.invoke(endpoint)\n",
        "        val route = CarPlayEndpointRoutePolicy.classify(\n"
        "            endpoint.ssid, endpoint.wifiCredentialSource != WifiCredentialSource.NONE,\n"
        "            endpoint.airPlayPort, EndpointHosts.hasUsable(endpoint.ipAddresses),\n"
        "        )\n"
        "        if (!bringup.observeEndpoint(endpoint.ssid, route)) {\n"
        "            log(\"iap2 late 0x4301: incomplete retransmission ignored for the same hotspot\")\n"
        "            return\n"
        "        }\n"
        "        onEndpointUpdate?.invoke(endpoint)\n",
        "late endpoint cannot downgrade",
    )

    controller = base / "app/src/main/java/com/mcarplay/app/SessionController.kt"
    replace_once(
        controller,
        "import com.mcarplay.app.iap2.Iap2MessageIds\n",
        "import com.mcarplay.app.iap2.CarPlayEndpointRoute\n"
        "import com.mcarplay.app.iap2.CarPlayEndpointRoutePolicy\n"
        "import com.mcarplay.app.iap2.Iap2MessageIds\n",
        "SessionController endpoint policy import",
    )
    replace_once(
        controller,
        "        if (endpoint.ssid.isEmpty()) {\n            pendingStartSessionEndpoint.set(endpoint)\n",
        "        val endpointRoute = CarPlayEndpointRoutePolicy.classify(\n"
        "            endpoint.ssid, endpoint.wifiCredentialSource != WifiCredentialSource.NONE,\n"
        "            endpoint.airPlayPort, EndpointHosts.hasUsable(endpoint.ipAddresses),\n"
        "        )\n"
        "        if (endpointRoute == CarPlayEndpointRoute.WAIT_FOR_WIFI_EVIDENCE) {\n"
        "            pendingStartSessionEndpoint.set(endpoint)\n",
        "do not hand off without Wi-Fi identity evidence",
    )
    replace_once(
        controller,
        "            val endpointSelfContained =\n"
        "                endpoint.airPlayPort > 0 && EndpointHosts.hasUsable(endpoint.ipAddresses)\n",
        "            // Only a valid advertised port + usable address bypasses the ctrl/mDNS wait.\n"
        "            // This does NOT bypass network ownership checks in WifiHandoffPolicy.\n"
        "            val endpointSelfContained = endpointRoute == CarPlayEndpointRoute.DIRECT_AFTER_WIFI_BIND\n",
        "direct endpoint only when complete",
    )

    tunnel = base / "app/src/main/java/com/mcarplay/app/airplay/VirtualIap2Link.kt"
    replace_once(
        tunnel,
        "    private var mfiFinished = false\n",
        "    private var mfiFinished = false\n"
        "    private var mfiSawExplicitRejection = false\n",
        "MIB3 explicit MFi rejection memory",
    )
    replace_once(
        tunnel,
        "        if (mfiPosition >= mfiOrder.size) {\n"
        "            log(\"IAPLINK: 隧道 MFi 挑战全部无应答——跳过校验直接 0xaa05（由车机后续行为判定）\")\n",
        "        if (mfiPosition >= mfiOrder.size) {\n"
        "            if (mfiSawExplicitRejection) {\n"
        "                mfiFinished = true\n"
        "                mib3AuthStage = 0\n"
        "                log(\"IAPLINK: MFi explicitly rejected and no attempts remain; abort auth burst\")\n"
        "                return\n"
        "            }\n"
        "            log(\"IAPLINK: MFi timeout: compatibility 0xaa05 is UNVERIFIED, not receiver acceptance\")\n",
        "no MIB3 false auth after explicit rejection",
    )
    replace_once(
        tunnel,
        "            ids.MFI_AUTHENTICATION_FAILED -> {\n"
        "                if (!mib3 || mfiFinished) return\n",
        "            ids.MFI_AUTHENTICATION_FAILED -> {\n"
        "                if (!mib3 || mfiFinished) return\n"
        "                mfiSawExplicitRejection = true\n",
        "MIB3 failed response classified",
    )
    replace_once(
        tunnel,
        "            ids.MFI_RESPONSE -> {\n"
        "                val challenged = mib3AuthStage == 3\n",
        "            ids.MFI_RESPONSE -> {\n"
        "                val challenged = mib3AuthStage == 3\n"
        "                if (!challenged || frame.body.isEmpty()) {\n"
        "                    log(\"IAPLINK: unexpected/empty 0xaa03 ignored (no pending MFi challenge)\")\n"
        "                    return\n"
        "                }\n",
        "MIB3 reject unsolicited/empty response",
    )

    print("R13 MFi evidence + endpoint state machine integrated after R12", flush=True)


def main() -> None:
    kit = Path(__file__).resolve().parent.parent
    output = Path(os.environ.get("R13_OUTPUT", "apk-output-r13")).resolve()
    stage = output.parent / (output.name + "-staging")
    if output.exists() or stage.exists():
        raise PatchMismatch("R13 output exists; refusing to overwrite")
    original = r12.patch

    def with_r13(base: Path, patchkit: Path) -> None:
        original(base, patchkit)
        patch(base, patchkit)

    r12.patch = with_r13
    os.environ["R12_OUTPUT"] = str(stage)
    r12.main()

    previous = stage / "mcarplay-LaCrosse-R12-auto-wifi-sync-debug.apk"
    if not previous.is_file() or not zipfile.is_zipfile(previous):
        raise PatchMismatch("R13 build did not produce a valid APK archive")
    output.mkdir(parents=True, exist_ok=False)
    target = output / "mcarplay-LaCrosse-R13-handshake-state-debug.apk"
    shutil.copy2(previous, target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(digest + "  " + target.name + "\n", encoding="utf-8")
    (output / "SCOPE.txt").write_text(
        "R13 layers on R12. Challenge response is unverified evidence; explicit MFi rejection "
        "or lost Bluetooth link aborts; silence retains a clearly unverified compatibility path. "
        "Endpoint confidence is classified independently of Wi-Fi ownership, port 1..65535 only. "
        "CarWith/CarLife video/audio and network cryptography are unchanged. "
        "A built APK does NOT prove real vehicle connectivity.\n",
        encoding="utf-8",
    )
    shutil.rmtree(stage)
    print("R13 verified archive:", target, digest, flush=True)


if __name__ == "__main__":
    try:
        main()
    except (PatchMismatch, r12.r10.r9.r8.r7.Blocked, subprocess.CalledProcessError,
            OSError, AssertionError, ValueError) as exc:
        sys.exit("R13 BUILD BLOCKED: " + str(exc))
