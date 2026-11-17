package com.mcarplay.app.util

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BluetoothIdentitySessionPolicyTest {
    @Test
    fun automaticStartRequiresRealIdentityEvenIfBenchOverrideIsSet() {
        val placeholder = DeviceIdentity.PLACEHOLDER_MAC
        assertFalse(BluetoothIdentitySessionPolicy.canStart(placeholder, automatic = true, allowPlaceholder = false))
        assertFalse(BluetoothIdentitySessionPolicy.canStart(placeholder, automatic = true, allowPlaceholder = true))
    }

    @Test
    fun manualStartRequiresRealIdentityUnlessBenchOverrideIsSelected() {
        val placeholder = DeviceIdentity.PLACEHOLDER_MAC
        assertFalse(BluetoothIdentitySessionPolicy.canStart(placeholder, automatic = false, allowPlaceholder = false))
        assertTrue(BluetoothIdentitySessionPolicy.canStart(placeholder, automatic = false, allowPlaceholder = true))
    }

    @Test
    fun savedIdentityAllowsBothManualAndAutomaticStart() {
        val saved = "10:22:33:44:55:6A"
        assertTrue(BluetoothIdentitySessionPolicy.canStart(saved, automatic = false, allowPlaceholder = false))
        assertTrue(BluetoothIdentitySessionPolicy.canStart(saved, automatic = true, allowPlaceholder = false))
    }

    @Test
    fun enteringARealAddressAfterPlaceholderWasSentNeedsFreshBtHandshake() {
        assertTrue(
            BluetoothIdentitySessionPolicy.requiresReconnect(
                DeviceIdentity.PLACEHOLDER_MAC,
                "10:22:33:44:55:6A",
            ),
        )
        assertTrue(BluetoothIdentitySessionPolicy.sessionUsedPlaceholder(DeviceIdentity.PLACEHOLDER_MAC))
    }

    @Test
    fun sameSessionIdentityIsNotMarkedStale() {
        assertFalse(BluetoothIdentitySessionPolicy.requiresReconnect("10:22:33:44:55:6A", "10:22:33:44:55:6a"))
        assertFalse(BluetoothIdentitySessionPolicy.sessionUsedPlaceholder("10:22:33:44:55:6A"))
    }

    @Test
    fun manuallyChangingValidAddressAlsoRequiresReconnect() {
        assertTrue(BluetoothIdentitySessionPolicy.requiresReconnect("10:22:33:44:55:6A", "10:22:33:44:55:6D"))
    }

    @Test
    fun noConnectionYetMeansSavedIdentityWillBeUsedAtNextStart() {
        assertFalse(BluetoothIdentitySessionPolicy.requiresReconnect(null, "10:22:33:44:55:6A"))
    }
}
