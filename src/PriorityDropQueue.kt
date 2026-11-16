package com.mcarplay.app.audio

import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong

/**
 * Keep the order of control and prompt events, while removing queued media
 * when the audio pipeline is already heavily backlogged. Producers never
 * block and do not evict critical events.
 */
internal class PriorityDropQueue<T>(capacity: Int, private val disposable: (T) -> Boolean) {
    private val queue = LinkedBlockingQueue<T>(capacity)
    private val offerLock = Any()
    private val evicted = AtomicLong(0L)
    private val rejected = AtomicLong(0L)

    val evictedTotal: Long get() = evicted.get()
    val rejectedTotal: Long get() = rejected.get()

    fun offer(value: T): Boolean = synchronized(offerLock) {
        // At eight queued events, a new navigation/control event should not
        // wait behind an entire block of stale music. Purge only disposable
        // media, preserving the original FIFO order of all critical events.
        if (!disposable(value) && queue.size >= PRIORITY_BACKLOG_THRESHOLD) {
            var removed = 0L
            for (existing in queue.toList()) {
                if (disposable(existing) && queue.remove(existing)) removed++
            }
            if (removed > 0) evicted.addAndGet(removed)
        }
        if (queue.offer(value)) return@synchronized true
        val candidate = queue.firstOrNull(disposable)
        if (candidate != null && queue.remove(candidate)) {
            evicted.incrementAndGet()
            if (queue.offer(value)) return@synchronized true
        }
        rejected.incrementAndGet()
        false
    }

    fun poll(timeout: Long, unit: TimeUnit): T? = queue.poll(timeout, unit)

    fun clear() = synchronized(offerLock) { queue.clear() }

    private companion object {
        const val PRIORITY_BACKLOG_THRESHOLD = 8
    }
}
