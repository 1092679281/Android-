package com.mcarplay.app.bt

import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicInteger
import kotlin.concurrent.thread

/** Independent adversarial tests: no platform Bluetooth APIs or mocked successes. */
class BluetoothSessionArbiterTest {
    @Test
    fun onlyOneOutboundAttemptMayOwnControlChannel() {
        val gate = BluetoothSessionArbiter()
        val owner = requireNotNull(gate.acquireOutbound())
        assertNull(gate.acquireOutbound())
        assertTrue(gate.controlActive)
        assertFalse(gate.inboundActive)
        owner.close()
        assertNotNull(gate.acquireOutbound()?.also { it.close() })
    }

    @Test
    fun inboundPreemptsUnconfirmedOutboundExactlyOnce() {
        val gate = BluetoothSessionArbiter()
        val outbound = requireNotNull(gate.acquireOutbound())
        val closes = AtomicInteger()
        outbound.onPreempted { closes.incrementAndGet() }
        val inbound = requireNotNull(gate.acquireInbound())
        assertFalse(outbound.isCurrent)
        assertTrue(inbound.isCurrent)
        assertTrue(gate.inboundActive)
        assertTrue(closes.get() == 1)
        assertFalse(inbound.awaitPreviousRetirement(10))
        outbound.close()
        assertTrue(inbound.awaitPreviousRetirement(500))
        inbound.close()
        assertFalse(gate.controlActive)
    }

    @Test
    fun staleOutboundCleanupCannotReleaseNewInboundOwner() {
        val gate = BluetoothSessionArbiter()
        val old = requireNotNull(gate.acquireOutbound())
        val inbound = requireNotNull(gate.acquireInbound())
        old.close()
        old.close()
        assertTrue(inbound.isCurrent)
        assertTrue(gate.inboundActive)
        assertNull(gate.acquireOutbound())
        inbound.close()
        assertFalse(gate.inboundActive)
    }

    @Test
    fun preemptCallbackRegisteredAfterReplacementStillFiresExactlyOnce() {
        val gate = BluetoothSessionArbiter()
        val old = requireNotNull(gate.acquireOutbound())
        val inbound = requireNotNull(gate.acquireInbound())
        val count = AtomicInteger()
        old.onPreempted { count.incrementAndGet() }
        old.onPreempted { count.incrementAndGet() }
        assertTrue(count.get() == 1)
        old.close()
        inbound.close()
    }

    @Test
    fun establishedOutboundCannotBeTakenByIncomingSocket() {
        val gate = BluetoothSessionArbiter()
        val outbound = requireNotNull(gate.acquireOutbound())
        assertTrue(outbound.confirm())
        assertNull(gate.acquireInbound())
        assertTrue(outbound.isCurrent)
        outbound.close()
        assertNotNull(gate.acquireInbound()?.also { it.close() })
    }

    @Test
    fun secondInboundNeverInterruptsFirstInbound() {
        val gate = BluetoothSessionArbiter()
        val first = requireNotNull(gate.acquireInbound())
        assertNull(gate.acquireInbound())
        assertTrue(first.isCurrent)
        first.close()
        assertNotNull(gate.acquireInbound()?.also { it.close() })
    }

    @Test
    fun oldOutboundCannotConfirmAfterPreemptionAndNewSocketWaitsForRelease() {
        val gate = BluetoothSessionArbiter()
        val outgoing = requireNotNull(gate.acquireOutbound())
        val incoming = requireNotNull(gate.acquireInbound())
        assertFalse(outgoing.confirm())
        assertFalse(incoming.awaitPreviousRetirement(1))
        outgoing.close()
        assertTrue(incoming.awaitPreviousRetirement(100))
        incoming.close()
    }

    @Test
    fun newInboundMustWaitUntilOldInFlightCallbackFinishes() {
        val gate = BluetoothSessionArbiter()
        val outbound = requireNotNull(gate.acquireOutbound())
        val callbackEntered = CountDownLatch(1)
        val callbackRelease = CountDownLatch(1)
        val worker =
            thread {
                assertTrue(
                    outbound.dispatchIfCurrent {
                        callbackEntered.countDown()
                        callbackRelease.await(3, TimeUnit.SECONDS)
                    },
                )
            }
        assertTrue(callbackEntered.await(2, TimeUnit.SECONDS))
        val inbound = requireNotNull(gate.acquireInbound())
        outbound.close()
        assertFalse("Old callback is still active", inbound.awaitPreviousRetirement(50))
        callbackRelease.countDown()
        worker.join(3_000)
        assertFalse(worker.isAlive)
        assertTrue("New channel can now safely start", inbound.awaitPreviousRetirement(500))
        inbound.close()
    }

