package com.mcarplay.app.net

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class R12WifiNetworkSelectionTest {
    private val wifi: (String) -> Boolean = { it.startsWith("wifi:") }

    @Test
    fun cellularDefaultWithOneCarWifiSelectsOnlyThatWifi() {
        assertEquals(
            "wifi:buick",
            WifiCarPlayConnector.chooseWifiNetworkTarget(null, "cell:5g", listOf("cell:5g", "wifi:buick"), wifi),
        )
    }

    @Test
    fun ambiguousTwoWifiNetworksDoNotAutoSelect() {
        assertNull(
            WifiCarPlayConnector.chooseWifiNetworkTarget(null, "cell:5g", listOf("wifi:home", "wifi:buick"), wifi),
        )
    }

    @Test
    fun establishedBindingWinsAndActiveWifiIsPreserved() {
        assertEquals(
            "wifi:car",
            WifiCarPlayConnector.chooseWifiNetworkTarget("wifi:car", "wifi:home", listOf("wifi:car", "wifi:home"), wifi),
        )
        assertEquals(
            "wifi:active",
            WifiCarPlayConnector.chooseWifiNetworkTarget("gone:old", "wifi:active", listOf("wifi:other"), wifi),
        )
    }

    @Test
    fun noWifiFoundDoesNotCreateOne() {
        assertNull(WifiCarPlayConnector.chooseWifiNetworkTarget(null, "cell:5g", listOf("cell:5g"), wifi))
    }
}
