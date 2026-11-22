package com.mcarplay.app.bt

import java.io.Closeable
import java.util.concurrent.CountDownLatch
import java.util.concurrent.TimeUnit

/**
 * Exactly one Bluetooth iAP2 control owner at a time.
 *
 * Receiver-initiated (inbound) RFCOMM may replace an outgoing attempt that
 * has not delivered a session endpoint. It may never steal an already
 * confirmed session or another inbound session.
 *
 * The new owner MUST wait for old lease retirement before exchanging protocol
 * bytes. No network or Bluetooth APIs run under the arbitration lock.
 */
internal class BluetoothSessionArbiter {
    private val lock = Any()
    private var owner: Lease? = null

    val inboundActive: Boolean get() = synchronized(lock) { owner?.inbound == true }
    val controlActive: Boolean get() = synchronized(lock) { owner != null }

    fun acquireOutbound(): Lease? =
        synchronized(lock) {
            if (owner != null) null else Lease(inbound = false, previous = null).also { owner = it }
        }

    fun acquireInbound(): Lease? {
        val previous: Lease?
        val acquired: Lease
        synchronized(lock) {
            previous = owner
            if (previous != null && (previous.inbound || previous.confirmed)) return null
            previous?.preempted = true
            acquired = Lease(inbound = true, previous = previous)
            owner = acquired
        }
        // Closing the outgoing socket can block or trigger callbacks. Never
        // run this while holding the arbitration lock.
        previous?.deliverPreemption()
        return acquired
    }

    inner class Lease internal constructor(
        val inbound: Boolean,
        private val previous: Lease?,
    ) : Closeable {
        private val retired = CountDownLatch(1)
        private var preemptAction: (() -> Unit)? = null
        private var preemptNotified = false
        private var closed = false

        internal var confirmed = inbound
        internal var preempted = false

        val isCurrent: Boolean get() = synchronized(lock) { !closed && owner === this }

        /** Outbound must confirm only once legitimate iAP2 endpoint has arrived. */
        fun confirm(): Boolean =
            synchronized(lock) {
                if (closed || owner !== this) false else {
                    confirmed = true
                    true
                }
            }

        /** When a late callback is registered after preemption, invoke it once. */
        fun onPreempted(action: () -> Unit) {
            val invokeNow =
                synchronized(lock) {
                    if (preempted && !preemptNotified) {
                        preemptNotified = true
                        true
                    } else {
                        if (!preempted && !closed) preemptAction = action
                        false
                    }
                }
            if (invokeNow) action()
        }

        internal fun deliverPreemption() {
            val action =
                synchronized(lock) {
                    if (!preempted || preemptNotified) null else {
                        preemptAction?.also {
                            preemptAction = null
                            preemptNotified = true
                        }
                    }
                }
            action?.invoke()
        }

        /**
         * A preempting inbound channel cannot start its protocol negotiation
         * until the old outbound attempt has stopped (or the bounded timeout
         * has elapsed, in which case the inbound caller must abort).
         */
        fun awaitPreviousRetirement(timeoutMillis: Long): Boolean {
            if (timeoutMillis < 0) return false
            val old = previous ?: return isCurrent
            val complete =
                try {
                    old.retired.await(timeoutMillis, TimeUnit.MILLISECONDS)
                } catch (_: InterruptedException) {
                    Thread.currentThread().interrupt()
                    false
                }
            return complete && isCurrent
        }

        override fun close() {
            synchronized(lock) {
                if (closed) return
                closed = true
                preemptAction = null
                if (owner === this) owner = null
                retired.countDown()
            }
        }
    }
}
