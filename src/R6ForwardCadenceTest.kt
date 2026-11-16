package com.mcarplay.app.video

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class R6ForwardCadenceTest {
    @Test fun repeatedSecondPrecisionPtsIsNotRegression() {
        val meter = VideoFrameCadenceMeter(120)
        repeat(91) { n -> meter.recordForwardedFrame(1_763_000_000_000_000L, n * 33_333_333L) }
        val stats = meter.snapshot(90 * 33_333_333L)
        assertEquals(0, stats.nonMonotonicPts)
        assertEquals(90, stats.repeatedPts)
        assertTrue(stats.forwardedFps in 29.9..30.1)
        assertEquals(0, stats.longGaps)
    }

    @Test fun cleanThirtyFpsIsNotFlaggedAsLongGaps() {
        val meter = VideoFrameCadenceMeter()
        repeat(301) { n -> meter.recordForwardedFrame(n * 33_333L, n * 33_333_333L) }
        val stats = meter.snapshot(300 * 33_333_333L)
        assertEquals(0, stats.longGaps)
        assertTrue(stats.longGapThresholdMs > 50.0)
        assertTrue(stats.p95IntervalMs in 33.3..33.4)
    }

    @Test fun stableSixtyFpsAndStall() {
        val meter = VideoFrameCadenceMeter(120)
        repeat(121) { n -> meter.recordForwardedFrame(n * 16_667L, n * 16_666_667L) }
        val end = 120 * 16_666_667L
        assertTrue(meter.snapshot(end).forwardedFps in 59.9..60.1)
        assertEquals(0, meter.snapshot(end).longGaps)
        assertTrue(meter.snapshot(end + 600_000_000L).stalled)
        assertEquals(0.0, meter.snapshot(end + 600_000_000L).forwardedFps, 0.001)
    }

    @Test fun trueLongGapDetected() {
        val meter = VideoFrameCadenceMeter()
        var clockNs = 0L
        repeat(60) { n ->
            if (n > 0) clockNs += if (n == 30) 130_000_000L else 33_333_333L
            meter.recordForwardedFrame(n * 33_333L, clockNs)
        }
        assertTrue(meter.snapshot(clockNs).longGaps >= 1)
    }

    @Test fun clockRollbackDoesNotCorruptPts() {
        val meter = VideoFrameCadenceMeter()
        meter.recordForwardedFrame(100, 1_000_000_000L)
        meter.recordForwardedFrame(0, 900_000_000L)
        meter.recordForwardedFrame(200, 1_016_000_000L)
        val s = meter.snapshot(1_016_000_000L)
        assertEquals(1, s.nonMonotonicClock)
        assertEquals(0, s.nonMonotonicPts)
        assertEquals(1, s.samples)
    }

    @Test fun resetClearsPriorSession() {
        val meter = VideoFrameCadenceMeter()
        meter.recordForwardedFrame(100, 1_000_000_000L)
        meter.recordForwardedFrame(100, 1_016_666_667L)
        assertEquals(1, meter.snapshot(1_016_666_667L).repeatedPts)
        meter.reset()
        assertEquals(0, meter.snapshot(2_000_000_000L).repeatedPts)
        assertEquals(0, meter.snapshot(2_000_000_000L).samples)
    }
}
