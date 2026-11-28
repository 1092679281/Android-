# R58 / 0.1.45 maintenance candidate — R58.2 validation checkpoint

Base maintenance branch: maintenance/r56-source-of-truth
R58.2 commit: 77d8d6f0b68162789bc962000eff608e16328c91
R58.2 GitHub Actions run: 45975498068
Run URL: https://github.com/1092679281/Android-/actions/runs/45975498068
Artifact ID: 15187905369
Artifact URL: https://github.com/1092679281/Android-/actions/runs/45975498068/artifacts/15187905369

## Source integrity

- R56 reconstructed baseline: 827 files, tree SHA-256 29bd33771f52538d918b8f9c2a66e6822b84d3e2c65a9817aff926dcde5fbec5.
- R57 candidate: 827 files, tree SHA-256 c0a92358ca8a283ad73f041274ef7915b15f7a10e5c9c45640f0e5f82ed91318.
- R58 candidate: 830 files, tree SHA-256 125ec362a2b4766fe1db4c7a63adaf26fe48afe4e893a078850662e893051fcb.
- R58.1 candidate: 832 files, tree SHA-256 4a3c8abacc5800c6d09059f1d4fde4ea99323c0eb105300cfa77e9d63d337501.
- R58.2 candidate: 832 files, tree SHA-256 2158c86e835dfa4a3c249554934374a2a6d399e4d7f5d0e3d1ca436afab799d9.
- R58.2 is an incremental continuation of the verified R56 reconstruction plus R57/R58/R58.1; no historical patch was replaced.
- R58.2 corrected the invalid function reference in Iap2SenderSession.kt and normalized Kotlin formatting. Spotless check is now a blocking gate after spotlessApply and the explicit MFi guard formatting correction.

## R58.2 GitHub Actions result

Run 45975498068 completed successfully on 2026-11-27T09:46:46Z.

- Source reconstruction and R57/R58/R58.1/R58.2 patch steps: passed.
- Spotless formatting check: passed.
- Standard unit tests: 1,482 tests; 0 failures, 0 errors, 0 skipped.
- Remote unit tests: 1,507 tests; 0 failures, 0 errors, 0 skipped.
- Standard Lint: passed.
- Standard Debug APK: built and APK signature verified.
  - package: com.mcarplay.app
  - versionName: 0.1.45-debug
  - versionCode: 1450000
  - SHA-256: f990efff0cd6ce301551e473ae311bd336a5c3ae59259212f4bd97974a101ef2
- Remote Debug APK: built and APK signature verified.
  - package: com.mcarplay.app.rd
  - versionName: 0.1.45-rd-debug
  - versionCode: 1450000
  - SHA-256: 1b75069cc8be780499733238db73cb31c30509bfdfbff7b59378a4c862c34ad0
- Artifact upload: passed; 58,630,326 bytes; retention 90 days.
- Build and signing verification do not constitute physical-device installation or launch validation.

## R58.2 source audit — remaining hard blockers

### MFi production verifier is intentionally unavailable

Exact source:
- app/src/main/java/com/mcarplay/app/iap2/MfiAuthenticationVerifier.kt
- app/src/main/java/com/mcarplay/app/iap2/Iap2SenderSession.kt
- app/src/main/java/com/mcarplay/app/bt/BtSession.kt
- app/src/main/java/com/mcarplay/app/airplay/VirtualIap2Link.kt
- app/src/main/java/com/mcarplay/app/airplay/AirPlayClient.kt

Findings:
- MfiAuthenticationVerifier.UNAVAILABLE returns TRUST_MATERIAL_UNAVAILABLE.
- Iap2SenderSession defaults to UNAVAILABLE.
- BtSession.runSenderSession constructs Iap2SenderSession without an authorized verifier.
- VirtualIap2Link also defaults to UNAVAILABLE and its production construction in AirPlayClient does not inject a verifier.
- Both production paths correctly fail closed: no 0xAA05, no authenticated milestone, no auth callback or MIB3 burst on an unverified response.
- Therefore real MFi authentication is not merely awaiting a test; there is currently no production verifier implementation or production injection path.
- Do not implement guessed certificate roots, bypass checks, or infer the MFi signature profile. Required input: authorized MFi trust anchors/certificate profile, licensed algorithm and message canonicalization specification, and known-good/known-bad challenge-response vectors. Private signing keys must not be added to the repository.

### 0x4300 ACK and vehicle SYN restart

Exact source:
- app/src/main/java/com/mcarplay/app/iap2/Iap2LinkEngine.kt
- app/src/main/java/com/mcarplay/app/iap2/Iap2SenderSession.kt
- app/src/main/java/com/mcarplay/app/transport/Iap2LinkChannel.kt

