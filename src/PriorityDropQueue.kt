package com.mcarplay.app.audio

import java.util.concurrent.LinkedBlockingQueue
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicLong

/** Preserve critical prompt/control events by evicting only disposable queued events. */
internal class PriorityDropQueue<T>(capacity: Int, private val disposable: (T) -> Boolean) {
    private val queue = LinkedBlockingQueue<T>(capacity)
    private val evicted = AtomicLong(0L)
    private val rejected = AtomicLong(0L)

    val evictedTotal: Long get() = evicted.get()
    val rejectedTotal: Long get() = rejected.get()

    fun offer(value: T): Boolean {
        if (queue.offer(value)) return true
        val candidate = queue.firstOrNull(disposable)
        if (candidate != null && queue.remove(candidate)) {
            evicted.incrementAndGet()
            if (queue.offer(value)) return true
        }
        rejected.incrementAndGet()
        return false
    }

    fun poll(timeout: Long, unit: TimeUnit): T? = queue.poll(timeout, unit)

    fun clear() = queue.clear()
}
