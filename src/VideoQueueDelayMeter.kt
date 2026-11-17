package com.mcarplay.app.video

import java.util.ArrayDeque
import kotlin.math.ceil

/** Queue dwell time before sender processing, never head-unit render latency. */
internal class VideoQueueDelayMeter(private val window: Int = 128) {
    init { require(window in 2..1_000) }

    private val agesMs = ArrayDeque<Long>()

    @Synchronized
    fun record(enqueuedNs: Long, dequeuedNs: Long) {
        if (dequeuedNs < enqueuedNs) return
        val ageMs = (dequeuedNs - enqueuedNs) / 1_000_000L
        agesMs.addLast(ageMs)
        if (agesMs.size > window) agesMs.removeFirst()
    }

    @Synchronized
    fun p95Ms(): Long {
        if (agesMs.isEmpty()) return 0L
        val sorted = agesMs.sorted()
        return sorted[ceil(sorted.size * 0.95).toInt().coerceIn(1, sorted.size) - 1]
    }

    @Synchronized
    fun reset() = agesMs.clear()
}
