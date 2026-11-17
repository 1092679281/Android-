package com.mcarplay.app.airplay

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class AirPlayActivationStateTest {
    @Test
    fun onlyExactRtsp200IsSuccessful() {
        assertEquals(200, AirPlayRtspStatus.code("RTSP/1.0 200 OK"))
        assertTrue(AirPlayRtspStatus.accepted("RTSP/1.0 200 OK"))
        assertTrue(AirPlayRtspStatus.accepted("HTTP/1.1 200"))
        assertFalse(AirPlayRtspStatus.accepted("RTSP/1.0 403 200 OK"))
        assertFalse(AirPlayRtspStatus.accepted("RTSP/1.0 2000 Invalid"))
        assertFalse(AirPlayRtspStatus.accepted("RTSP/1.0 455 Method Not Valid 200"))
        assertFalse(AirPlayRtspStatus.accepted("garbage 200 OK"))
        assertFalse(AirPlayRtspStatus.accepted(""))
    }

    @Test
    fun cannotRecordBeforeBothSetupAndActualTcpConnect() {
        val state = AirPlayActivationState()
        assertFalse(state.canSetupScreen())
        assertFalse(state.canRecord())
        assertFalse(state.videoDataConnected())
        assertFalse(state.onRecordReply("RTSP/1.0 200 OK", true))

        state.sessionSetupAccepted()
        assertEquals(AirPlayActivationState.Stage.SESSION_SETUP_ACCEPTED, state.stage)
        assertTrue(state.canSetupScreen())
        assertFalse(state.canRecord())

        assertTrue(state.screenSetupAccepted())
        assertEquals(AirPlayActivationState.Stage.SCREEN_SETUP_ACCEPTED, state.stage)
        assertFalse(state.canRecord())
        assertFalse(state.onRecordReply("RTSP/1.0 200 OK", true))

        assertTrue(state.videoDataConnected())
        assertTrue(state.canRecord())
        assertFalse(state.onRecordReply("RTSP/1.0 403 Forbidden", true))
        assertEquals(AirPlayActivationState.Stage.DATA_PORT_CONNECTED, state.stage)
        assertFalse(state.onRecordReply("RTSP/1.0 200 OK", false))
        assertTrue(state.onRecordReply("RTSP/1.0 200 OK", true))
        assertEquals(AirPlayActivationState.Stage.RECORD_ACCEPTED, state.stage)
    }

    @Test
    fun lateScreenRecoveryMustReconnectBeforeForceRecord() {
        val state = AirPlayActivationState()
        state.sessionSetupAccepted()
        state.screenSetupAccepted()
        state.videoDataConnected()
        state.onRecordReply("RTSP/1.0 200 OK", true)

        state.screenTornDown()
        assertFalse(state.canRecord())
        assertTrue(state.screenSetupAccepted())
        assertFalse(state.canRecord())
        assertTrue(state.videoDataConnected())
        assertTrue(state.canRecord())
        assertTrue(state.onRecordReply("RTSP/1.0 200 OK", true))
    }

    @Test
    fun resetOnClosedOrReplacedControlConnection() {
        val state = AirPlayActivationState()
        state.sessionSetupAccepted()
        state.screenSetupAccepted()
        state.videoDataConnected()
        state.onRecordReply("RTSP/1.0 200 OK", true)
        state.reset()
        assertEquals(AirPlayActivationState.Stage.NEED_SESSION_SETUP, state.stage)
        assertFalse(state.canRecord())
        assertFalse(state.screenSetupAccepted())
    }

    @Test
    fun legacyAudioRepeatRecordDoesNotDegradeAcceptedSession() {
        val state = AirPlayActivationState()
        state.sessionSetupAccepted()
        state.screenSetupAccepted()
        state.videoDataConnected()
        assertTrue(state.onRecordReply("RTSP/1.0 200 OK", true))
        assertTrue(state.canRecord())
        assertFalse(state.onRecordReply("RTSP/1.0 455 Busy", true))
        assertTrue(state.canRecord())
        assertEquals(AirPlayActivationState.Stage.RECORD_ACCEPTED, state.stage)
    }
}
