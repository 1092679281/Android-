package com.mcarplay.app.audio

import java.util.concurrent.TimeUnit
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class PriorityDropQueueR8Test {
    @Test fun navigationDoesNotWaitBehindEightBufferedMusicChunks() {
        val queue = PriorityDropQueue<Pair<Boolean, Int>>(16) { it.first }
        repeat(8) { assertTrue(queue.offer(true to it)) }
        assertTrue(queue.offer(false to 99))
        assertEquals(false to 99, queue.poll(0, TimeUnit.MILLISECONDS))
        assertEquals(8L, queue.evictedTotal)
    }

    @Test fun criticalEventsKeepFifoOrder() {
        val queue = PriorityDropQueue<Pair<Boolean, Int>>(16) { it.first }
        assertTrue(queue.offer(false to 1))
        repeat(9) { assertTrue(queue.offer(true to it)) }
        assertTrue(queue.offer(false to 2))
        assertTrue(queue.offer(false to 3))
        assertEquals(false to 1, queue.poll(0, TimeUnit.MILLISECONDS))
        assertEquals(false to 2, queue.poll(0, TimeUnit.MILLISECONDS))
        assertEquals(false to 3, queue.poll(0, TimeUnit.MILLISECONDS))
    }
}
