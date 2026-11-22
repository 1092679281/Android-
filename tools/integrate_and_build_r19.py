#!/usr/bin/env python3
"""R19: adversarial review of dual RFCOMM control sessions on the R18 baseline."""
from pathlib import Path
import hashlib
import os
import shutil
import sys
import zipfile
import xml.etree.ElementTree as ET
import integrate_and_build_r18 as r18


class InvariantError(RuntimeError):
    pass


def replace_once(path: Path, old: str, new: str, reason: str) -> None:
    data = path.read_text(encoding="utf-8")
    count = data.count(old)
    if count != 1:
        raise InvariantError(f"{reason}: expected 1 match, found {count} in {path}")
    path.write_text(data.replace(old, new, 1), encoding="utf-8")


def patch(base: Path, kit: Path) -> None:
    copy = r18.r16.r15.r14.r13.r12.r10.r9.r8.copy_new
    copy(kit, base, "BluetoothSessionArbiter.kt", "app/src/main/java/com/mcarplay/app/bt/BluetoothSessionArbiter.kt")
    copy(kit, base, "BluetoothSessionArbiterTest.kt", "app/src/test/java/com/mcarplay/app/bt/BluetoothSessionArbiterTest.kt")

    client = base / "app/src/main/java/com/mcarplay/app/bt/Iap2BluetoothClient.kt"

    # A lease is acquired before starting BluetoothSocket.connect(), not after:
    # inbound calls may arrive during SDP or while an outgoing socket is blocked.
    replace_once(
        client,
        "            var connected: BluetoothSocket? = null\n",
        "            var connected: BluetoothSocket? = null\n"
        "            var connectedLease: BluetoothSessionArbiter.Lease? = null\n",
        "track owned outbound socket",
    )
    replace_once(
        client,
        "                val socket = selfLinkChange { tryConnect(device, name, myGeneration, diagnosticEpoch) }\n"
        "                if (socket != null) {\n",
        "                val lease = BtSessionGate.acquireOutbound() ?: continue\n"
        "                lease.onPreempted {\n"
        "                    // Car-initiated RFCOMM takes precedence over an UNCONFIRMED outgoing attempt.\n"
        "                    runCatching { currentSocket.get()?.close() }\n"
        "                    runCatching { activeChannel.get()?.close() }\n"
        "                }\n"
        "                val socket =\n"
        "                    try {\n"
        "                        selfLinkChange { tryConnect(device, name, myGeneration, diagnosticEpoch) }\n"
        "                    } catch (error: Exception) {\n"
        "                        lease.close()\n"
        "                        throw error\n"
        "                    }\n"
        "                if (socket != null && lease.isCurrent) {\n"
        "                    connectedLease = lease\n",
        "reserve outbound before connect and reject stale successes",
    )
    replace_once(
        client,
        "                } else {\n"
        "                    val now = android.os.SystemClock.uptimeMillis()\n"
        "                    if (!inboundWait.isWaiting(device.address) && now - lastFailureLogAt > FAILURE_LOG_THROTTLE_MILLIS) {\n",
        "                } else {\n"
        "                    // A preempted or failed attempt cannot retain a socket or an ownership lease.\n"
        "                    if (socket != null) {\n"
        "                        currentSocket.compareAndSet(socket, null)\n"
        "                        runCatching { socket.close() }\n"
        "                    }\n"
        "                    lease.close()\n"
        "                    val now = android.os.SystemClock.uptimeMillis()\n"
        "                    if (!inboundWait.isWaiting(device.address) && now - lastFailureLogAt > FAILURE_LOG_THROTTLE_MILLIS) {\n",
        "release failed/preempted outgoing lease",
    )
    replace_once(
        client,
        "            if (generation.get() != myGeneration) {\n"
        "                // stop() 与 connect() 成功竞争：本线程已过期，不建会话\n"
        "                currentSocket.compareAndSet(connected, null)\n"
        "                runCatching { connected.close() }\n"
        "                return\n"
        "            }\n"
        "            runSession(connected)\n",
        "            val lease = connectedLease ?: throw IllegalStateException(\"Successful RFCOMM has no arbiter lease\")\n"
        "            if (generation.get() != myGeneration || !lease.isCurrent) {\n"
        "                // A late outgoing connect() may succeed after inbound owns the session.\n"
        "                currentSocket.compareAndSet(connected, null)\n"
        "                runCatching { connected.close() }\n"
        "                lease.close()\n"
        "                if (generation.get() != myGeneration) return\n"
        "                continue\n"
        "            }\n"
        "            try {\n"
        "                runSession(connected, lease)\n"
        "            } finally {\n"
        "                lease.close()\n"
        "            }\n",
        "guard socket-to-protocol transition and lease lifetime",
    )
    replace_once(
        client,
        "    private fun runSession(socket: BluetoothSocket) {\n",
        "    private fun runSession(socket: BluetoothSocket, lease: BluetoothSessionArbiter.Lease) {\n"
        "        if (!lease.isCurrent) {\n"
        "            runCatching { socket.close() }\n"
        "            return\n"
        "        }\n",
        "bound outbound protocol to live lease",
    )
    replace_once(
        client,
        "                onEndpoint,\n"
        "                onWifiCredentials,\n"
        "                onEndpointUpdate,\n"
        "                onLinkClosed,\n"
        "                onPreEndpointFailure,\n",
        "                { endpoint ->\n"
        "                    lease.dispatchIfCurrent { if (lease.confirm()) onEndpoint(endpoint) }\n"
        "                },\n"
        "                { credentials -> lease.dispatchIfCurrent { onWifiCredentials(credentials) } },\n"
        "                { endpoint -> lease.dispatchIfCurrent { onEndpointUpdate(endpoint) } },\n"
        "                { observation, peer -> lease.dispatchIfCurrent { onLinkClosed(observation, peer) } },\n"
        "                { reason, peer -> lease.dispatchIfCurrent { onPreEndpointFailure(reason, peer) } },\n",
        "prevent stale outgoing callbacks from altering active vehicle session",
    )
    replace_once(
        client,
        "                onGeneration,\n"
        "                peerAddress = socket.remoteDevice?.address,\n"
        "                onObservation = onObservation,\n",
        "                { generation -> lease.dispatchIfCurrent { onGeneration(generation) } },\n"
        "                peerAddress = socket.remoteDevice?.address,\n"
        "                onObservation = { observation, active -> lease.dispatchIfCurrent { onObservation(observation, active) } },\n",
        "ignore old outbound observation data",
    )
    replace_once(
        client,
        "                onSession = { session -> if (activeChannel.get() === channel) activeSession.set(channel to session) },\n",
        "                onSession = { session -> lease.dispatchIfCurrent { if (activeChannel.get() === channel) activeSession.set(channel to session) } },\n",
        "ensure outbound activeSession belongs to lease",
    )

    # Old shared flags are not atomic; replace them with a shared lease arbiter
    # that both the inbound server and outbound client use for every RFCOMM.
    source = client.read_text(encoding="utf-8")
    delimiter = "/**\n * 入站会话门闸：车机主动连入的 iAP2 会话活跃期间，出站客户端暂停连接尝试。\n"
    if source.count(delimiter) != 1:
        raise InvariantError("Cannot identify original BtSessionGate flag object")
    head = source.split(delimiter, 1)[0]
    client.write_text(
        head +
        """/** An atomic lease arbiter prevents simultaneous iAP2 control handshakes. */
object BtSessionGate {
    private val arbiter = BluetoothSessionArbiter()

    val inboundActive: Boolean get() = arbiter.inboundActive
    val controlActive: Boolean get() = arbiter.controlActive

    @Volatile
    var sessionActive: Boolean = false

    internal fun acquireInbound(): BluetoothSessionArbiter.Lease? = arbiter.acquireInbound()

    internal fun acquireOutbound(): BluetoothSessionArbiter.Lease? =
        if (sessionActive) null else arbiter.acquireOutbound()
}
""",
        encoding="utf-8",
    )

    server = base / "app/src/main/java/com/mcarplay/app/bt/Iap2BluetoothServer.kt"
    replace_once(
        server,
        "            log(\"BT: 接收端已连入 name=$peerName，开始 iAP2 发送端会话\")\n"
        "            val observation = ReceiverDetectionRuntime.observation(peerAddress)\n"
        "            Thread({ runSession(socket, observation) }, \"iap2-bt-session\").apply {\n",
        "            val lease = BtSessionGate.acquireInbound()\n"
        "            if (lease == null) {\n"
        "                log(\"BT: 已有确认过的 iAP2 会话或接收端回连，拒绝第二条 RFCOMM 避免双链路互踩\")\n"
        "                runCatching { socket.close() }\n"
        "                continue\n"
        "            }\n"
        "            log(\"BT: 车机回连获得唯一 iAP2 所有权，等待旧出站连接退出\")\n"
        "            val observation = ReceiverDetectionRuntime.observation(peerAddress)\n"
        "            Thread({\n"
        "                try {\n"
        "                    runSession(socket, observation, lease)\n"
        "                } finally {\n"
        "                    // Even if socket.inputStream fails before runSession try/finally.\n"
        "                    lease.close()\n"
        "                    runCatching { socket.close() }\n"
        "                }\n"
        "            }, \"iap2-bt-session\").apply {\n",
        "acquire inbound owner before thread scheduling",
    )
    replace_once(
        server,
        "    private fun runSession(\n"
        "        socket: BluetoothSocket,\n"
        "        observation: ReceiverObservation?,\n"
        "    ) {\n",
        "    private fun runSession(\n"
        "        socket: BluetoothSocket,\n"
        "        observation: ReceiverObservation?,\n"
        "        lease: BluetoothSessionArbiter.Lease,\n"
        "    ) {\n"
        "        if (!lease.awaitPreviousRetirement(5_000)) {\n"
        "            log(\"BT: 旧出站连接未完成清理或本轮已取消——拒绝并行 iAP2 协商，等待新回连\")\n"
        "            runCatching { socket.close() }\n"
        "            lease.close()\n"
        "            return\n"
        "        }\n",
        "wait for old outgoing writes to retire before inbound starts",
    )
    replace_once(
        server,
        "            BtSessionGate.inboundActive = true\n",
        "",
        "remove mutable inboundActive flag",
    )
    replace_once(
        server,
        "                onEndpoint,\n"
        "                onWifiCredentials,\n"
        "                onEndpointUpdate,\n"
        "                onLinkClosed,\n"
        "                onPreEndpointFailure,\n",
        "                { endpoint -> lease.dispatchIfCurrent { onEndpoint(endpoint) } },\n"
        "                { credentials -> lease.dispatchIfCurrent { onWifiCredentials(credentials) } },\n"
        "                { endpoint -> lease.dispatchIfCurrent { onEndpointUpdate(endpoint) } },\n"
        "                { observation, peer -> lease.dispatchIfCurrent { onLinkClosed(observation, peer) } },\n"
        "                { reason, peer -> lease.dispatchIfCurrent { onPreEndpointFailure(reason, peer) } },\n",
        "prevent stale inbound callbacks",
    )
    replace_once(
        server,
        "                onGeneration,\n"
        "                peerAddress = socket.remoteDevice?.address,\n"
        "                observation = observation,\n"
        "                onObservation = onObservation,\n",
        "                { generation -> lease.dispatchIfCurrent { onGeneration(generation) } },\n"
        "                peerAddress = socket.remoteDevice?.address,\n"
        "                observation = observation,\n"
        "                onObservation = { activeObservation, active -> lease.dispatchIfCurrent { onObservation(activeObservation, active) } },\n",
        "prevent stale inbound generation/state",
    )
    replace_once(
        server,
        "                    synchronized(channelLock) { if (activeChannel === channel) activeSession = session }\n",
        "                    lease.dispatchIfCurrent { synchronized(channelLock) { if (activeChannel === channel) activeSession = session } }\n",
        "register live inbound sessions only",
    )
    # Both legacy flag resets are obsolete. A lease must stay owned until
    # runSession actually stops; detachCurrentSession may only close the channel.
    old_flag = "                    BtSessionGate.inboundActive = false\n"
    data = server.read_text(encoding="utf-8")
    if data.count(old_flag) != 2:
        raise InvariantError(f"expected 2 legacy inbound flag clears, found {data.count(old_flag)}")
    server.write_text(data.replace(old_flag, ""), encoding="utf-8")
    replace_once(
        server,
        "            channel.close()\n"
        "            log(\"SESSION 结束，等待接收端重连（BT 监听仍在运行）\")\n",
        "            channel.close()\n"
        "            lease.close()\n"
        "            log(\"SESSION 结束，等待接收端重连（BT 监听仍在运行）\")\n",
        "retire inbound lease in finally",
    )
    print("R19: atomic inbound/outbound BT ownership, no concurrent iAP2 handshakes", flush=True)


