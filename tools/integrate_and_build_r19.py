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
    # Rebuild the entire attempt scope so every exit either transfers the lease
    # to runSession or closes its socket and releases the lease exactly once.
    replace_once(
        client,
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
        "                    connectedLease = lease\n"
        "                    log(\"BT-C: ✓ 已连入 $name 的无线 iAP2 服务（RFCOMM 建立）\")\n"
        "                    Iap2ReceiverMemory.remember(context, device.address)\n"
        "                    connected = socket\n"
        "                    break\n"
        "                } else {\n"
        "                    // A preempted or failed attempt cannot retain a socket or an ownership lease.\n"
        "                    if (socket != null) {\n"
        "                        currentSocket.compareAndSet(socket, null)\n"
        "                        runCatching { socket.close() }\n"
        "                    }\n"
        "                    lease.close()\n"
        "                    val now = android.os.SystemClock.uptimeMillis()\n"
        "                    if (!inboundWait.isWaiting(device.address) && now - lastFailureLogAt > FAILURE_LOG_THROTTLE_MILLIS) {\n"
        "                        lastFailureLogAt = now\n"
        "                        log(\"BT-C: 连接 $name 失败（具体阶段与系统异常见 BT-DIAG），3 秒后重试…\")\n"
        "                    }\n"
        "                }\n",
        "                val lease = BtSessionGate.acquireOutbound() ?: continue\n"
        "                var candidateSocket: BluetoothSocket? = null\n"
        "                var leaseTransferred = false\n"
        "                try {\n"
        "                    // Guard the blocking socket creation/connect and its ownership as one operation.\n"
        "                    val started = lease.dispatchIfCurrent {\n"
        "                        candidateSocket = selfLinkChange {\n"
        "                            tryConnect(device, name, myGeneration, diagnosticEpoch, lease)\n"
        "                        }\n"
        "                    }\n"
        "                    val socket = candidateSocket\n"
        "                    if (started && socket != null && lease.isCurrent) {\n"
        "                        runCatching { Iap2ReceiverMemory.remember(context, device.address) }\n"
        "                            .onFailure { error -> runCatching { log(\"BT-C: 接收端记忆写入失败 - ${error.message}\") } }\n"
        "                        connected = socket\n"
        "                        connectedLease = lease\n"
        "                        leaseTransferred = true\n"
        "                        runCatching { log(\"BT-C: ✓ 已连入 $name 的无线 iAP2 服务（RFCOMM 建立）\") }\n"
        "                        break\n"
        "                    }\n"
        "                    if (socket != null) {\n"
        "                        currentSocket.compareAndSet(socket, null)\n"
        "                        runCatching { socket.close() }\n"
        "                    }\n"
        "                    val now = android.os.SystemClock.uptimeMillis()\n"
        "                    if (!inboundWait.isWaiting(device.address) && now - lastFailureLogAt > FAILURE_LOG_THROTTLE_MILLIS) {\n"
        "                        lastFailureLogAt = now\n"
        "                        log(\"BT-C: 连接 $name 失败（具体阶段与系统异常见 BT-DIAG），3 秒后重试…\")\n"
        "                    }\n"
        "                } catch (error: Exception) {\n"
        "                    currentSocket.getAndSet(null)?.let { runCatching { it.close() } }\n"
        "                    runCatching { log(\"BT-C: RFCOMM 尝试异常 - ${error.message ?: error.javaClass.simpleName}\") }\n"
        "                } finally {\n"
        "                    if (!leaseTransferred) {\n"
        "                        candidateSocket?.let {\n"
        "                            currentSocket.compareAndSet(it, null)\n"
        "                            runCatching { it.close() }\n"
        "                        }\n"
        "                        lease.close()\n"
        "                    }\n"
        "                }\n",
        "make outbound lease/socket transfer exception-safe and preemption-aware",
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
        "                val entered = lease.dispatchIfCurrent { runSession(connected, lease) }\n"
        "                if (!entered) {\n"
        "                    currentSocket.compareAndSet(connected, null)\n"
        "                    runCatching { connected.close() }\n"
        "                }\n"
        "            } finally {\n"
        "                lease.close()\n"
        "            }\n",
        "guard socket-to-protocol transition and lease lifetime",
    )
    # Register cancellation against the exact socket after creation. This closes
    # the race where inbound wins before currentSocket is populated.
    replace_once(
        client,
        "    private fun tryConnect(\n"
        "        device: BluetoothDevice,\n"
        "        name: String,\n"
        "        myGeneration: Long,\n"
        "        diagnosticEpoch: Long,\n"
        "    ): BluetoothSocket? {\n",
        "    private fun tryConnect(\n"
        "        device: BluetoothDevice,\n"
        "        name: String,\n"
        "        myGeneration: Long,\n"
        "        diagnosticEpoch: Long,\n"
        "        lease: BluetoothSessionArbiter.Lease,\n"
        "    ): BluetoothSocket? {\n",
        "bind RFCOMM connect attempt to its lease",
    )
    replace_once(
        client,
        "            } catch (error: IOException) {\n"
        "                diagnostics.connectFinished(\n"
        "                    trace,\n"
        "                    creatingSocket = true,\n"
        "                    error = error,\n"
        "                    cancelled =\n"
        "                        !running || generation.get() != myGeneration,\n"
        "                )\n"
        "                return null\n",
        "            } catch (error: IOException) {\n"
        "                diagnostics.connectFinished(\n"
        "                    trace,\n"
        "                    creatingSocket = true,\n"
        "                    error = error,\n"
        "                    cancelled =\n"
        "                        !lease.isCurrent || !running || generation.get() != myGeneration,\n"
        "                )\n"
        "                return null\n",
        "classify socket creation interrupted by inbound preemption as cancellation",
    )
    replace_once(
        client,
        "            val cancelled = !running || generation.get() != myGeneration\n"
        "            diagnostics.connectFinished(trace, error = error, cancelled = cancelled)\n"
        "            if (!cancelled) noteConnectFailure(device, name, error, SystemClock.elapsedRealtime() - connectStartedAt)\n",
        "            val cancelled = !lease.isCurrent || !running || generation.get() != myGeneration\n"
        "            diagnostics.connectFinished(trace, error = error, cancelled = cancelled)\n"
        "            if (!cancelled) noteConnectFailure(device, name, error, SystemClock.elapsedRealtime() - connectStartedAt)\n",
        "do not count intentional inbound preemption as receiver rejection",
    )
    replace_once(
        client,
        "        currentSocket.set(socket)\n"
        "        if (!running || generation.get() != myGeneration) {\n",
        "        lease.onPreempted {\n"
        "            currentSocket.compareAndSet(socket, null)\n"
        "            runCatching { socket.close() }\n"
        "            runCatching { activeChannel.get()?.close() }\n"
        "        }\n"
        "        currentSocket.set(socket)\n"
        "        if (!lease.isCurrent || !running || generation.get() != myGeneration) {\n",
        "register exact socket cancellation before blocking connect",
    )
    replace_once(
        client,
        "            socket.connect()\n"
        "            diagnostics.connectFinished(trace, cancelled = !running || generation.get() != myGeneration)\n"
        "            inboundWait.connected(device.address)\n"
        "            socket\n",
        "            socket.connect()\n"
        "            if (!lease.isCurrent || !running || generation.get() != myGeneration) {\n"
        "                currentSocket.compareAndSet(socket, null)\n"
        "                runCatching { socket.close() }\n"
        "                diagnostics.connectFinished(trace, cancelled = true)\n"
        "                return null\n"
        "            }\n"
        "            diagnostics.connectFinished(trace, cancelled = false)\n"
        "            inboundWait.connected(device.address)\n"
        "            socket\n",
        "reject socket success after preemption or stop",
    )
    replace_once(
        client,
        "        } catch (error: SecurityException) {\n"
        "            currentSocket.compareAndSet(socket, null)\n"
        "            runCatching { socket.close() }\n"
        "            diagnostics.connectFinished(trace, error = error, cancelled = !running || generation.get() != myGeneration)\n"
        "            null\n"
        "        }\n",
        "        } catch (error: Exception) {\n"
        "            currentSocket.compareAndSet(socket, null)\n"
        "            runCatching { socket.close() }\n"
        "            val cancelled = !lease.isCurrent || !running || generation.get() != myGeneration\n"
        "            diagnostics.connectFinished(trace, error = error, cancelled = cancelled)\n"
        "            if (!cancelled) runCatching { log(\"BT-C: RFCOMM connect exception - ${error.message ?: error.javaClass.simpleName}\") }\n"
        "            null\n"
        "        }\n",
        "clean up unexpected RFCOMM connect exceptions",
    )
    replace_once(
        client,
        "            } catch (error: SecurityException) {\n"
        "                diagnostics.connectFinished(\n"
        "                    trace,\n"
        "                    creatingSocket = true,\n"
        "                    error = error,\n"
        "                    cancelled =\n"
        "                        !running || generation.get() != myGeneration,\n"
        "                )\n"
        "                return null\n"
        "            }\n",
        "        } catch (error: Exception) {\n"
        "            diagnostics.connectFinished(\n"
        "                trace,\n"
        "                creatingSocket = true,\n"
        "                error = error,\n"
        "                cancelled =\n"
        "                    !lease.isCurrent || !running || generation.get() != myGeneration,\n"
        "            )\n"
        "            return null\n"
        "        }\n",
        "handle unexpected RFCOMM socket creation exceptions",
    )

    # Make every post-connect exit close the socket, even when stream acquisition
    # or channel construction throws before the old try/finally was entered.
    replace_once(
        client,
        "        if (!lease.isCurrent) {\n"
        "            runCatching { socket.close() }\n"
        "            return\n"
        "        }\n"
        "        val stream =\n"
        "            StreamDuplexStream(socket.inputStream, socket.outputStream) {\n"
        "                runCatching { socket.close() }\n"
        "            }\n"
        "        val channel = Iap2LinkChannel(stream, name = \"iap2-bt-car\") { line -> log(line) }\n"
        "        activeChannel.set(channel)\n"
        "        try {\n",
        "        var sessionChannel: Iap2LinkChannel? = null\n"
        "        try {\n"
        "            if (!lease.isCurrent) return\n"
        "            val stream =\n"
        "                StreamDuplexStream(socket.inputStream, socket.outputStream) {\n"
        "                    runCatching { socket.close() }\n"
        "                }\n"
        "            val channel = Iap2LinkChannel(stream, name = \"iap2-bt-car\") { line -> log(line) }\n"
        "            sessionChannel = channel\n"
        "            activeChannel.set(channel)\n"
        "            if (!lease.isCurrent) return\n",
        "put stream/channel setup inside unconditional cleanup scope",
    )
    replace_once(
        client,
        "        } catch (error: IOException) {\n"
        "            log(\"BT-C: SESSION 失败 - ${error.message}\")\n"
        "        } finally {\n",
        "        } catch (error: IOException) {\n"
        "            runCatching { log(\"BT-C: SESSION 失败 - ${error.message}\") }\n"
        "        } catch (error: Exception) {\n"
        "            if (error is InterruptedException) Thread.currentThread().interrupt()\n"
        "            runCatching { log(\"BT-C: SESSION 异常 - ${error.message ?: error.javaClass.simpleName}\") }\n"
        "        } finally {\n",
        "keep reconnect loop alive after non-IO session setup failures",
    )
    replace_once(
        client,
        "            activeChannel.compareAndSet(channel, null)\n"
        "            activeSession.get()?.takeIf { it.first === channel }?.let { activeSession.compareAndSet(it, null) }\n"
        "            currentSocket.compareAndSet(socket, null)\n"
        "            runCatching { socket.close() }\n"
        "            channel.close()\n"
        "            log(\"BT-C: 本轮会话结束（客户端仍在运行，将自动重连）\")\n",
        "            sessionChannel?.let { channel ->\n"
        "                activeChannel.compareAndSet(channel, null)\n"
        "                activeSession.get()?.takeIf { it.first === channel }?.let { activeSession.compareAndSet(it, null) }\n"
        "                runCatching { channel.close() }\n"
        "            }\n"
        "            currentSocket.compareAndSet(socket, null)\n"
        "            runCatching { socket.close() }\n"
        "            runCatching { log(\"BT-C: 本轮会话结束（客户端仍在运行，将自动重连）\") }\n",
        "always retire socket and optional channel",
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
        """/** One lock serializes RFCOMM ownership with the AirPlay active-session gate. */
object BtSessionGate {
    private val arbiter = BluetoothSessionArbiter()

    val inboundActive: Boolean get() = arbiter.inboundActive
    val controlActive: Boolean get() = arbiter.controlActive

    var sessionActive: Boolean
        get() = arbiter.sessionActive
        set(value) = arbiter.setSessionActive(value)

    internal fun acquireInbound(): BluetoothSessionArbiter.Lease? = arbiter.acquireInbound()

    internal fun acquireOutbound(): BluetoothSessionArbiter.Lease? = arbiter.acquireOutbound()
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
        "sessionActiveBlocksNewOutboundLeaseUntilCleared",
        "preemptedOutboundCannotStartLateTransportOperation",
        "preemptionCallbackFailureDoesNotOrphanInboundOwner",
        "callbackRegisteredAfterRetirementIsNotInvoked",
        "latePreemptionCallbackFailureDoesNotEscapeAcquisitionThread",
    }
    cases = suite.findall("testcase")
    observed = {case.attrib.get("name") for case in cases}
    if len(cases) != 15 or observed != expected:
        raise InvariantError(f"R19 must run exactly 15 arbiter scenarios: got {observed}")
    for attr in ("failures", "errors", "skipped"):
        if int(suite.attrib.get(attr, "0")) != 0:
            raise InvariantError(f"R19 arbiter report has {attr} != 0")

    if os.environ.get("R19_SOURCE_ONLY") == "1":
        print("R19 source-only review PASS: 15/15 arbiter tests; no APK assembled", flush=True)
        return

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
