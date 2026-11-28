# R56 source reconstruction / R56 源码重建

**Canonical candidate:** R56 / 0.1.43. This is not a stable release and is not vehicle-validated.

## Source of truth

- Repository: `1092679281/Android-` (patch/reconstruction repository; not an Android project at root).
- Maintenance branch: `maintenance/r56-source-of-truth`.
- Exact baseline: R44 / 0.1.31, source artifact from workflow run `45596424156`, artifact ID `15014496262`.
- Baseline archive SHA-256: `d7e3ea795ee908bd77e3f920511f3f0f532ba63b182df23a57624ca58fcc321b` (authoritative exact-baseline pin).
- The embedded R44 per-file TSV contains 647 valid entries; 578 match the files in that pinned archive and 69 do not. This pre-existing manifest inconsistency is reported but is not used as a gate; the archive SHA-256, ordered patch checks and final R56 tree fingerprint are the integrity gates.
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
1. Confirms the R44 embedded TSV structure and reports its 69 stale entries; CI verifies the exact R44 ZIP SHA-256.
2. Verifies every incremental patch against `SHA256SUMS`.
3. Applies R45 through R56 in order, checking each patch before applying it.
4. Applies the R56 source-hygiene patch.
5. Moves historical fingerprints and legacy evidence into `docs/provenance/` and `archive/`.
6. Verifies the final 827-file source tree against the pinned fingerprint.

Patch order is mandatory; do not apply the R56 cumulative patch on top of incremental patches.

## Durable baseline

The R44 Actions artifact expires on 2026-12-25. The validation workflow archives the verified R44 ZIP as a GitHub Release asset named `r44-source-baseline` before relying on it for subsequent reconstructions. A durable Library copy is also kept under `/mcarplay/02-baseline/R44/`.

## Release and security policy

- R56 is a source candidate only. Do not tag it as a stable release before complete Android CI and E2LB vehicle acceptance.
- Do not commit signing keys, keystore passwords, `local.properties`, APKs, raw diagnostic logs, or personal data.
- MFi cryptographic verification, E2LB 0x4300 acknowledgement, 0x4301/Wi-Fi handoff and AirPlay vehicle acceptance remain unresolved or unverified.

## R58.5.1 MFi 失败收敛

R58.5.1 不伪造 MFi 成功，也不实现未经授权的密码学验证。它将缺少信任材料和明确密码学拒绝标记为终止性认证阻塞，停止同一车机的自动重连，并在 Bluetooth 与 AirPlay 虚拟 iAP2 两条路径上统一上报失败。只有接入获授权的验证器/信任材料后，手动重试才有意义。

该补丁不会解除当前 MFi 认证阻塞；在获得授权验证器和真车证据前，仍不得将候选标记为已完成 CarPlay 真车验收。

## R58.5 标准版在线更新

应用首页的「检查更新」读取本仓库的 GitHub Releases。发布流程使用维护分支重建并通过 CI 的源码，
按发行标签写入 APK 版本，使用固定证书签名，再生成标准 APK 与 `SHA256SUMS.txt`。
`remote` 是另一包名，继续通过自己的诊断产物分发。

- 在 GitHub Actions 配置已有的 `RELEASE_KEYSTORE_B64`、`RELEASE_STORE_PASSWORD`、
  `RELEASE_KEY_ALIAS`、`RELEASE_KEY_PASSWORD`，并将签名证书公开指纹配置为变量
  `OTA_SIGNER_SHA256`。已有正式安装应继续使用其原签名密钥。可以从原 APK 的
  `apksigner verify --print-certs` 输出读取证书 SHA-256。密钥和密码应存放在仓库 Secrets。
- 在已审查的维护提交上推送递增标签，例如 `v0.1.46-test.1`。工作流通过证书、
  版本和 SHA-256 检查后创建本仓库的 Release 草稿；审核说明和验证范围后再公开。
  应用只会发现已公开、有匹配 APK 的发行项。签名不匹配、版本退回和重复标签都会阻止发布。
- PR 演练使用单次测试密钥签发两个版本，在 Android 17 模拟器覆盖安装，检查版本、
  安装记录和已有通知授权。测试证书只用于该次演练。
