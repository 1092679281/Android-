# R56 source reconstruction / R56 源码重建

**Canonical candidate:** R56 / 0.1.43. This is not a stable release and is not vehicle-validated.

## Source of truth

- Repository: `1092679281/Android-` (patch/reconstruction repository; not an Android project at root).
- Maintenance branch: `maintenance/r56-source-of-truth`.
- Exact baseline: R44 / 0.1.31, source artifact from workflow run `45596424156`, artifact ID `15014496262`.
- Baseline archive SHA-256: `d7e3ea795ee908bd77e3f920511f3f0f532ba63b182df23a57624ca58fcc321b`.
- R56 full candidate archive SHA-256: `686f1968b5846fe49e55f9b96032c21d77e5408f281d13434b79831d34afcbff`.
- Organized R56 source archive SHA-256: `877a54f7af496ee4f82a2064fbabab7cccbf1b702d2672828f12620252ffebab`.
- Verified organized tree: 827 files; deterministic tree SHA-256 `29bd33771f52538d918b8f9c2a66e6822b84d3e2c65a9817aff926dcde5fbec5`.

## Rebuild

Run from a checkout of this repository:

```bash
# Restore the exact R44 source archive into ./baseline first.
bash r56-build/rebuild-r56.sh ./baseline
```

The rebuild script:
1. Verifies every incremental patch against `SHA256SUMS`.
2. Applies R45 through R56 in order, checking each patch before applying it.
3. Applies the R56 source-hygiene patch.
4. Moves historical fingerprints and legacy evidence into `docs/provenance/` and `archive/`.
5. Verifies the final 827-file source tree against the pinned fingerprint.

Patch order is mandatory; do not apply the R56 cumulative patch on top of incremental patches.

## Durable baseline

The R44 Actions artifact expires on 2026-12-25. The validation workflow archives the verified R44 ZIP as a GitHub Release asset named `r44-source-baseline` before relying on it for subsequent reconstructions. A durable Library copy is also kept under `/mcarplay/02-baseline/R44/`.

## Release and security policy

- R56 is a source candidate only. Do not tag it as a stable release before complete Android CI and E2LB vehicle acceptance.
- Do not commit signing keys, keystore passwords, `local.properties`, APKs, raw diagnostic logs, or personal data.
- MFi cryptographic verification, E2LB 0x4300 acknowledgement, 0x4301/Wi-Fi handoff and AirPlay vehicle acceptance remain unresolved or unverified.
