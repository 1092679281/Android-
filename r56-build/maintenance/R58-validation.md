# R58 / 0.1.45 maintenance candidate — MFi fail-closed and E2LB ACK closure

Base: R57 / 0.1.44 exact candidate source tree.
R57 base tree SHA-256: c0a92358ca8a283ad73f041274ef7915b15f7a10e5c9c45640f0e5f82ed91318 (827 files).
R58 candidate tree: 830 files.
R58 tree SHA-256: 5567e7c633be5e466b0f8ce3a09726caf9f79c0704e872eadd7a8e77a9f325a7.
Patch format: unified=1; exact replay against the R57 source archive passed.
Uncompressed patch SHA-256: c102471df3b028f1809a26358b5c322164e58b7d0f00f756e484ce6c49818882.
Compressed patch archive SHA-256: 91d3b6ae5436dde82d768481d9881622d38aacfd6c7f02554440d8cf129a0ae8.

## Findings and changes

### MFi authentication boundary
- Both Bluetooth iAP2 and virtual iAP2 tunnel paths now require strict 0xAA01 and 0xAA03 TLV structure before verification.
- The verifier contract receives the complete 0xAA01 certificate TLV container, the complete 0x1D01 receiver-identification body, the exact challenge and the signature. This preserves the inputs needed for certificate-chain and receiver-identity binding under the authorized MFi profile.
- Production default is TRUST_MATERIAL_UNAVAILABLE and fails closed. Only a verifier result of VERIFIED can emit 0xAA05, mark IAP2_AUTHENTICATED or trigger the authentication burst.
- Verifier/provider exceptions are mapped to a hard rejection. Out-of-phase duplicate certificate frames cannot replace an outstanding challenge. Explicit 0xAA04 rejection without a safely rotatable receiver identity terminates rather than retrying a guessed challenge.
- Test-only verifier implementations remain in src/test; public class constructors are internal to prevent external API callers from injecting a fake verifier.

### E2LB 0x4300 / 0x4301
- 0x4300 uses the reliable iAP2 send window and retransmission queue, not fire-and-forget.
- The channel records submission time, first wire-send time and exact sequence; ACK waiters are notified on every inbound frame (including ACK-only frames), timer transition and link termination.
- The sender waits through the remaining bounded retry budget for the exact cumulative ACK before classifying availability.
- A 0x4301 response without the exact 0x4300 cumulative ACK is classified START_SESSION_WITHOUT_LINK_ACK and is blocked from endpoint handoff. Application response cannot be substituted for transport ACK.
- Invite/Wi-Fi alternative handoff is permitted only after 0x4300 itself is cumulatively ACKed.
- The R57 fixes for earliest retransmission deadline and late SYN-ACK false acknowledgement remain in the patch base.

### Diagnostics and tests
- IAP2_AUTHENTICATED documentation now means local MFi cryptographic verifier success, not merely a sent 0xAA05.
- Added regression coverage for duplicate/out-of-phase certificates, verifier exceptions, exact ACK wait, 0x4301 without ACK, alternative-handoff gating and exact-sequence fallback.
- Test doubles are explicitly test-only and do not implement or claim MFi cryptography.

## Local validation
- Exact R58 patch replay from a clean R57 HEAD: passed; 830 files and exact candidate tree fingerprint.
- Kotlin/JVM compilation: Iap2LinkEngine, DuplexStream, Iap2LinkChannel, Iap2AvailabilityProgress, MFi verifier contract and strict TLV parser passed.
- Real in-memory two-ended iAP2 link smoke: exact observed control ACK returned PEER_ACKED and a non-null wire sequence.
- Python diagnostic/logbot tests: 23/23 passed.
- git diff --cached --check: passed.
- Full Android Gradle unit tests, Lint and APK builds: pending R58 GitHub Actions; not claimed locally.

## Six-role adversarial review status
Reviewed Bluetooth/RFCOMM lifecycle, iAP2 sequence/ACK state, MFi trust boundary, E2LB/Wi-Fi handoff, concurrency/waiter lifecycle, and negative/regression tests. This is a role-based review by one assistant, not six independently executing agents; independent-agent sign-off remains outstanding.

## Release blockers / not verified
- No authorized MFi trust anchors, licensed signature profile or real challenge/response vectors are present. The production verifier therefore intentionally returns TRUST_MATERIAL_UNAVAILABLE. This prevents a false MFi success but also means real MFi authentication is not yet implemented.
- No vehicle-side raw 0x4300 ACK/0x4301 capture has been supplied; no claim that the original vehicle SYN restart root cause is fixed.
- No real vehicle validation of 0x4300, 0x4301, Wi-Fi handoff, AirPlay SETUP/RECORD, video, audio, touch or reconnect.
- No physical device install/launch/crash validation performed in this environment.
- Candidate only. No stable release or formal Release created.
