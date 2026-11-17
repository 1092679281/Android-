package com.mcarplay.app.airplay

import org.junit.Assert.assertEquals
import org.junit.Test

class InitialSetupRecoveryPolicyTest {
    @Test
    fun saicGmE2lbTraceWaitsForFreshInviteInsteadOfBlindRepeatingSetup() {
        assertEquals(
            InitialSetupRecoveryAction.WAIT_FOR_FRESH_CTRL_INVITE,
            InitialSetupRecoveryPolicy.afterRejectedSetup(500, true, 0),
        )
    }

    @Test
    fun authenticatedEndpointDoesNotGetBlindRetryRule() {
        assertEquals(
            InitialSetupRecoveryAction.END_SESSION,
            InitialSetupRecoveryPolicy.afterRejectedSetup(500, false, 0),
        )
    }

    @Test
    fun alreadyInvitedSessionDoesNotRepeatOnSameChannel() {
        assertEquals(
            InitialSetupRecoveryAction.END_SESSION,
            InitialSetupRecoveryPolicy.afterRejectedSetup(500, true, 1),
        )
    }

    @Test
    fun forbiddenOrBadRequestIsNotReclassifiedAsNotYetInvited() {
        for (code in listOf(null, 400, 401, 403, 404, 455, 503, 200)) {
            assertEquals(
                "$code",
                InitialSetupRecoveryAction.END_SESSION,
                InitialSetupRecoveryPolicy.afterRejectedSetup(code, true, 0),
            )
        }
    }
}
