package com.mcarplay.app.airplay

import com.mcarplay.app.iap2.Iap2SenderSession
import com.mcarplay.app.iap2.ReceiverProfile
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicBoolean
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread

/** Real loopback RTSP tests for state-changing SETUP/RECORD/TEARDOWN ordering. */
class AirPlayScreenLifecycleConcurrencyTest {
    @Test
    fun screenTeardownWaitsForAnInFlightScreenSetupResponse() {
        AirPlayRecordLifecycleTest.Peer().use { peer ->
            val setupEntered = CountDownLatch(1)
            val releaseSetup = CountDownLatch(1)
            val teardownSeen = CountDownLatch(1)
            peer.reply = { request ->
                when {
                    request.method == "SETUP" && request.path == "/setup" ->
                        request.respond(200, initialSetupBody())
                    request.path == "/info" ->
                        request.respond(200, infoBody())
                    request.method == "SETUP" && request.path == "/" -> {
                        setupEntered.countDown()
                        check(releaseSetup.await(5, TimeUnit.SECONDS))
                        request.respond(200, screenSetupBody())
                    }
                    request.method == "TEARDOWN" -> {
                        teardownSeen.countDown()
                        request.respond(200)
                    }
                    else -> request.respond(200)
                }
            }
            val client = newClient(peer.port)
            try {
                client.enableActivationGate()
                assertTrue(client.reconnect())
                val setup = requireNotNull(client.runSetup())
                assertTrue(setup.displayUuid == "screen-0")

                val screenResult = AtomicReference<AirPlayClient.ScreenStreamInfo?>()
                val screenThread = thread {
                    screenResult.set(client.runScreenStream(null, setup.displayUuid))
                }
                assertTrue(setupEntered.await(2, TimeUnit.SECONDS))

                val teardownStarted = CountDownLatch(1)
                val teardownDone = CountDownLatch(1)
                val teardownResult = AtomicBoolean(false)
                val teardownThread = thread {
                    teardownStarted.countDown()
                    teardownResult.set(client.teardownScreenStream())
                    teardownDone.countDown()
                }
                assertTrue(teardownStarted.await(1, TimeUnit.SECONDS))
                // A teardown must not observe a missing UUID while its SETUP is still in flight.
                assertFalse(teardownDone.await(150, TimeUnit.MILLISECONDS))

                releaseSetup.countDown()
                screenThread.join(3_000)
                assertNotNull(screenResult.get())
                assertTrue(teardownDone.await(2, TimeUnit.SECONDS))
                teardownThread.join(1_000)
                assertTrue(teardownResult.get())
                assertTrue(teardownSeen.await(1, TimeUnit.SECONDS))
            } finally {
                releaseSetup.countDown()
                client.close()
            }
        }
    }

    @Test
    fun screenTeardownWaitsForInFlightRecordResponse() {
        AirPlayRecordLifecycleTest.Peer().use { peer ->
            val recordEntered = CountDownLatch(1)
            val releaseRecord = CountDownLatch(1)
            val teardownSeen = CountDownLatch(1)
            peer.reply = { request ->
                when {
                    request.method == "SETUP" && request.path == "/setup" ->
                        request.respond(200, initialSetupBody())
                    request.path == "/info" ->
                        request.respond(200, infoBody())
                    request.method == "SETUP" && request.path == "/" ->
                        request.respond(200, screenSetupBody())
                    request.method == "RECORD" -> {
                        recordEntered.countDown()
                        check(releaseRecord.await(5, TimeUnit.SECONDS))
                        request.respond(200)
                    }
                    request.method == "TEARDOWN" -> {
                        teardownSeen.countDown()
                        request.respond(200)
                    }
                    else -> request.respond(200)
                }
            }
            val client = newClient(peer.port)
            try {
                client.enableActivationGate()
                assertTrue(client.reconnect())
                val setup = requireNotNull(client.runSetup())
                assertNotNull(client.runScreenStream(null, setup.displayUuid))
                assertTrue(client.confirmVideoDataPortConnected())

                val recordResult = AtomicBoolean(false)
                val recordDone = CountDownLatch(1)
                val recordThread = thread {
                    recordResult.set(client.record())
                    recordDone.countDown()
                }
                assertTrue(recordEntered.await(2, TimeUnit.SECONDS))

                val teardownDone = CountDownLatch(1)
                val teardownResult = AtomicBoolean(false)
                val teardownThread = thread {
                    teardownResult.set(client.teardownScreenStream())
                    teardownDone.countDown()
                }
                assertFalse(teardownDone.await(150, TimeUnit.MILLISECONDS))

                releaseRecord.countDown()
                assertTrue(recordDone.await(2, TimeUnit.SECONDS))
                recordThread.join(1_000)
                assertTrue(recordResult.get())
                assertTrue(teardownDone.await(2, TimeUnit.SECONDS))
                teardownThread.join(1_000)
                assertTrue(teardownResult.get())
                assertTrue(teardownSeen.await(1, TimeUnit.SECONDS))
            } finally {
                releaseRecord.countDown()
                client.close()
            }
        }
    }

    private fun newClient(port: Int): AirPlayClient {
        val endpoint =
            Iap2SenderSession.CarPlayEndpoint(
                ssid = "test",
                passphrase = "",
                channel = 0,
                securityType = 0,
                airPlayPort = port,
                deviceIdentifier = null,
                publicKey = null,
                sourceVersion = null,
                ipAddresses = listOf("127.0.0.1"),
                receiverSignals = ReceiverProfile.Signals(),
            )
        return AirPlayClient(endpoint, log = {})
    }

    private fun initialSetupBody(): ByteArray =
        BinaryPlist.encode(
            linkedMapOf(
                "eventPort" to 0L,
                "timingPort" to 0L,
                "keepAlivePort" to 0L,
                "enabledFeatures" to emptyList<String>(),
            ),
        )

    private fun infoBody(): ByteArray =
        BinaryPlist.encode(
            linkedMapOf(
                "displays" to
                    listOf(
                        linkedMapOf(
                            "widthPixels" to 1920L,
                            "heightPixels" to 720L,
                            "maxFPS" to 60L,
                            "uuid" to "screen-0",
                        ),
                    ),
                "hidDevices" to emptyList<Any>(),
                "audioFormats" to emptyList<Any>(),
            ),
        )

    private fun screenSetupBody(): ByteArray =
        BinaryPlist.encode(
            linkedMapOf(
                "streams" to listOf(linkedMapOf("dataPort" to 45678L)),
            ),
        )
}
