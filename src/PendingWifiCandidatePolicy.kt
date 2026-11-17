package com.mcarplay.app.net

/** Only controls whether to ASK the user. Never authorizes Wi-Fi binding or pairing. */
internal object PendingWifiCandidatePolicy {
    fun mayPrompt(
        readableSsid: Boolean,
        freshInvite: Boolean,
        selectedTarget: Boolean,
        uniqueWifi: Boolean,
    ): Boolean {
        // An SSID is only a name, not proof that this is the selected car.
        // A trusted receiver invite may ask for consent independently.
        // Without such an invite, require both a selected target and one Wi-Fi.
        if (freshInvite) return true
        return selectedTarget && uniqueWifi
    }
}
