package com.mcarplay.app.airplay

/**
 * Evidence from RTSP responses is deliberately narrower than "video on head unit".
 * A 200 response means the corresponding request was accepted, not that a frame was displayed.
 */
internal object AirPlayRtspStatus {
    private val status = Regex("^(?:RTSP|HTTP)/\\d+(?:\\.\\d+)?\\s+(\\d{3})(?:\\s|$)")

    fun code(line: String): Int? =
        status.find(line.trim())?.groupValues?.get(1)?.toIntOrNull()

    fun accepted(line: String): Boolean = code(line) == 200
}

/**
 * Sender-side activation evidence in protocol order. Each step must be confirmed before
 * proceeding to the next; an attempted TCP connect is not a connected video stream.
 *
 * This does not bypass pairing, network identity, or the existing receiver-specific
 * single-RECORD rules. It contains no hardware-backed Apple identity assertion.
 */
internal class AirPlayActivationState {
    enum class Stage {
        NEED_SESSION_SETUP,
        SESSION_SETUP_ACCEPTED,
        SCREEN_SETUP_ACCEPTED,
        DATA_PORT_CONNECTED,
        RECORD_ACCEPTED,
    }

    var stage = Stage.NEED_SESSION_SETUP
        private set

    @Synchronized
    fun reset() {
        stage = Stage.NEED_SESSION_SETUP
    }

    @Synchronized
    fun sessionSetupAccepted() {
        stage = Stage.SESSION_SETUP_ACCEPTED
    }

    @Synchronized
    fun canSetupScreen(): Boolean =
        stage == Stage.SESSION_SETUP_ACCEPTED ||
            stage == Stage.RECORD_ACCEPTED // screen can be torn down/reconfigured

    @Synchronized
    fun screenSetupAccepted(): Boolean {
        if (!canSetupScreen()) return false
        stage = Stage.SCREEN_SETUP_ACCEPTED
        return true
    }

    @Synchronized
    fun videoDataConnected(): Boolean {
        if (stage != Stage.SCREEN_SETUP_ACCEPTED) return false
        stage = Stage.DATA_PORT_CONNECTED
        return true
    }

    @Synchronized
    fun canRecord(): Boolean =
        stage == Stage.DATA_PORT_CONNECTED ||
            stage == Stage.RECORD_ACCEPTED // legacy optional audio re-RECORD

    @Synchronized
    fun onRecordReply(statusLine: String, liveConnection: Boolean): Boolean {
        if (!canRecord() || !liveConnection || !AirPlayRtspStatus.accepted(statusLine)) return false
        stage = Stage.RECORD_ACCEPTED
        return true
    }

    /** Screen re-SETUP after returning to CarPlay requires a NEW data socket and RECORD. */
    @Synchronized
    fun screenTornDown() {
        if (stage != Stage.NEED_SESSION_SETUP) stage = Stage.SESSION_SETUP_ACCEPTED
    }
}
