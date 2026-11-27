# R58 / 0.1.45 maintenance candidate — R58.1 delta

Base candidate: R58.0 / 0.1.45, CI run 45969302895.
R58.0 tree SHA-256: 125ec362a2b4766fe1db4c7a63adaf26fe48afe4e893a078850662e893051fcb (830 files).
R58.1 final tree: 832 files.
R58.1 tree SHA-256: 4a3c8abacc5800c6d09059f1d4fde4ea99323c0eb105300cfa77e9d63d337501.
Incremental patch base: exact R58.0 CI candidate source archive.
Incremental patch SHA-256: fbd73f19d4916802c4dc5a4b9ac3695857ded23deb3fa4fc880bda1bdb6b54a1.
Compressed patch SHA-256: 13e6a36f8eb782413239c9bc0eaf6b303c83837b107cb494c43319c508c3ea95.

## R58.1 additional findings and changes

### 0x4301 could be missed while waiting for 0x4300 ACK
The first R58 implementation waited for the link-layer receipt without concurrently draining iAP2 control data. The link reader can process the ACK header and enqueue a 0x4301 control payload in the same inbound frame. If the receipt became PEER_ACKED before the sender thread resumed, the wait loop could exit before the session parser consumed that queued 0x4301.

Change:
- Pump iAP2 control frames while waiting for the exact 0x4300 cumulative ACK.
- Retain one 0x4301 for endpoint handoff and defer unrelated control frames instead of dropping them.
- After ACK, drain the already-arrived control queue briefly (bounded 100 ms) to cover the ACK-header/control-payload scheduling race.
- Ignore duplicate 0x4301 in the same wait window.
- Added Iap2AvailabilityFramePump and deterministic regression test for 0x4301 retention, duplicate suppression and unrelated-frame deferral.

### Formatting
- The R58.0 CI Spotless audit found one formatting diff in PairingClients.kt. Corrected in R58.1. The formatter audit remains non-blocking for the historical reconstruction chain but is expected to pass on the final candidate.

## R58.0 full CI evidence (before R58.1 delta)
GitHub Actions run 45969302895 completed successfully:
- Standard unit tests: 1,481 tests, 0 failures/errors.
- Remote unit tests: 1,506 tests, 0 failures/errors.
- Standard Lint: passed.
- Standard Debug APK: package com.mcarplay.app, versionName 0.1.45-debug, versionCode 1450000; apksigner verification passed; SHA-256 4c8328cbebc221cf94af15821b7327c11152057f5bf4b30e00077ba40c42c25f.
- Remote Debug APK: package com.mcarplay.app.rd, versionName 0.1.45-rd-debug, versionCode 1450000; apksigner verification passed; SHA-256 cf8fa8992f803a526d4d8d21f4dcaad901de4efba702e430d7b685656473c3cc.
- Spotless formatting audit: non-blocking failure on PairingClients.kt; fixed in R58.1.
These CI results apply to R58.0, not yet to the final R58.1 delta.

## R58.1 local validation
- Incremental patch replays cleanly against the exact R58.0 CI artifact; 832 files and exact final tree fingerprint.
- Kotlin/JVM focused regression suite: 54/54 passed (Iap2LinkEngineTest, Iap2AvailabilityProgressTest, Iap2AvailabilityFramePumpTest under a minimal JUnit-compatible runner).
- Python diagnostic/logbot tests: 23/23 passed.
- Kotlin compile of link engine/channel and two-ended in-memory iAP2 loopback ACK smoke: passed; exact ACK receipt PEER_ACKED with wire sequence 101.
- git diff --cached --check: passed.
- Final R58.1 Android Gradle tests, Lint, Spotless and APK build: pending GitHub Actions.

## R58.0 changes retained
- R57 earliest retransmission deadline and late SYN-ACK false-ACK fixes.
- MFi strict TLV structure, verifier contract, default TRUST_MATERIAL_UNAVAILABLE fail-closed behavior; only VERIFIED can enqueue 0xAA05.
- Virtual tunnel subscriptions, HID and EA/touch input gated until local MFi verification and successful AA05 queue admission.
- 0x4300 reliable send window, exact-sequence ACK receipt and bounded retry wait.
- 0x4301 without exact 0x4300 ACK is blocked from endpoint handoff; application response cannot substitute for link ACK.

## Six-role adversarial review status
Reviewed Bluetooth/RFCOMM lifecycle, iAP2 sequence/ACK state, MFi trust boundary, E2LB/Wi-Fi handoff, concurrency/waiter lifecycle, and negative/regression tests. This is a role-based review by one assistant, not six independently executing agents; independent-agent sign-off remains outstanding.

## Release blockers / not verified
- No authorized MFi trust anchors, licensed signature profile or real challenge/response vectors are present. The production verifier intentionally returns TRUST_MATERIAL_UNAVAILABLE. This prevents false MFi success but real MFi authentication is not yet implemented.
- No vehicle-side raw 0x4300 ACK/0x4301 capture has been supplied; no claim that the original vehicle SYN restart root cause is fixed.
- No real vehicle validation of 0x4300, 0x4301, Wi-Fi handoff, AirPlay SETUP/RECORD, video, audio, touch or reconnect.
- No physical device install/launch/crash validation performed.
- Candidate only. No stable release or formal Release created.
