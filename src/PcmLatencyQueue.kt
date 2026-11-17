package com.mcarplay.app.audio

import java.util.ArrayDeque
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong

/**
 * PCM backlog measured in decoded audio milliseconds, not an arbitrary count
 * of network chunks. Keeps the newest bounded audio when the producer runs
 * faster than the RTP sender. All retained slices are stereo s16 frame aligned.
 *
 * This controls only the Android sender queue; the receiver's jitter buffer
 * and DAC latency must still be measured on a vehicle.
 */
internal class PcmLatencyQueue(
    sampleRate: Int,
    budgetMs: Int = 120,
) {
    init {
        require(sampleRate in 8_000..192_000)
        require(budgetMs in 20..500)
    }

    // 16-bit stereo = four bytes per sample frame.
    val budgetBytes: Int = ((sampleRate.toLong() * budgetMs / 1_000L) * 4L).toInt()
    private val lock = java.lang.Object()
    private val items = ArrayDeque<ByteArray>()
    private var queuedBytes = 0

    private val droppedBlocks = AtomicLong(0)
    private val trimmedBlocks = AtomicLong(0)
    private val maximumDelay = AtomicLong(0)
    private val enqueueAtNs = ArrayDeque<Long>()

    val droppedTotal: Long get() = droppedBlocks.get()
    val trimmedTotal: Long get() = trimmedBlocks.get()
    val maxQueueAgeMs: Long get() = maximumDelay.get()

    /** Returns number of discarded older chunks, including a truncated input. */
    fun offer(pcm: ByteArray): Int {
        require(pcm.size % 4 == 0) { "Stereo PCM must be frame aligned" }
        if (pcm.isEmpty()) return 0
        val trimmed = pcm.size > budgetBytes
        val copy =
            if (trimmed) pcm.copyOfRange(pcm.size - budgetBytes, pcm.size)
            else pcm.copyOf()
        var evictions = if (trimmed) 1 else 0
        synchronized(lock) {
            while (queuedBytes + copy.size > budgetBytes && items.isNotEmpty()) {
                val removed = items.removeFirst()
                enqueueAtNs.removeFirst()
                queuedBytes -= removed.size
                evictions++
            }
            items.addLast(copy)
            enqueueAtNs.addLast(System.nanoTime())
            queuedBytes += copy.size
            check(queuedBytes <= budgetBytes)
            lock.notifyAll()
        }
        if (trimmed) trimmedBlocks.incrementAndGet()
        if (evictions > 0) droppedBlocks.addAndGet(evictions.toLong())
        return evictions
    }

    fun poll(): ByteArray? = synchronized(lock) { removeFirstLocked() }

    fun poll(timeout: Long, unit: TimeUnit): ByteArray? {
        require(timeout >= 0)
        var remaining = unit.toNanos(timeout)
        val deadline = System.nanoTime() + remaining
        synchronized(lock) {
            while (items.isEmpty() && remaining > 0) {
                lock.wait(remaining / 1_000_000L, (remaining % 1_000_000L).toInt())
                remaining = deadline - System.nanoTime()
            }
            return removeFirstLocked()
        }
    }

    fun clear() = synchronized(lock) {
        items.clear()
        enqueueAtNs.clear()
        queuedBytes = 0
    }

    val backlogBytes: Int get() = synchronized(lock) { queuedBytes }

    private fun removeFirstLocked(): ByteArray? {
        if (items.isEmpty()) return null
        val data = items.removeFirst()
        val queuedAt = enqueueAtNs.removeFirst()
        queuedBytes -= data.size
        val ageMs = ((System.nanoTime() - queuedAt).coerceAtLeast(0L)) / 1_000_000L
        maximumDelay.accumulateAndGet(ageMs, ::maxOf)
        return data
    }
}