Findings:
- 0x4300 is sent through sendObservedControl, tracked in the reliable unacknowledged queue, and associated with an exact sequence receipt.
- PEER_ACKED requires a valid cumulative ACK advancing over the exact sent sequence; local write completion is recorded separately.
- If a new pure peer SYN arrives on an established Bluetooth link after the control session has begun, rebuildOnNewSyn causes the old link to be retired rather than carrying old authentication/endpoint state into a new negotiation.
- The current unit tests include synthetic new-SYN/ACK and retransmission cases. They are not a captured replay of the user's vehicle.
- No vehicle-side raw RX/TX capture has been supplied for the failing 0x4300 sequence. The current source can distinguish an observed peer SYN from a local close in its frame/termination records, but cannot prove why the head unit initiated it or whether the actual head unit's ACK encoding/sequence differs from the synthetic model.
- Required input: a privacy-scrubbed raw RX/TX byte trace with monotonic timestamps, from the first SYNC through 0x4300, any ACK, subsequent DETECT/SYN, and socket close. Preserve control, sequence, ACK, session ID, lengths, checksums and frame boundaries. Redact MACs, serials, keys and credentials without changing frame structure.

### 0x4301 / Wi-Fi / AirPlay

- R58.1 added a control-frame pump so 0x4301 is retained while waiting for the exact 0x4300 ACK; unrelated frames are deferred and duplicate 0x4301 is ignored in the same wait window.
- The corresponding unit test proves queue behavior, not actual head-unit delivery.
- Real 0x4301 receive, endpoint trust, Wi-Fi join, AirPlay SETUP/RECORD, video/audio/touch and reconnect remain unverified.

## Adversarial review status

- Six technical perspectives were reviewed by one assistant; this is not six independently executing agents or external reviewer sign-off.
- CI and unit-test evidence is available for the candidate.
- Independent protocol review and real vehicle trace review remain outstanding.

## Release status

Candidate only. No stable release or formal Release was created. No physical-device install/launch/crash validation and no real-vehicle protocol validation are claimed.


## R58.3 targeted E2LB probe experiment (2026-11-27)

R58.3 patch: r56-build/maintenance/R58.3-disable-speculative-detect-probe.patch.bz2
Compressed patch SHA-256: 39d49444fb1371e16f7d14b6bcef46e05f292a77302bb5080d78a5b675b6e203.
Uncompressed patch SHA-256: 37192a930a3b66d6bf2d359088263b9459ba141e0da6e4d7d5640f31aa8c5b9b.
Candidate tree: 832 files, SHA-256 ed5634d5b98a93da9fb7365d43415502e1f290d8eea76bb4df54cbf03a0b6ea0.

### Original R44 trace evidence (粘贴的文本 (1).txt)

The three failures have the same sequence:
- 0x4300 was sent as `awaitAck=false` / passive receipt (seq 110); this directly confirms the original sender did not request link-layer acknowledgement/retransmission for this request.
- The phone then observed repeated DETECT markers.
- The phone emitted a standalone DETECT marker reply (reply=1/2).
- A new pure SYN arrived from the peer roughly 18 ms after that reply in all three attempts:
  - 11:29:19.082 marker reply -> 11:29:19.100 peer SYN seq 118.
  - 11:29:27.539 marker reply -> 11:29:27.618 peer SYN seq 165.
  - 11:29:36.115 marker reply -> 11:29:36.190 peer SYN seq 187.
- Therefore the peer initiated the observed renegotiation. The temporal correlation between our standalone marker reply and the peer SYN is strong and repeatable, but the log omits raw wire bytes; it does not prove that the marker reply caused the peer restart.

### R58.3 change

- Keep E2LB conservative reliable send-window behavior.
- Disable only the speculative standalone marker echo for E2LB while an observed control request is awaiting ACK.
- Other engine users retain the previous default unless they explicitly disable the probe.
- Add regression coverage proving repeated DETECT markers do not produce outbound marker replies when disabled, and that the exact cumulative ACK still advances the 0x4300 receipt to PEER_ACKED.
- This is a targeted mitigation/experiment based on the repeated trace timing, not a proven root-cause fix. The vehicle must be retested to determine whether the SYN restart stops.

### R58.3 local focused validation

- Kotlin/JVM loopback smoke using the exact Iap2LinkEngine source: passed; marker replies remained suppressed and exact 0x4300 ACK was accepted.
- Full Gradle test execution could not be run in the local container because the Gradle 8.10.2 distribution was not cached and outbound DNS/network access was unavailable. GitHub Actions is the authoritative full Android validation gate for this patch.
- R58.3 Spotless, Standard/Remote tests, Lint and APK builds: pending the new GitHub Actions run.

## Important interaction with MFi gate

