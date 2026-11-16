package com.mcarplay.app.video

/** Limits producer backlog; overflow still triggers existing IDR rejoin logic. */
internal object VideoQueueBudget {
    const val DEFAULT_BUDGET_MS = 300

    fun capacity(targetFps: Int, budgetMs: Int = DEFAULT_BUDGET_MS): Int {
        require(budgetMs in 100..1_000)
        val fps = targetFps.coerceIn(15, 60)
        val count = (fps.toLong() * budgetMs + 999L) / 1_000L
        return count.toInt().coerceIn(6, 24)
    }
}