    @Test
    fun competingOutboundStartsAreMutuallyExclusive() {
        val gate = BluetoothSessionArbiter()
        val start = CountDownLatch(1)
        val acquired = AtomicInteger()
        val attemptsDone = CountDownLatch(12)
        val finish = CountDownLatch(1)
        val threads =
            (1..12).map {
                thread(start = true) {
                    if (start.await(3, TimeUnit.SECONDS)) {
                        val lease = gate.acquireOutbound()
                        if (lease != null) acquired.incrementAndGet()
                        attemptsDone.countDown()
                        if (lease != null) {
                            finish.await(3, TimeUnit.SECONDS)
                            lease.close()
                        }
                    } else {
                        attemptsDone.countDown()
                    }
                }
            }
        start.countDown()
        assertTrue("All competitors attempted acquisition", attemptsDone.await(3, TimeUnit.SECONDS))
        assertTrue("Exactly one simultaneous owner", acquired.get() == 1)
        finish.countDown()
        threads.forEach { it.join(3_000) }
        assertFalse(gate.controlActive)
    }

    @Test
    fun independentInstancesCannotShareLeasesAcrossSessions() {
        val a = BluetoothSessionArbiter()
        val b = BluetoothSessionArbiter()
        val aLease = requireNotNull(a.acquireOutbound())
        val bLease = requireNotNull(b.acquireOutbound())
        assertTrue(aLease.isCurrent)
        assertTrue(bLease.isCurrent)
        aLease.close()
        assertTrue(bLease.isCurrent)
        bLease.close()
    }

    @Test
    fun sessionActiveBlocksNewOutboundLeaseUntilCleared() {
        val gate = BluetoothSessionArbiter()
        gate.setSessionActive(true)
        assertTrue(gate.sessionActive)
        assertNull(gate.acquireOutbound())
        gate.setSessionActive(false)
        assertFalse(gate.sessionActive)
        assertNotNull(gate.acquireOutbound()?.also { it.close() })
    }

    @Test
    fun preemptedOutboundCannotStartLateTransportOperation() {
        val gate = BluetoothSessionArbiter()
        val outbound = requireNotNull(gate.acquireOutbound())
        val inbound = requireNotNull(gate.acquireInbound())
        val started = AtomicInteger()
        assertFalse(outbound.dispatchIfCurrent { started.incrementAndGet() })
        assertTrue(started.get() == 0)
        outbound.close()
        assertTrue(inbound.awaitPreviousRetirement(500))
        inbound.close()
    }

    @Test
    fun preemptionCallbackFailureDoesNotOrphanInboundOwner() {
        val gate = BluetoothSessionArbiter()
        val outbound = requireNotNull(gate.acquireOutbound())
        outbound.onPreempted { throw IllegalStateException("simulated socket close failure") }
        val inbound = requireNotNull(gate.acquireInbound())
        assertTrue(inbound.isCurrent)
        assertFalse(outbound.isCurrent)
        outbound.close()
        assertTrue(inbound.awaitPreviousRetirement(500))
        inbound.close()
    }

    @Test
    fun latePreemptionCallbackFailureDoesNotEscapeAcquisitionThread() {
        val gate = BluetoothSessionArbiter()
        val outbound = requireNotNull(gate.acquireOutbound())
        val inbound = requireNotNull(gate.acquireInbound())
        outbound.onPreempted { throw IllegalStateException("late socket cleanup failure") }
        assertTrue(inbound.isCurrent)
        outbound.close()
        assertTrue(inbound.awaitPreviousRetirement(500))
        inbound.close()
    }

    @Test
    fun callbackRegisteredAfterRetirementIsNotInvoked() {
        val gate = BluetoothSessionArbiter()
        val outbound = requireNotNull(gate.acquireOutbound())
        val inbound = requireNotNull(gate.acquireInbound())
        outbound.close()
        val calls = AtomicInteger()
        outbound.onPreempted { calls.incrementAndGet() }
        assertTrue(calls.get() == 0)
        assertTrue(inbound.awaitPreviousRetirement(500))
        inbound.close()
    }

}
