# 2023 LaCrosse / HyperOS — R8 guarded iOS-style build

## Source of truth
- The full Android app comes from **wangxso/mcarplay @ 8e25e0f69ab7a3bec14649542adea6eb22f74f9a** (pinned).
- This kit layers R5–R7 changes and then the **R8 incremental fixes** in `tools/integrate_and_build_r8.py`.
- R7 and its APK remain rollback options. No change to authentication, RTSP, AES/ChaCha framing or RTP payload format.

## R8 changes
1. **Audio (sender-side):** a 120 ms **decoded PCM byte** cap at the negotiated 44.1/48 kHz sample rate replaces 64 arbitrary PCM chunks. Retain newest audio under backpressure, count evictions/truncations, and log the largest Android sender queue waiting time. This is not a vehicle audio latency measurement.
2. **Navigation/control:** protect non-media events from eviction; when >=8 events have queued, a new navigation/control event removes stale media chunks without reordering existing critical events. Keep R7 behavior for smaller queues.
3. **Video diagnosis:** timestamp external frames as they join and leave the bounded sender queue; log p95 sender queue delay alongside sender-only forwarded FPS. This is not actual head-unit displayed FPS. R7 300 ms capacity and IDR recovery remain for compatibility.
4. **Touch:** reject out-of-display DOWN/MOVE rather than clamping to edge ghost touches. Still map an out-of-range UP to an edge so the CarLife gesture always releases. Preserve proportional resolution conversion.
5. **UI:** group the nine existing display-settings controls as iOS-style rounded cards, increase heading/description readability, make the four-way compatibility selector horizontally scrollable on narrow screens, and label FPS clearly as **sent FPS**. Preserve every view ID and existing listener binding. No licensed Apple fonts/assets bundled.

## Review gates
- **Audio reviewer:** verifies byte-based memory/time budget, frame alignment, navigation queue FIFO / overflow and rejected events.
- **Video reviewer:** verifies no accidental marketing of sender cadence as car display FPS; checks queue dwell, pause/resume resets and IDR admission remains unchanged.
- **Touch reviewer:** verifies extreme resolutions, overflow avoidance, out-of-bounds DOWN and UP release.
- **UI/accessibility reviewer:** verifies original XML IDs preserved, grouped cards, smaller screens scrollable, unit tests/lint; visual screenshot review is still required.
- CI: Python syntax, Kotlin unit tests (old and new), spotless, Android lint, standard debug assemble, DEX/manifest/ZIP checksum/SHA-256 gates.

**Not claimed**: measured end-to-end audio latency, measured vehicle display 60 FPS, calibrated letterboxing/cropping viewport, OEM head-unit compatibility, or pixel-level screenshot verification. Test in a parked vehicle; avoid using development builds while driving.
