package com.mcarplay.app.util

/**
 * Bluetooth address included in a live iAP2 session and CarPlay ctrl TXT is
 * immutable for that session. Changing user settings later does not rewrite
 * the already-sent 0x4300 or 0x4e0e.
 */
internal object BluetoothIdentitySessionPolicy {
    fun canStart(
        mac: String,
        automatic: Boolean,
        allowPlaceholder: Boolean,
    ): Boolean = !sessionUsedPlaceholder(mac) || (!automatic && allowPlaceholder)

    fun requiresReconnect(sessionMac: String?, savedMac: String): Boolean =
        sessionMac != null && !sessionMac.equals(savedMac, ignoreCase = true)

    fun sessionUsedPlaceholder(sessionMac: String?): Boolean =
        sessionMac == DeviceIdentity.PLACEHOLDER_MAC
}
