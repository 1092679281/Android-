package com.mcarplay.app.airplay

/**
 * After an explicit server-side SETUP 500, never silently claim an active session.
 * A guessed gateway:7000 AirPlay endpoint and no receiver invite is a weaker
 * signal than an actual 0x4301, mDNS endpoint, or fresh ctrl invite.
 *
 * Only a NEW invite can initiate a bounded retry; a late 0x4301 already has a
 * separate asynchronous path in SessionController. All other errors fail as before.
 */
internal enum class InitialSetupRecoveryAction {
    END_SESSION,
    WAIT_FOR_FRESH_CTRL_INVITE,
}

internal object InitialSetupRecoveryPolicy {
    fun afterRejectedSetup(
        statusCode: Int?,
        gatewayPortWasGuessed: Boolean,
        ctrlInvitesObserved: Int,
    ): InitialSetupRecoveryAction =
        if (statusCode == 500 && gatewayPortWasGuessed && ctrlInvitesObserved == 0) {
            InitialSetupRecoveryAction.WAIT_FOR_FRESH_CTRL_INVITE
        } else {
            InitialSetupRecoveryAction.END_SESSION
        }
}
