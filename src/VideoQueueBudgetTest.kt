package com.mcarplay.app.video

import org.junit.Assert.assertEquals
import org.junit.Test

class VideoQueueBudgetTest {
    @Test fun normalRates() {
        assertEquals(9, VideoQueueBudget.capacity(30))
        assertEquals(18, VideoQueueBudget.capacity(60))
    }
    @Test fun capUnreasonableRates() {
        assertEquals(6, VideoQueueBudget.capacity(0))
        assertEquals(18, VideoQueueBudget.capacity(120))
        assertEquals(24, VideoQueueBudget.capacity(60, 1_000))
    }
    @Test(expected = IllegalArgumentException::class)
    fun rejectInvalidDelay() {
        VideoQueueBudget.capacity(30, 0)
    }
}
