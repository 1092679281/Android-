package com.mcarplay.app.bt

import android.content.Context

/** Remember an explicit audio preference; unknown always means video-only. */
object QuickConnectPrefs {
    private const val PREFS = "settings"
    private const val KEY_LAST_AUDIO = "quick_connect_last_audio_enabled"

    fun lastAudioEnabled(context: Context): Boolean? {
        val preferences = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        return if (preferences.contains(KEY_LAST_AUDIO)) preferences.getBoolean(KEY_LAST_AUDIO, false) else null
    }

    fun remember(
        context: Context,
        enabled: Boolean,
    ) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putBoolean(KEY_LAST_AUDIO, enabled)
            .apply()
    }
}
