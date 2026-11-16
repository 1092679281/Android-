package com.mcarplay.app.carlife

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class TouchMappingR8Test {
    @Test fun mapsWideScreenToVideoPrecisely() {
        assertEquals(0 to 0, mapCarLifeTouch(0, 0, 1920, 720, 1280, 480))
        assertEquals(640 to 240, mapCarLifeTouch(960, 360, 1920, 720, 1280, 480))
        assertEquals(1279 to 479, mapCarLifeTouch(1919, 719, 1920, 720, 1280, 480))
    }

    @Test fun rejectsOutOfViewportTouchesInsteadOfGhostEdgeClicks() {
        assertNull(mapCarLifeTouch(-1, 10, 1920, 720, 1280, 480))
        assertNull(mapCarLifeTouch(1920, 0, 1920, 720, 1280, 480))
        assertNull(mapCarLifeTouch(0, 720, 1920, 720, 1280, 480))
        assertNull(mapCarLifeTouch(0, 0, 0, 720, 1280, 480))
    }

    @Test fun supportsLargeCoordinatesWithoutMultiplicationOverflow() {
        assertEquals(9999 to 9999, mapCarLifeTouch(99999, 99999, 100000, 100000, 10000, 10000))
    }
}
