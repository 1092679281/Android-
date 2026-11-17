package com.mcarplay.app.audio

import java.util.concurrent.TimeUnit
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PcmLatencyQueueTest {
    @Test fun budgetMatchesPcmDuration() {
        assertEquals(23_040, PcmLatencyQueue(48_000, 120).budgetBytes)
        assertEquals(21_168, PcmLatencyQueue(44_100, 120).budgetBytes)
    }

    @Test fun newestDataSurvivesBackpressure() {
        val queue = PcmLatencyQueue(8_000, 100) // 3200 bytes
        assertEquals(0, queue.offer(ByteArray(1600) { 1 }))
        assertEquals(0, queue.offer(ByteArray(1600) { 2 }))
        assertEquals(1, queue.offer(ByteArray(1600) { 3 }))
        assertEquals(3200, queue.backlogBytes)
        assertArrayEquals(ByteArray(1600) { 2 }, queue.poll())
        assertArrayEquals(ByteArray(1600) { 3 }, queue.poll())
        assertEquals(1L, queue.droppedTotal)
        assertNull(queue.poll(0, TimeUnit.MILLISECONDS))
    }

    @Test fun oversizedIncomingChunkKeepsFreshAlignedTail() {
        val queue = PcmLatencyQueue(8_000, 100)
        val input = ByteArray(6400) { if (it < 3200) 1 else 7 }
        assertEquals(1, queue.offer(input))
        assertEquals(1L, queue.trimmedTotal)
        assertArrayEquals(ByteArray(3200) { 7 }, queue.poll())
    }

    @Test fun maintainsOwnCopyAndReset() {
        val q = PcmLatencyQueue(48_000)
        val src = ByteArray(1408) { 9 }
        q.offer(src)
        src.fill(2)
        assertArrayEquals(ByteArray(1408) { 9 }, q.poll())
        q.offer(ByteArray(1408))
        q.clear()
        assertEquals(0, q.backlogBytes)
        assertNull(q.poll())
        assertTrue(q.maxQueueAgeMs >= 0L)
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsUnalignedPcm() {
        PcmLatencyQueue(48_000).offer(ByteArray(3))
    }
}
