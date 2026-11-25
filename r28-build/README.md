# R28 / 0.1.15 — reviewed UI candidate

This is a staging configuration, not a completed R28 source import. The exact reviewed delta must be uploaded to `r28-build/R28-from-R26.patch` before running the R28 workflow. The existing R26 workflow and history are unchanged.

## Reproducibility

- Pinned R26 base: `2bdb7948375669cbd63f892bf83ecaa4faf2c272`
- R26 fingerprint: 603 paths, `a45186491113b533fa7c56c3ff3735b75550b166b120ecb5b50fa81a3f3aa2d5`
- R28 patch SHA-256: `a0515024efd17896978ec7e1fa448831c9e919411979c4614642f9596ddec970`
- Expected R28 app fingerprint: 612 paths, `c5e5a3b16b120ef6e958d49b8597e30e3deb2cdb1bce8806ecd419e322496a60`

Local patch application was checked against the original R26 ZIP. All app files after applying the delta match the R28 ZIP byte for byte. Android compilation is pending; local Gradle wrapper could not resolve services.gradle.org.

The new CI workflow reconstructs the existing pinned R26 baseline, verifies the exact R28 patch and resulting source, then runs strict formatting, both debug unit-test variants, lint and debug compilation. It does not publish a release, replace signing credentials or modify the main branch. The workflow will trigger on upload of the exact patch to the target branch. Debug APKs are not original-signed upgrade packages.

The R19 baseline Actions artifact is a dependency; it was available at configuration time, with expiry 2026-12-22.
