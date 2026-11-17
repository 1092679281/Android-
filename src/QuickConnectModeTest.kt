package com.mcarplay.app.bt

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class QuickConnectModeTest {
    @Test
    fun firstLaunchAsks() {
        assertTrue(QuickConnectMode.needsFirstTimeChoice(null))
        assertFalse(QuickConnectMode.forAutomatic(null))
    }

    @Test
    fun rememberedVideoOnlyStaysSilent() {
        assertFalse(QuickConnectMode.needsFirstTimeChoice(false))
        assertFalse(QuickConnectMode.forAutomatic(false))
    }

    @Test
    fun rememberedAudioCanBeReused() {
        assertFalse(QuickConnectMode.needsFirstTimeChoice(true))
        assertTrue(QuickConnectMode.forAutomatic(true))
    }
}
