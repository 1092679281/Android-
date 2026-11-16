# R9 — One-tap CarPlay-like connection

The existing bridge is **CarWith (HyperOS) → 7 local CarLife channels → wireless CarPlay sender → compatible CarPlay receiver**. The on-car interface remains **CarWith**, not the licensed iOS CarPlay interface. R9 does not add Apple CarPlay to a CarLife-only receiver.

## Changes
- First manual start explicitly asks video-only or audio. The pre-existing video-only default remains.
- Later starts use that choice without another modal.
- Long press the idle Connect CTA to change the audio choice at any time.
- On Bluetooth-triggered automatic starts, apply the saved mode only to a fresh session. Missing choice leaves audio disabled.
- Original Bluetooth permissions, identity checks, system settings prompts, manual stop cooldown and reconnection circuit breaker remain.
- No changes to auth/encryption, CarLife takeover, AirPlay/RTSP transports, receiver compatibility or touch coordinate protocol.

## Four review perspectives
Audio: no automatic opt-in without explicit choice, regression tests.
Connectivity: no duplicate start, preserved auto and manual boundaries.
Security: no privileged CarWith service bypass and no unauthorized pairing.
UI: discoverable long-press hint with both Chinese and English strings.

GitHub Actions tests, lint, formatting and assemble are necessary but do not prove real 2023 LaCrosse compatibility, displayed FPS or actual latency. Test parked, with R8 as rollback.
