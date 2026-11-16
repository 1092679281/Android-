package com.mcarplay.app.video

/** Explicit preference 30/60, bounded by a valid positive receiver maxFPS. */
internal object SourceFpsPolicy {
    fun effective(
        requested: Int,
        receiverMax: Int,
    ): Int {
        val selected = if (requested >= 60) 60 else 30
        val cap = receiverMax.takeIf { it in 1..240 } ?: selected
        return minOf(selected, cap)
    }
}
