package com.mcarplay.app.video

import org.junit.Assert.assertEquals
import org.junit.Test

class SourceFpsPolicyTest {
    @Test
    fun explicit60WhenReceiverCanAccept60() {
        assertEquals(60, SourceFpsPolicy.effective(60, 60))
        assertEquals(60, SourceFpsPolicy.effective(60, 120))
    }

    @Test
    fun receiverLimitWins() {
        assertEquals(30, SourceFpsPolicy.effective(60, 30))
        assertEquals(45, SourceFpsPolicy.effective(60, 45))
        assertEquals(24, SourceFpsPolicy.effective(30, 24))
    }

    @Test
    fun missingReceiverReportDoesNotAssumeItSupports60() {
        assertEquals(60, SourceFpsPolicy.effective(60, 0))
        assertEquals(30, SourceFpsPolicy.effective(30, -1))
        assertEquals(30, SourceFpsPolicy.effective(30, 999))
    }

    @Test
    fun safeDefaultIs30() {
        assertEquals(30, SourceFpsPolicy.effective(30, 60))
    }
}
