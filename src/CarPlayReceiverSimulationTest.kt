package com.mcarplay.app.airplay

import com.mcarplay.app.iap2.Iap2SenderSession
import com.mcarplay.app.video.ExternalVideoFrame
import com.mcarplay.app.video.ExternalVideoSource
import com.mcarplay.app.video.VideoSender
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.ByteArrayOutputStream
import java.io.Closeable
import java.io.DataInputStream
import java.io.InputStream
import java.net.InetAddress
import java.net.ServerSocket
import java.net.Socket
import java.net.SocketException
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.concurrent.CopyOnWriteArrayList
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Loopback receiver simulation: actual AirPlayClient RTSP, actual VideoSender TCP,
 * actual plist encoding and H.264 Annex-B -> avcC + encrypted frame packaging.
 *
 * Scope: one host JVM, no Android emulator, Bluetooth RFCOMM, mDNS, CarWith capture,
 * real MFi hardware or vehicle firmware. A 200 response here comes from OUR FAKE
 * receiver; it must never be represented as the actual Buick accepting CarPlay.
 */
class CarPlayReceiverSimulationTest {
    @Test
    fun endToEndCleartextRtspThroughTwoSetupsTcpRecordAndVideoFrames() {
        FakeReceiver().use { receiver ->
            val client = AirPlayClient(receiver.endpoint, log = {})
            client.enableActivationGate()
            var sender: VideoSender? = null
            try {
                assertTrue(client.reconnect())
                assertFalse("No RECORD before SETUP", client.record())

                val setup = client.runSetup()
                assertNotNull("Session SETUP must yield a parsed response", setup)
                assertEquals("simulated-display", setup!!.displayUuid)
                assertEquals(1280, setup.displayWidth)
                assertEquals(720, setup.displayHeight)

                val stream = client.runScreenStream(null, setup.displayUuid)
                assertNotNull("Stream SETUP must supply dataPort", stream)
                assertEquals(receiver.videoPort, stream!!.dataPort)
                assertFalse("No RECORD before a real TCP connection", client.record())

                sender =
                    VideoSender(
                        "127.0.0.1",
                        stream.dataPort,
                        stream.cipher,
                        1280,
                        720,
                        log = {},
                        externalVideoSource = object : ExternalVideoSource {
                            override fun requestKeyFrame(): Boolean = true
                        },
                    )
                assertTrue("Actual VideoSender socket must connect", sender.openDataPort())
                assertTrue("Fake receiver must observe TCP accept", receiver.videoConnected.await(2, TimeUnit.SECONDS))
                assertTrue(client.confirmVideoDataPortConnected(true))
                assertTrue("RECORD 200 should activate the local simulated session", client.record())

                assertTrue(sender.start {})
                val h264 =
                    intArrayOf(
                        0, 0, 0, 1, 0x67, 0x42, 0, 0x1f,
                        0, 0, 0, 1, 0x68, 0xce, 6, 0xe2,
                        0, 0, 0, 1, 0x65, 0x88, 0x84,
                    ).map { it.toByte() }.toByteArray()
                assertTrue(sender.submitExternalFrame(ExternalVideoFrame(h264, true, 0)))
                assertTrue("Simulator should receive avcC and one video frame", receiver.twoVideoMessages.await(3, TimeUnit.SECONDS))
                assertEquals(listOf(1, 0), receiver.videoOpcodes.take(2))
                assertEquals(1L, sender.framesSentTotal)
                assertEquals(
                    listOf("SETUP /setup", "GET /info", "SETUP /", "RECORD /"),
                    receiver.requests.map { it.method + " " + it.path },
                )
                val firstBody = receiver.requests.first().body
                assertEquals("02:00:00:00:00:00", firstBody["deviceID"])
                assertTrue((firstBody["timingPort"] as Number).toInt() > 0)
                assertTrue((firstBody["features"] as List<*>).contains("viewAreas"))
                val screenBody = (receiver.requests[2].body["streams"] as List<*>).single() as Map<*, *>
                assertEquals(110L, screenBody["type"])
                assertEquals("simulated-display", screenBody["uuid"])
            } finally {
                sender?.stop()
                client.close()
            }
        }
    }

    @Test
    fun buickLikeSetup500MustStopBeforeScreenStreamAndRecord() {
        FakeReceiver(setupReply = FakeReceiver.SetupReply.REJECT_500).use { receiver ->
            val client = AirPlayClient(receiver.endpoint, log = {})
            client.enableActivationGate()
            try {
                assertTrue(client.reconnect())
                assertNull(client.runSetup())
                assertEquals(500, client.lastInitialSetupStatusCode)
                assertTrue(client.lastInitialSetupUsedPlaceholderId)
                assertNull("A screen stream is forbidden without initial SETUP", client.runScreenStream(null, "simulated-display"))
                assertFalse("A failed SETUP cannot RECORD", client.record())
                assertEquals(listOf("SETUP /setup"), receiver.requests.map { it.method + " " + it.path })
                assertEquals(
                    InitialSetupRecoveryAction.WAIT_FOR_FRESH_CTRL_INVITE,
                    InitialSetupRecoveryPolicy.afterRejectedSetup(
                        client.lastInitialSetupStatusCode,
                        gatewayPortWasGuessed = true,
                        ctrlInvitesObserved = 0,
                    ),
                )
            } finally {
                client.close()
            }
        }
    }

