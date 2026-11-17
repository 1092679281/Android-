package com.mcarplay.app.carlife

import org.junit.Assert.assertEquals
import org.junit.Test

class VideoInitFpsR10Test {
    @Test
    fun protocolHasActual60FpsField() {
        val packet = CarLifeProtocol.videoInitPayload(1920, 720, fps = 60)
        assertEquals(1920, CarLifeProtocol.firstIntField(packet, 1))
        assertEquals(720, CarLifeProtocol.firstIntField(packet, 2))
        assertEquals(60, CarLifeProtocol.firstIntField(packet, 3))
    }

    @Test
    fun defaultRequestRemains30() {
        assertEquals(30, CarLifeProtocol.firstIntField(CarLifeProtocol.videoInitPayload(1280, 720), 3))
    }

    @Test
    fun carWithCanReply30WhenAskedFor60() {
        val reply = CarLifeProtocol.pbInt(1, 1280) +
            CarLifeProtocol.pbInt(2, 720) +
            CarLifeProtocol.pbInt(3, 30)
        assertEquals(30, CarLifeProtocol.parseVideoFormat(reply)?.fps)
    }
}
