# R58 / 0.1.45 maintenance candidate — final pre-CI revision

Base: R57 / 0.1.44 exact candidate source tree.
R57 base tree SHA-256: c0a92358ca8a283ad73f041274ef7915b15f7a10e5c9c45640f0e5f82ed91318 (827 files).
R58 candidate tree: 830 files.
R58 tree SHA-256: 125ec362a2b4766fe1db4c7a63adaf26fe48afe4e893a078850662e893051fcb.
Patch format: unified=1; exact replay against a clean R57 source archive passed.
Uncompressed patch SHA-256: b8117e253101ec6449c24a38c3a53526ffba509ce40a128246bc27636d14b9d8.
Compressed patch archive SHA-256: 38c4a8288e04b77954ccfa064a5d2151dd0185892b6f0c8e57b2eea753f6e77e.

## Findings and changes

### MFi authentication boundary
- Both Bluetooth iAP2 and virtual iAP2 tunnel paths require strict 0xAA01 and 0xAA03 TLV structure before verification.
- The verifier contract receives the complete 0xAA01 certificate TLV container, the complete 0x1D01 receiver-identification body, the exact challenge and the signature. This preserves the inputs needed for certificate-chain and receiver-identity binding under the authorized MFi profile.
- Production default is TRUST_MATERIAL_UNAVAILABLE and fails closed. Only a verifier result of VERIFIED can enqueue 0xAA05 and open the local MFi-authenticated state.
- Verifier/provider exceptions are hard rejections. Out-of-phase duplicate certificate frames cannot replace an outstanding challenge. Explicit 0xAA04 rejection without a safely rotatable receiver identity terminates rather than retrying a guessed challenge.
- Virtual tunnel subscriptions, StartHID, HID reports and EA/touch data are ignored until MFi verification succeeds and 0xAA05 is accepted into the local iAP2 send queue. If AA05 cannot be queued, the authentication callback and MIB3 burst are suppressed.
- Test-only verifier implementations remain in src/test; public class constructors are internal to prevent external API callers from injecting a fake verifier.

### E2LB 0x4300 / 0x4301
- 0x4300 uses the reliable iAP2 send window and retransmission queue, not fire-and-forget.
- The channel records submission time, first wire-send time and exact sequence; ACK waiters are notified on every inbound frame (including ACK-only frames), timer transition and link termination.
- The sender waits through the remaining bounded retry budget for the exact cumulative ACK before classifying availability.
- A 0x4301 response without the exact 0x4300 cumulative ACK is classified START_SESSION_WITHOUT_LINK_ACK and blocked from endpoint handoff. Application response cannot substitute for transport ACK.
- Invite/Wi-Fi alternative handoff is permitted only after 0x4300 itself is cumulatively ACKed.
- Fallback learning is bound to the exact observed 0x4300 sequence; null/mismatched receipt sequence cannot trigger a restart fallback.
- The R57 fixes for earliest retransmission deadline and late SYN-ACK false acknowledgement remain in the patch base.

### Diagnostics and tests
- IAP2_AUTHENTICATED means local MFi verifier success plus successful enqueue of AA05; it does not claim peer ACK.
- IAP2_AUTH_SIGNAL_UNVERIFIED never clears the diagnostic MFi blocker.
- Added regressions for duplicate/out-of-phase certificates, verifier exceptions, pre-auth HID/subscription/EA suppression, authenticated HID/EA forwarding, exact ACK wait, 0x4301 without ACK, alternative-handoff gating and exact-sequence fallback.
- Fixed two issues exposed by the first full R58 CI run: an ACK test now uses the actual send timestamp instead of assuming the handshake clock starts at zero; the R58 changelog Chinese heading is normalized to the release-notes parser's required 简体中文 label.

## Local validation
- Exact R58 patch replay from clean R57 HEAD: passed; 830 files and exact candidate tree fingerprint.
- Kotlin/JVM focused regression suite: 53/53 passed (Iap2LinkEngineTest and Iap2AvailabilityProgressTest under a minimal JUnit-compatible runner).
- Kotlin/JVM compilation: Iap2LinkEngine, DuplexStream, Iap2LinkChannel, Iap2AvailabilityProgress, MFi verifier contract and strict TLV parser passed.
- Real in-memory two-ended iAP2 link smoke: exact observed control ACK returned PEER_ACKED and a non-null wire sequence.
- Python diagnostic/logbot tests: 23/23 passed.
- git diff --cached --check: passed.
- Full Android Gradle unit tests, Lint and APK builds: final R58 CI rerun pending.

## CI history
- Initial R58 workflow run failed its source-tree fingerprint because the newly added workflow hash script escaped the NUL/newline separators incorrectly. The workflow was corrected to use the same canonical delimiters as R56/R57.
- The next R58 CI run passed source reconstruction, R57/R58 patch replay, R58 tree fingerprint, Spotless audit, APK packaging, APK metadata and signature verification. Two tests failed: the absolute test clock assumption and the changelog heading. Both are fixed in this final candidate patch and require a fresh full CI rerun.

## Six-role adversarial review status
Reviewed Bluetooth/RFCOMM lifecycle, iAP2 sequence/ACK state, MFi trust boundary, E2LB/Wi-Fi handoff, concurrency/waiter lifecycle, and negative/regression tests. This is a role-based review by one assistant, not six independently executing agents; independent-agent sign-off remains outstanding.

## Release blockers / not verified
- No authorized MFi trust anchors, licensed signature profile or real challenge/response vectors are present. The production verifier therefore intentionally returns TRUST_MATERIAL_UNAVAILABLE. This prevents false MFi success but also means real MFi authentication is not yet implemented.
- No vehicle-side raw 0x4300 ACK/0x4301 capture has been supplied; no claim that the original vehicle SYN restart root cause is fixed.
- No real vehicle validation of 0x4300, 0x4301, Wi-Fi handoff, AirPlay SETUP/RECORD, video, audio, touch or reconnect.
- No physical device install/launch/crash validation performed in this environment.
- Candidate only. No stable release or formal Release created.
