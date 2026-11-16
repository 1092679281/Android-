package com.mcarplay.app.audio

import java.util.concurrent.TimeUnit
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PriorityDropQueueTest {
    @Test fun protectPromptOnOverflow() {
        val queue = PriorityDropQueue<Pair<Boolean, Int>>(3) { it.first }
        assertTrue(queue.offer(true to 1))
        assertTrue(queue.offer(false to 10))
        assertTrue(queue.offer(true to 2))
        assertTrue(queue.offer(false to 11))
        assertEquals(1L, queue.evictedTotal)
        assertEquals(false to 10, queue.poll(0, TimeUnit.MILLISECONDS))
        assertEquals(true to 2, queue.poll(0, TimeUnit.MILLISECONDS))
        assertEquals(false to 11, queue.poll(0, TimeUnit.MILLISECONDS))
    }
    @Test fun rejectWhenAllAreCritical() {
        val queue = PriorityDropQueue<Pair<Boolean, Int>>(2) { it.first }
        assertTrue(queue.offer(false to 10))
        assertTrue(queue.offer(false to 11))
        assertFalse(queue.offer(true to 100))
        assertEquals(0L, queue.evictedTotal)
        assertEquals(1L, queue.rejectedTotal)
        assertEquals(false to 10, queue.poll(0, TimeUnit.MILLISECONDS))
    }
    @Test fun clearingKeepsQueueReusable() {
        val queue = PriorityDropQueue<Int>(1) { true }
        assertTrue(queue.offer(1))
        assertTrue(queue.offer(2))
        assertEquals(1L, queue.evictedTotal)
        queue.clear()
        assertEquals(null, queue.poll(0, TimeUnit.MILLISECONDS))
        assertTrue(queue.offer(3))
    }
}