    @Test
    fun successStatusWithMalformedPlistIsNotSuccessfulSetup() {
        FakeReceiver(setupReply = FakeReceiver.SetupReply.MALFORMED_200).use { receiver ->
            val client = AirPlayClient(receiver.endpoint, log = {})
            client.enableActivationGate()
            try {
                assertTrue(client.reconnect())
                assertNull("200 without valid plist must be rejected", client.runSetup())
                assertEquals(200, client.lastInitialSetupStatusCode)
                assertFalse(client.record())
                assertEquals(listOf("SETUP /setup"), receiver.requests.map { it.method + " " + it.path })
            } finally {
                client.close()
            }
        }
    }

    @Test
    fun absentVideoTcpListenerMustBlockRecordDespiteTwoSuccessfulSetups() {
        FakeReceiver(videoAvailable = false).use { receiver ->
            val client = AirPlayClient(receiver.endpoint, log = {})
            client.enableActivationGate()
            val sender: VideoSender?
            try {
                assertTrue(client.reconnect())
                val setup = client.runSetup()
                assertNotNull(setup)
                val stream = client.runScreenStream(null, setup!!.displayUuid)
                assertNotNull(stream)
                sender = VideoSender("127.0.0.1", stream!!.dataPort, stream.cipher, 1280, 720, log = {})
                try {
                    assertFalse("Closed data listener should fail socket connect", sender.openDataPort())
                    assertFalse("Never signal a TCP connection that did not happen", client.confirmVideoDataPortConnected(false))
                    assertFalse("RECORD cannot follow failed video socket", client.record())
                    assertEquals(
                        listOf("SETUP /setup", "GET /info", "SETUP /"),
                        receiver.requests.map { it.method + " " + it.path },
                    )
                } finally {
                    sender.stop()
                }
            } finally {
                client.close()
            }
        }
    }

    @Test
    fun independentReferenceReceiverValidatesSrpPairingAndEncryptedKeyDirections() {
        // Existing upstream reference peer follows PairSetup/PairVerify SRP6a,
        // but is an in-memory cryptographic peer, NOT an encrypted RTSP TCP server.
        val server = AirPlayPairingTest.MockReceiver()
        val keys = AirPlayCrypto.ed25519Generate()
        val identity = ControllerIdentity("sim-phone", keys.privateKey, keys.publicKey)
        val transport = TlvTransport { path, payload -> server.handle(path, payload) }
        val paired = PairSetupClient(identity, transport) { }.run()
        assertNotNull(paired)
        assertTrue(server.pairings.containsKey(identity.pairingId))
        val verified = PairVerifyClient(identity, transport) { }.run(server.staticKey.publicKey)
        assertTrue(verified.phoneWriteKey.contentEquals(server.lastReadKey))
        assertTrue(verified.phoneReadKey.contentEquals(server.lastWriteKey))
    }

