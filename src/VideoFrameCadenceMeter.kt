package com.mcarplay.app.video

import java.util.ArrayDeque
import kotlin.math.ceil

/**
 * Measures successfully forwarded video frames only.
 * NOT actual head-unit display / VSYNC fps.
 */
class VideoFrameCadenceMeter(private val windowSize: Int = 300) {
    init { require(windowSize in 2..3600) }

    data class Snapshot(
        val samples: Int,
        val forwardedFps: Double,
        val p95IntervalMs: Double,
        val longGaps: Int,
        val nonMonotonicPts: Int,
        val nonMonotonicClock: Int,
        val idleMs: Long,
        val stalled: Boolean,
    )

    private val intervalsMs = ArrayDeque<Double>()
    private var lastClockNs: Long? = null
    private var lastPtsUs: Long? = null
    private var nonMonotonicPts = 0
    private var nonMonotonicClock = 0

    @Synchronized
    fun recordForwardedFrame(ptsUs: Long, clockNs: Long) {
        val previousPts = lastPtsUs
        if (previousPts != null && ptsUs <= previousPts) nonMonotonicPts++
        lastPtsUs = ptsUs
        val previousClock = lastClockNs
        if (previousClock != null && clockNs <= previousClock) {
            nonMonotonicClock++
            return
        }
        if (previousClock != null) {
            intervalsMs.addLast((clockNs - previousClock) / 1_000_000.0)
            if (intervalsMs.size > windowSize) intervalsMs.removeFirst()
        }
        lastClockNs = clockNs
    }

    @Synchronized
    fun snapshot(nowNs: Long = System.nanoTime()): Snapshot {
        val last = lastClockNs
        val idleMs = if (last == null) 0L else ((nowNs - last).coerceAtLeast(0L)) / 1_000_000L
        if (intervalsMs.isEmpty()) {
            return Snapshot(0, 0.0, 0.0, 0, nonMonotonicPts, nonMonotonicClock, idleMs, false)
        }
        val stalled = idleMs >= STALL_THRESHOLD_MS
        val sorted = intervalsMs.sorted()
        val p95Index = ceil(sorted.size * 0.95).toInt().coerceIn(1, sorted.size) - 1
        val fps = intervalsMs.size * 1000.0 / intervalsMs.sum()
        return Snapshot(
            intervalsMs.size,
            if (stalled) 0.0 else fps,
            sorted[p95Index],
            intervalsMs.count { it > 25.0 },
            nonMonotonicPts,
            nonMonotonicClock,
            idleMs,
            stalled,
        )
    }

    @Synchronized
    fun reset() {
        intervalsMs.clear()
        lastClockNs = null
        lastPtsUs = null
        nonMonotonicPts = 0
        nonMonotonicClock = 0
    }

    companion object {
        const val STALL_THRESHOLD_MS = 500L
    }
}
