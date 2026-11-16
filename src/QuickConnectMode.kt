package com.mcarplay.app.bt

/** Pure policy: never turn on auto audio before the user has selected it. */
internal object QuickConnectMode {
    fun needsFirstTimeChoice(previousAudio: Boolean?): Boolean = previousAudio == null

    fun forAutomatic(previousAudio: Boolean?): Boolean = previousAudio == true
}