def main() -> None:
    output = Path(os.environ.get("R19_OUTPUT", "apk-output-r19")).resolve()
    stage = output.parent / (output.name + "-staging")
    if output.exists() or stage.exists():
        raise InvariantError("R19 output/staging already exists")
    original_patch = r18.patch

    def with_r19(base: Path, kit: Path) -> None:
        original_patch(base, kit)
        patch(base, kit)

    r18.patch = with_r19
    os.environ["R18_OUTPUT"] = str(stage)
    r18.main()

    report_path = (
        Path(os.environ["R7_UPSTREAM"]).resolve()
        / "app/build/test-results/testStandardDebugUnitTest"
        / "TEST-com.mcarplay.app.bt.BluetoothSessionArbiterTest.xml"
    )
    if not report_path.is_file():
        raise InvariantError("Required R19 arbiter JUnit XML missing")
    suite = ET.parse(report_path).getroot()
    expected = {
        "onlyOneOutboundAttemptMayOwnControlChannel",
        "inboundPreemptsUnconfirmedOutboundExactlyOnce",
        "staleOutboundCleanupCannotReleaseNewInboundOwner",
        "preemptCallbackRegisteredAfterReplacementStillFiresExactlyOnce",
        "establishedOutboundCannotBeTakenByIncomingSocket",
        "secondInboundNeverInterruptsFirstInbound",
        "oldOutboundCannotConfirmAfterPreemptionAndNewSocketWaitsForRelease",
        "newInboundMustWaitUntilOldInFlightCallbackFinishes",
        "competingOutboundStartsAreMutuallyExclusive",
        "independentInstancesCannotShareLeasesAcrossSessions",
    }
    cases = suite.findall("testcase")
    observed = {case.attrib.get("name") for case in cases}
    if len(cases) != 10 or observed != expected:
        raise InvariantError(f"R19 must run exactly 10 arbiter scenarios: got {observed}")
    for attr in ("failures", "errors", "skipped"):
        if int(suite.attrib.get(attr, "0")) != 0:
            raise InvariantError(f"R19 arbiter report has {attr} != 0")

    previous = stage / "mcarplay-LaCrosse-R18-identity-snapshot-debug.apk"
    if not previous.is_file() or not zipfile.is_zipfile(previous):
        raise InvariantError("Android build/tests did not produce a valid staged APK")

    output.mkdir(parents=True, exist_ok=False)
    destination = output / "mcarplay-LaCrosse-R19-connection-arbiter-debug.apk"
    shutil.copy2(previous, destination)
    sha = hashlib.sha256(destination.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(f"{sha}  {destination.name}\n", encoding="utf-8")
    (output / "BLUETOOTH_ARBITER_JUNIT.xml").write_bytes(report_path.read_bytes())
    (output / "REVIEW-SCOPE.md").write_text(
        "R19 independently examines concurrency, identity and protocol-gating. "
        "Real changes: shared atomic RFCOMM ownership, inbound can take an "
        "unconfirmed outbound attempt, bounded previous-lease retirement, "
        "stale callback rejection, tests for races and stale cleanup. "
        "Inherited: R18 shared MAC, R16 SETUP500 gating, R15 updater. "
        "NOT implemented: privileged wireless ADB service, full Buick E2LB "
        "MFi trust, CarWith in-vehicle picture validation. "
        "Do NOT treat debug APK or mock receiver success as real CarPlay support.\n",
        encoding="utf-8",
    )
    shutil.rmtree(stage)
    print("R19 Android build and gate tests PASS, sha256:", sha, flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        sys.exit("R19 BUILD BLOCKED: " + str(exc))
