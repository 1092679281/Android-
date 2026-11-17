package com.mcarplay.app.iap2

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class CarPlayBringupStateTest {
    @Test
    fun responseDoesNotMeanCryptographicAuthentication() {
        val state = CarPlayBringupState()
        state.onLinkReady()
        state.onIdentified()
        assertEquals(
            MfiNextAction.SEND_UNVERIFIED_AUTH_SIGNAL,
            state.onMfiEvidence(MfiChallengeEvidence.RESPONSE_UNVERIFIED, linkAlive = true),
        )
        state.onAuthSignalSent()
        assertEquals(CarPlayBringupState.Stage.AUTH_SIGNAL_SENT_UNVERIFIED, state.stage)
        assertEquals(MfiChallengeEvidence.RESPONSE_UNVERIFIED, state.mfiEvidence)
    }

    @Test
    fun explicitMfiRejectionAndDisconnectAbortWithoutAuthSignal() {
        for (evidence in listOf(MfiChallengeEvidence.EXPLICITLY_REJECTED, MfiChallengeEvidence.LINK_LOST)) {
            val state = CarPlayBringupState()
            state.onLinkReady()
            state.onIdentified()
            assertEquals(MfiNextAction.ABORT, state.onMfiEvidence(evidence, linkAlive = true))
            assertEquals(CarPlayBringupState.Stage.FAILED, state.stage)
        }
        assertEquals(
            MfiNextAction.ABORT,
            MfiEvidencePolicy.decide(MfiChallengeEvidence.TIMED_OUT, linkAlive = false),
        )
    }

    @Test
    fun silentTimeoutIsAnExplicitlyUnverifiedCompatibilityAttempt() {
        val state = CarPlayBringupState()
        state.onLinkReady()
        state.onIdentified()
        assertEquals(
            MfiNextAction.SEND_UNVERIFIED_AUTH_SIGNAL,
            state.onMfiEvidence(MfiChallengeEvidence.TIMED_OUT, linkAlive = true),
        )
        state.onAuthSignalSent()
        assertEquals(CarPlayBringupState.Stage.AUTH_SIGNAL_SENT_UNVERIFIED, state.stage)
    }

    @Test
    fun cannotProcessEndpointBeforeAuthSignal() {
        val state = CarPlayBringupState()
        state.onLinkReady()
        state.onIdentified()
        var rejected = false
        try {
            state.observeEndpoint("car", CarPlayEndpointRoute.DIRECT_AFTER_WIFI_BIND)
        } catch (_: IllegalStateException) {
            rejected = true
        }
        assertTrue(rejected)
    }

    @Test
    fun endpointNeedsWifiEvidenceAndValidPort() {
        fun route(ssid: String, hasNetwork: Boolean, port: Int, hasAddress: Boolean) =
            CarPlayEndpointRoutePolicy.classify(ssid, hasNetwork, port, hasAddress)
        assertEquals(
            CarPlayEndpointRoute.WAIT_FOR_WIFI_EVIDENCE,
            route("", false, 7000, true),
        )
        assertEquals(
            CarPlayEndpointRoute.WAIT_FOR_WIFI_EVIDENCE,
            route("untrusted", false, 7000, true),
        )
        assertEquals(
            CarPlayEndpointRoute.DISCOVER_AFTER_WIFI_BIND,
            route("car", true, 0, false),
        )
        assertEquals(
            CarPlayEndpointRoute.DISCOVER_AFTER_WIFI_BIND,
            route("car", true, 65536, true),
        )
        assertEquals(
            CarPlayEndpointRoute.DISCOVER_AFTER_WIFI_BIND,
            route("car", true, 7000, false),
        )
        assertEquals(
            CarPlayEndpointRoute.DIRECT_AFTER_WIFI_BIND,
            route("car", true, 7000, true),
        )
    }

    @Test
    fun lateEndpointCanUpgradeButNotDowngradeSameCar() {
        val state = CarPlayBringupState()
        state.onLinkReady()
        state.onIdentified()
        state.onMfiEvidence(MfiChallengeEvidence.RESPONSE_UNVERIFIED, linkAlive = true)
        state.onAuthSignalSent()
        assertTrue(state.observeEndpoint("", CarPlayEndpointRoute.WAIT_FOR_WIFI_EVIDENCE))
        assertEquals(CarPlayBringupState.Stage.WAITING_ENDPOINT, state.stage)
        assertTrue(state.observeEndpoint("car", CarPlayEndpointRoute.DISCOVER_AFTER_WIFI_BIND))
        assertTrue(state.observeEndpoint("car", CarPlayEndpointRoute.DIRECT_AFTER_WIFI_BIND))
        assertFalse(state.observeEndpoint("car", CarPlayEndpointRoute.DISCOVER_AFTER_WIFI_BIND))
        assertEquals(CarPlayBringupState.Stage.DIRECT_ENDPOINT_AVAILABLE, state.stage)
        // Same session but the receiver changes hotspot: permit a new, lower-certainty handoff.
        assertTrue(state.observeEndpoint("car-new", CarPlayEndpointRoute.DISCOVER_AFTER_WIFI_BIND))
        assertEquals(CarPlayBringupState.Stage.DISCOVERING_ENDPOINT, state.stage)
    }
}
