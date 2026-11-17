package com.mcarplay.app.net

/** Only controls whether to ASK the user. Never authorizes Wi-Fi binding or pairing. */
internal object PendingWifiCandidatePolicy {
    fun mayPrompt(
        readableSsid: Boolean,
        freshInvite: Boolean,
        selectedTarget: Boolean,
        uniqueWifi: Boolean,
    ): Boolean = readableSsid || freshInvite || (selectedTarget && uniqueWifi)
}
