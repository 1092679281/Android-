# R57 / 0.1.44 candidate: link reliability and ACK integrity

Base: exact R56 tree 29bd33771f52538d918b8f9c2a66e6822b84d3e2c65a9817aff926dcde5fbec5.
This maintenance delta does not modify the historical R44–R56 patches or their verification script.
Patch SHA-256: a49d62a32917da3aa33e53c11aa92116ad039175a714bdeb002973bb3967d270.
Candidate: 827 files, tree SHA-256 c0a92358ca8a283ad73f041274ef7915b15f7a10e5c9c45640f0e5f82ed91318.

## Reproduced defects and changes
- Iap2LinkEngine.drainSendWindow overwrote the minimum retry deadline with a newly queued reliable packet's later deadline. The minimum outstanding deadline is now preserved. Test failed before (4100 expected, 7900 actual), passed after.
- Iap2LinkEngine.processFrame allowed a valid-looking SYN-ACK in NORMAL after control data had been sent to advance the cumulative ACK and falsely mark an observed availability receipt PEER_ACKED. A late SYN-ACK is now ignored in that state; genuine bare cumulative ACKs still confirm the receipt. Test failed before (FRAME_GENERATED expected, PEER_ACKED actual), passed after. Negotiation before the first control send and pure-SYN rebuild behavior remain unchanged.
- LogContractTest previously failed because tools/logbot/rules.py used an obsolete BLUETOOTH stage label. Synchronized rules and AI prompt.
- ForbiddenAudiReplayTest expected multiple attempts after a first-use Pair-Setup 403 without saved identity. Current production PairingHandshake rejects untrusted identity and AirPlayClient stops. Updated the replay to require a single Pair-Setup, no Pair-Verify, no keys, forbidden flag; existing PairingRejectionTest checks transient retry delay. Production trust policy is unchanged. Android integration replay still requires CI.

## Local validation
- Exact Kotlin sources: Iap2LinkEngineTest (38 methods, 36 pass/2 fail before, 38 pass/0 fail after), compiled and run using kotlinc and a minimal JUnit-compatible harness, not Android Gradle.
- Python logbot.test_diagnose: 15/15.
- git diff --check passed; exact candidate patch replay from the CI-produced R56 source archive succeeded; 827 files retained, exact candidate tree verified.
- Reviewed the engine's reader/pacer locking in Iap2LinkChannel, handshake entry, retransmission paths, and existing sequence wrap, duplicate frames, queued receipts, no-ACK and restart tests. This is a focused single-assistant review, not independent six-agent whole-project approval.

## Unresolved release blockers
MFi cryptographic verification is still unimplemented: the authorized trust anchors, signature profile and identity-binding materials have not been supplied. The historical unverified 0xAA05 compatibility path remains; this patch does not endorse it or claim authentication. Observed 0x4300 remains passive and there is no real vehicle ACK evidence; no retransmission policy or payload shape is guessed. Root cause of E2LB's actual SYN restart remains unproven without raw frames and vehicle-side evidence. No real 0x4301, Wi-Fi handoff, AirPlay, media, touch, or reconnect validation. No real vehicle/device access, APK install or startup validation. No stable release authorized.
