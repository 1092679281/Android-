package com.mcarplay.app.video

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class R5ForwardCadenceTest {
    @Test
    fun sixtyFpsMeasuresSenderOnly() {
        val meter = VideoFrameCadenceMeter(120)
        repeat(121) { i -> meter.recordForwardedFrame(i * 16_667L, i * 16_666_667L) }
        val measured = meter.snapshot(120 * 16_666_667L)
        assertEquals(120, measured.samples)
        assertTrue(measured.forwardedFps in 59.9..60.1)
        assertTrue(measured.p95IntervalMs in 16.6..16.8)
    }

    @Test
    fun historicFpsNeverLooksLiveAfterStall() {
        val meter = VideoFrameCadenceMeter(120)
        repeat(121) { i -> meter.recordForwardedFrame(i * 16_667L, i * 16_666_667L) }
        val last = 120 * 16_666_667L
        val stopped = meter.snapshot(last + 600_000_000L)
        assertEquals(0.0, stopped.forwardedFps, 0.001)
        assertTrue(stopped.stalled)
        assertEquals(600L, stopped.idleMs)
    }

    @Test
    fun regressionAndResets() {
        val meter = VideoFrameCadenceMeter(3)
        meter.recordForwardedFrame(100, 1_000_000_000L)
        meter.recordForwardedFrame(200, 1_016_667_000L)
        meter.recordForwardedFrame(150, 1_010_000_000L)
        meter.recordForwardedFrame(300, 1_033_334_000L)
        val stats = meter.snapshot(1_033_334_000L)
        assertEquals(1, stats.nonMonotonicClock)
        // The PTS from a rolled-back clock sample is not a valid data point.
        assertEquals(0, stats.nonMonotonicPts)
        assertEquals(2, stats.samples)
        meter.reset()
        assertEquals(0, meter.snapshot(1_033_334_000L).samples)
    }
}
