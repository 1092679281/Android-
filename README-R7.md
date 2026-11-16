# mcarplay LaCrosse / HyperOS R7

**Pinned upstream**: wangxso/mcarplay @ 8e25e0f69ab7a3bec14649542adea6eb22f74f9a.

R7 inherits R6 corrected sender-only cadence telemetry and existing Apple-inspired settings accessibility fixes.

- Video: replace an unbounded-in-time 64-frame queue with an approximate 300 ms backlog budget. At target 30 FPS: 9 frames; 60 FPS: 18 frames. Rejected input still resets the existing CarLife gate to await a decodable IDR. Tradeoff: latency vs possible more IDR rejoin events.
- Audio: when full, evict only older media PCM, not navigation/voice prompts or control Init/Stop. Reject incoming events if all queued items are high priority. Record rejection/eviction.
- Audio PCM: reject abnormal external input chunks over 128 KiB before copying; count/log both oversize drops and queue overflow without blocking the producer.
- Retain prior iOS-inspired theme, fixed contrast, >=48dp targeted settings controls; do not alter authentication, RTSP or timing protocols.

Build gate: spotless, Android JVM tests, lint, assembleStandardDebug, DEX and manifest validation, SHA-256. APK is DEBUG signed. **No vehicle testing, full R3 merge, guaranteed 60 FPS, or UI screenshot verification.** Retain previous R6 build for rollback.
