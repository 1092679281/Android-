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