The historical R44 trace shows an unverified 0xAA03 response followed by a compatibility 0xAA05. R58 intentionally removed that unsafe behavior. In R58.2/R58.3 production construction, both Bluetooth Iap2SenderSession and AirPlay VirtualIap2Link still use MfiAuthenticationVerifier.UNAVAILABLE. Consequently the current candidate correctly aborts before sending 0xAA05 and will not reach 0x4300 on a real vehicle until an authorized MFi verifier and trust/profile material are integrated. Do not use test doubles or an authentication bypass to test around this blocker.

## R58.5 maintenance candidate

R58.5 applies after the formatted R58.4 source from commit
`2a24ebcd2d1b39f650aca767b7b7edbf4301a469`.
The R58.4 CI source has 834 files and tree SHA-256
`506c6b7ca9fd2f668730b88782245df9f1cf249903d380e76aa41da4c3d5a4dd`.
Replaying the R58.5 patch on that source produced 837 files and tree SHA-256
`ee63699431fde032169ee3bc33cdf6aa6dfa16c0bc7097766c0fbb3e26dc5173`.

- Network discovery releases its multicast lock after resolution, stop or failure. Network loss stops the old discovery and releases the
  video sender's streaming Wi-Fi lock. The streaming lock follows actual video output and is released on suspension or teardown.
- Audio sockets, recorder and codec have an idempotent shutdown path. A stopped negotiated stream cannot restart with the same key and
  counter. Projection revocation stops only its matching audio capture.
- Shizuku touch gestures are serialized and can send CANCEL on failure, replacement or display teardown. The new Binder transaction is appended.
- Projection grants are passed directly to the foreground service. Service teardown clears and stops the owned projection.
- The AirPlay controller's Ed25519 seed migrates to Android Keystore-backed AES-GCM storage while preserving the pairing ID. SRP server
  proofs use a timing-resistant comparison.
- The session's serial RTSP control worker bounds its pending queue and times out when idle. Decoder rate hints use a supported nominal
  frame rate with a fallback to the base configuration.
- CI builds both R8 Release variants as a separate verification gate and checks the Shizuku service name in the mapping. The application
  keeps R8 opt-in pending device verification. The build rejects dynamic or changing Release runtime versions when this gate is enabled.
  Linux CI pins and checks SHA-256 for 685 artifacts and metadata files across 388 resolved Gradle components.
  The checked-in manifest covers Debug tests and lint, APK packaging, and the optimized Release builds.

A local JVM run passed 46 focused audio and AirPlay tests, including the identity envelope and retired audio stream regressions.
Android Keystore migration on an actual device, Android 17 runtime behavior, real-vehicle 0x4300 ACK and renewed SYN timing, mDNS
reliability, and decoder behavior still require device or vehicle evidence. The production MFi trust material and verifier are still
required before this candidate can reach the authenticated 0x4300 exchange on the vehicle.


## R58.5.1 terminal MFi failure handling (2026-11-28)

Patch: `r56-build/maintenance/R58.5.1-mfi-auth-failure-stop.patch.bz2`

- Compressed patch SHA-256: `bde7d4d392d6b80814c040eb7f5f0bdc23b17b09ece4e0fb30227c683139710c`.
- Uncompressed patch SHA-256: `975dbaeb648e394dc9b1699133b5da7a74eb810ec7ff1db6c212aae73a1f2862`.
- Candidate adds one Kotlin test file and updates the existing sender-session tests (838 files before formatter normalization).
- Bluetooth startup now classifies `RESPONSE_UNVERIFIED` and `CRYPTOGRAPHICALLY_REJECTED` as terminal MFi blockers, reports a dedicated diagnostic, and stops automatic Bluetooth reconnect for that receiver. Manual connection remains available after the missing authorized verifier is supplied.
- The AirPlay virtual iAP2 path now forwards malformed, rejected, timed-out, and unverifiable MFi outcomes to the owning session. The owner tears down the failed attempt instead of silently waiting for a never-authenticated tunnel.
- Regression tests cover stable blocker classification and the virtual-link callback. Both paths remain fail-closed: no unverified `0xAA05`, no authenticated milestone, and no MIB3 burst.
- This patch does **not** implement the production MFi verifier. `Iap2SenderSession` and `VirtualIap2Link` still use `MfiAuthenticationVerifier.UNAVAILABLE` until the project receives authorized MFi trust anchors/certificate profile, licensed signature and canonicalization specification, and known-good/known-bad vectors. Do not add guessed roots, bypasses, or private keys.
- R58.5.1 Android CI and formatter fingerprint: pending this commit's GitHub Actions run.
- 0x4300/0x4301, Wi-Fi, AirPlay SETUP/RECORD, and video/audio/touch still require the authorized MFi gate to be cleared before the complete chain can be exercised on the E2LB vehicle. Existing synthetic tests are not real-vehicle acceptance.
