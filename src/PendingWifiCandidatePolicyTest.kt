package com.mcarplay.app.net

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PendingWifiCandidatePolicyTest {
    @Test
    fun unknownSsidAndSingleWifiWithExplicitCarCanPromptForConsent() {
        assertTrue(PendingWifiCandidatePolicy.mayPrompt(false, false, true, true))
    }

    @Test
    fun noSelectedCarOrSeveralWifiNetworksCannotPromptBlindly() {
        assertFalse(PendingWifiCandidatePolicy.mayPrompt(false, false, false, true))
        assertFalse(PendingWifiCandidatePolicy.mayPrompt(false, false, true, false))
    }

    @Test
    fun observedNameOrFreshCarInvitePreservesOriginalPromptBehavior() {
        assertTrue(PendingWifiCandidatePolicy.mayPrompt(true, false, false, false))
        assertTrue(PendingWifiCandidatePolicy.mayPrompt(false, true, false, false))
    }
}
