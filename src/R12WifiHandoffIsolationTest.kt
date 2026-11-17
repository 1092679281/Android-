package com.mcarplay.app.iap2

import org.junit.Assert.assertEquals
import org.junit.Test

class R12WifiHandoffIsolationTest {
    @Test
    fun merelySeeingWifiNeverCountsAsCarOwnership() {
        assertEquals(
            WifiHandoffAction.WAIT,
            WifiHandoffPolicy.decide(
                source = WifiCredentialSource.NONE,
                targetCurrent = true,
                liveSsidMatches = null,
                liveWifiPresent = true,
                freshInvite = false,
                cachedCredentials = false,
            ),
        )
    }

    @Test
    fun previousCarCannotHijackNewTarget() {
        assertEquals(
            WifiHandoffAction.IGNORE,
            WifiHandoffPolicy.decide(
                source = WifiCredentialSource.KNOWN_SSID,
                targetCurrent = false,
                liveSsidMatches = true,
                liveWifiPresent = true,
                freshInvite = true,
                cachedCredentials = true,
            ),
        )
    }

    @Test
    fun actualReceiverInviteCanBindCurrentWifi() {
        assertEquals(
            WifiHandoffAction.BIND_CURRENT,
            WifiHandoffPolicy.decide(
                source = WifiCredentialSource.NONE,
                targetCurrent = true,
                liveSsidMatches = null,
                liveWifiPresent = true,
                freshInvite = true,
                cachedCredentials = false,
            ),
        )
    }

    @Test
    fun matchingOnlyAStoredNameStillRequiresVerificationOrConsent() {
        assertEquals(
            WifiHandoffAction.ASK_CONFIRM_CURRENT,
            WifiHandoffPolicy.decide(
                source = WifiCredentialSource.KNOWN_SSID,
                targetCurrent = true,
                liveSsidMatches = null,
                liveWifiPresent = true,
                freshInvite = false,
                cachedCredentials = false,
            ),
        )
    }
}
