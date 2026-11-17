package com.mcarplay.app.iap2

/**
 * Evidence about the accessory's MFi challenge exchange, NOT a certificate/signature
 * verification result. In particular, 0xAA03 being present does not make this an iPhone.
 */
internal enum class MfiChallengeEvidence {
    RESPONSE_UNVERIFIED,
    EXPLICITLY_REJECTED,
    TIMED_OUT,
    LINK_LOST,
}

internal enum class MfiNextAction {
    /** Compatibility-only 0xAA05. Never interpret this as verified MFi authentication. */
    SEND_UNVERIFIED_AUTH_SIGNAL,
    ABORT,
}

internal object MfiEvidencePolicy {
    fun decide(evidence: MfiChallengeEvidence, linkAlive: Boolean): MfiNextAction =
        if (!linkAlive ||
            evidence == MfiChallengeEvidence.LINK_LOST ||
            evidence == MfiChallengeEvidence.EXPLICITLY_REJECTED
        ) {
            MfiNextAction.ABORT
        } else {
            MfiNextAction.SEND_UNVERIFIED_AUTH_SIGNAL
        }
}

/**
 * Describes the next endpoint step, not permission to bind a Wi-Fi network.
 * Network authorization remains exclusively with WifiHandoffPolicy.
 */
internal enum class CarPlayEndpointRoute {
    WAIT_FOR_WIFI_EVIDENCE,
    DISCOVER_AFTER_WIFI_BIND,
    DIRECT_AFTER_WIFI_BIND,
}

internal object CarPlayEndpointRoutePolicy {
    fun validPort(port: Int): Boolean = port in 1..65535

    fun classify(
        ssid: String,
        networkIdentityAvailable: Boolean,
        port: Int,
        hasUsableAddress: Boolean,
    ): CarPlayEndpointRoute =
        when {
            ssid.isBlank() || !networkIdentityAvailable -> CarPlayEndpointRoute.WAIT_FOR_WIFI_EVIDENCE
            validPort(port) && hasUsableAddress -> CarPlayEndpointRoute.DIRECT_AFTER_WIFI_BIND
            else -> CarPlayEndpointRoute.DISCOVER_AFTER_WIFI_BIND
        }
}

/**
 * Evidence-driven iAP2 bring-up state machine. It tracks what was observed/sent;
 * it never equates a locally sent 0xAA05 with peer acceptance.
 *
 * The AirPlay TCP/SETUP/RECORD stages are tracked separately in ConnectionTimeline.
 */
internal class CarPlayBringupState {
    internal enum class Stage {
        WAIT_LINK,
        LINK_READY,
        IDENTIFIED,
        CHALLENGE_OBSERVED,
        AUTH_SIGNAL_SENT_UNVERIFIED,
        WAITING_ENDPOINT,
        DISCOVERING_ENDPOINT,
        DIRECT_ENDPOINT_AVAILABLE,
        FAILED,
    }

    var stage: Stage = Stage.WAIT_LINK
        private set

    var mfiEvidence: MfiChallengeEvidence? = null
        private set

    private var acceptedSsid: String? = null
    private var acceptedRoute: CarPlayEndpointRoute? = null

    fun onLinkReady() {
        check(stage == Stage.WAIT_LINK) { "Link already advanced: $stage" }
        stage = Stage.LINK_READY
    }

    fun onIdentified() {
        check(stage == Stage.LINK_READY) { "Identification out of order: $stage" }
        stage = Stage.IDENTIFIED
    }

    fun onMfiEvidence(evidence: MfiChallengeEvidence, linkAlive: Boolean): MfiNextAction {
        check(stage == Stage.IDENTIFIED) { "MFi result out of order: $stage" }
        mfiEvidence = evidence
        val action = MfiEvidencePolicy.decide(evidence, linkAlive)
        stage = if (action == MfiNextAction.ABORT) Stage.FAILED else Stage.CHALLENGE_OBSERVED
        return action
    }

    fun onAuthSignalSent() {
        check(stage == Stage.CHALLENGE_OBSERVED) { "0xAA05 must follow challenge evidence: $stage" }
        stage = Stage.AUTH_SIGNAL_SENT_UNVERIFIED
    }

    /**
     * Late incomplete 0x4301 retransmissions must not downgrade a previously
     * complete endpoint for the same SSID. A changed SSID can begin a new handoff.
     * Returns false only when the stale/downgraded observation is ignored.
     */
    fun observeEndpoint(ssid: String, route: CarPlayEndpointRoute): Boolean {
        check(
            stage == Stage.AUTH_SIGNAL_SENT_UNVERIFIED ||
                stage == Stage.WAITING_ENDPOINT ||
                stage == Stage.DISCOVERING_ENDPOINT ||
                stage == Stage.DIRECT_ENDPOINT_AVAILABLE,
        ) { "Endpoint before authorization signal: $stage" }
        if (acceptedSsid == ssid && acceptedRoute != null &&
            route.ordinal < acceptedRoute!!.ordinal
        ) {
            return false
        }
        acceptedSsid = ssid
        acceptedRoute = route
        stage =
            when (route) {
                CarPlayEndpointRoute.WAIT_FOR_WIFI_EVIDENCE -> Stage.WAITING_ENDPOINT
                CarPlayEndpointRoute.DISCOVER_AFTER_WIFI_BIND -> Stage.DISCOVERING_ENDPOINT
                CarPlayEndpointRoute.DIRECT_AFTER_WIFI_BIND -> Stage.DIRECT_ENDPOINT_AVAILABLE
            }
        return true
    }
}