    /** Small TCP receiver with deterministic, strict SETUP/RECORD sequencing. */
    private class FakeReceiver(
        private val setupReply: SetupReply = SetupReply.ACCEPT_200,
        videoAvailable: Boolean = true,
    ) : Closeable {
        enum class SetupReply { ACCEPT_200, REJECT_500, MALFORMED_200 }

        data class Request(val method: String, val path: String, val body: Map<*, *>)

        private val loopback = InetAddress.getByName("127.0.0.1")
        private val controlSocket = ServerSocket(0, 1, loopback)
        private val dataSocket = ServerSocket(0, 1, loopback)
        val videoPort: Int = dataSocket.localPort
        val endpoint =
            Iap2SenderSession.CarPlayEndpoint(
                ssid = "CARPLAY-SIMULATION",
                passphrase = "",
                channel = 0,
                securityType = 0,
                airPlayPort = controlSocket.localPort,
                deviceIdentifier = null,
                publicKey = null,
                sourceVersion = null,
                ipAddresses = listOf("127.0.0.1"),
            )
        val requests = CopyOnWriteArrayList<Request>()
        val videoOpcodes = CopyOnWriteArrayList<Int>()
        val videoConnected = CountDownLatch(1)
        val twoVideoMessages = CountDownLatch(2)
        private val workerErrors = CopyOnWriteArrayList<Throwable>()
        private val controlWorker: Thread
        private val videoWorker: Thread?

        init {
            if (!videoAvailable) dataSocket.close()
            controlWorker =
                Thread({
                    try {
                        controlSocket.accept().use { peer ->
                            peer.soTimeout = 6_000
                            val input = peer.getInputStream()
                            while (true) {
                                val request = readRequest(input) ?: break
                                requests.add(request.first)
                                val rq = request.first
                                val sequence = request.second
                                val responseCode: Int
                                val body: ByteArray
                                when {
                                    rq.method == "SETUP" && rq.path == "/setup" -> {
                                        responseCode = if (setupReply == SetupReply.REJECT_500) 500 else 200
                                        body =
                                            if (setupReply == SetupReply.MALFORMED_200) {
                                                "invalid-bplist".toByteArray()
                                            } else {
                                                BinaryPlist.encode(mapOf("eventPort" to 0L, "timingPort" to 0L))
                                            }
                                    }
                                    rq.method == "GET" && rq.path == "/info" -> {
                                        responseCode = 200
                                        body =
                                            BinaryPlist.encode(
                                                mapOf(
                                                    "displays" to listOf(
                                                        mapOf(
                                                            "uuid" to "simulated-display",
                                                            "widthPixels" to 1280L,
                                                            "heightPixels" to 720L,
                                                            "maxFPS" to 60L,
                                                        ),
                                                    ),
                                                ),
                                            )
                                    }
                                    rq.method == "SETUP" && rq.path == "/" -> {
                                        responseCode = 200
                                        body = BinaryPlist.encode(mapOf("streams" to listOf(mapOf("dataPort" to videoPort.toLong()))))
                                    }
                                    rq.method == "RECORD" && rq.path == "/" -> {
                                        responseCode = if (videoConnected.count == 0L) 200 else 455
                                        body = BinaryPlist.encode(emptyMap<String, Any>())
                                    }
                                    else -> {
                                        responseCode = 400
                                        body = BinaryPlist.encode(mapOf("error" to "unknown command"))
                                    }
                                }
                                val reason = if (responseCode == 200) "OK" else "Rejected"
                                peer.getOutputStream().apply {
                                    write(
                                        (
                                            "RTSP/1.0 " + responseCode + " " + reason + "\r\n" +
                                                "CSeq: " + sequence + "\r\n" +
                                                "Content-Type: application/x-apple-binary-plist\r\n" +
                                                "Content-Length: " + body.size + "\r\n\r\n"
                                        ).toByteArray(Charsets.US_ASCII),
                                    )
                                    write(body)
                                    flush()
                                }
                            }
                        }
                    } catch (_: SocketException) {
                        // Socket is closed by test cleanup.
                    } catch (error: Throwable) {
                        workerErrors.add(error)
                    }
                }, "simulated-carplay-control").also { it.isDaemon = true; it.start() }
            videoWorker =
                if (videoAvailable) {
                    Thread({
                        try {
                            dataSocket.accept().use { peer ->
                                peer.soTimeout = 5_000
                                videoConnected.countDown()
                                val input = DataInputStream(peer.getInputStream())
                                repeat(2) {
                                    val header = ByteArray(128)
                                    input.readFully(header)
                                    val length = ByteBuffer.wrap(header).order(ByteOrder.LITTLE_ENDIAN).getInt(0)
                                    require(length in 1..8192) { "Invalid CarPlay video body length" }
                                    input.readFully(ByteArray(length))
                                    videoOpcodes.add(header[4].toInt() and 0xFF)
                                    twoVideoMessages.countDown()
                                }
                            }
                        } catch (_: SocketException) {
                            // Closed before the video port was used.
                        } catch (error: Throwable) {
                            workerErrors.add(error)
                        }
                    }, "simulated-carplay-video").also { it.isDaemon = true; it.start() }
                } else {
                    null
                }
        }

        private fun readRequest(input: InputStream): Pair<Request, String>? {
            val buffer = ByteArrayOutputStream()
            var suffix = ""
            while (!suffix.endsWith("\r\n\r\n")) {
                val next = input.read()
                if (next < 0) return null
                buffer.write(next)
                suffix = (suffix + next.toChar()).takeLast(4)
                require(buffer.size() <= 16_384)
            }
            val lines = buffer.toString("ISO-8859-1").split("\r\n")
            val start = lines.first().split(' ')
            require(start.size >= 3)
            val headers =
                lines.drop(1).filter { it.contains(':') }.associate {
                    it.substringBefore(':').lowercase() to it.substringAfter(':').trim()
                }
            val length = headers["content-length"]?.toInt() ?: 0
            require(length in 0..65536)
            val body = input.readNBytes(length)
            require(body.size == length)
            val plist = if (body.isEmpty()) emptyMap<String, Any>() else BinaryPlist.parse(body) as Map<*, *>
            return Request(start[0], start[1], plist) to (headers["cseq"] ?: "1")
        }

        override fun close() {
            controlSocket.close()
            dataSocket.close()
            controlWorker.join(500)
            videoWorker?.join(500)
            assertTrue("Simulator worker raised an exception: " + workerErrors, workerErrors.isEmpty())
        }
    }
}
