package com.mcarplay.app.util

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class BluetoothIdentitySessionPolicyTest {
    @Test
    fun enteringARealAddressAfterPlaceholderWasSentNeedsFreshBtHandshake() {
        assertTrue(
            BluetoothIdentitySessionPolicy.requiresReconnect(
                DeviceIdentity.PLACEHOLDER_MAC,
                "08:B3:39:17:A5:4C",
            ),
        )
        assertTrue(BluetoothIdentitySessionPolicy.sessionUsedPlaceholder(DeviceIdentity.PLACEHOLDER_MAC))
    }

    @Test
    fun sameSessionIdentityIsNotMarkedStale() {
        assertFalse(BluetoothIdentitySessionPolicy.requiresReconnect("08:B3:39:17:A5:4C", "08:b3:39:17:a5:4c"))
        assertFalse(BluetoothIdentitySessionPolicy.sessionUsedPlaceholder("08:B3:39:17:A5:4C"))
    }

    @Test
    fun manuallyChangingValidAddressAlsoRequiresReconnect() {
        assertTrue(BluetoothIdentitySessionPolicy.requiresReconnect("08:B3:39:17:A5:4C", "08:B3:39:17:A5:4D"))
    }

    @Test
    fun noConnectionYetMeansSavedIdentityWillBeUsedAtNextStart() {
        assertFalse(BluetoothIdentitySessionPolicy.requiresReconnect(null, "08:B3:39:17:A5:4C"))
    }
}
