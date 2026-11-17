package com.mcarplay.app.video

import org.junit.Assert.assertEquals
import org.junit.Test

class VideoQueueDelayMeterTest {
    @Test fun p95MeasuresSenderQueueOnly() {
        val meter = VideoQueueDelayMeter(20)
        repeat(20) { i -> meter.record(0L, (i + 1L) * 1_000_000L) }
        assertEquals(19L, meter.p95Ms())
    }

    @Test fun ignoresClockRollbackAndAllowsReset() {
        val meter = VideoQueueDelayMeter()
        meter.record(100L, 99L)
        assertEquals(0L, meter.p95Ms())
        meter.record(0L, 10_000_000L)
        assertEquals(10L, meter.p95Ms())
        meter.reset()
        assertEquals(0L, meter.p95Ms())
    }
}
