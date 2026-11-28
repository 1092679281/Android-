# Android APK 签名与跨会话维护记录

> 本文件是 Android 项目的长期签名操作记录。新聊天窗口、CI 维护和 APK 发布都必须先读取本文件。
> 
> **安全规则：** 本文件只记录公钥证书指纹、包名、流程和 GitHub Secret 名称。禁止写入 keystore、Base64 私钥、密码、恢复码或任何可用于签名的秘密。

## 1. 固定规则

1. **正式安装包统一使用固定签名的 `StandardRelease`。** 正式更新只能由仓库的签名 OTA 工作流构建和发布。
2. `StandardDebug` / `RemoteDebug` 仅用于开发、测试和 CI 验证。GitHub Actions 临时 runner 生成的 Debug keystore 不保证跨运行相同，Debug APK 不得作为长期升级包发布。
3. 禁止为了让一次构建通过而自动生成新的正式签名密钥；禁止轮换正式签名密钥，除非经过明确的迁移计划和用户批准。
4. 每次正式构建必须核对 APK 的签名证书 SHA-256；缺少密钥、指纹不匹配、签名验证失败或版本倒退时，必须 fail closed，禁止发布。
5. PR 中的 OTA rehearsal 使用一次性临时测试密钥，只能证明同一轮演练中同签名 APK 可以覆盖安装，**不能**证明它与正式签名证书相同。
6. 签名私钥只保存在 GitHub Actions Secrets 和用户本地加密离线备份中；绝不提交到 Git、上传到聊天、贴到 issue/PR 或放入构建产物。

## 2. Android 应用身份

| 变体 | applicationId | 用途 |
|---|---|---|
| Standard | `com.mcarplay.app` | 日常安装和正式 OTA |
| Remote | `com.mcarplay.app.rd` | 独立诊断/测试安装，不是 Standard OTA 包 |

正式 OTA 工作流目前只构建并发布 Standard APK。Remote 包名不同，不能与 Standard 混为一谈。

## 3. 正式签名配置

仓库 `.github/workflows/publish-lacrosse-ota.yml` 已使用以下持久化配置：

| GitHub 配置 | 类型 | 用途 |
|---|---|---|
| `RELEASE_KEYSTORE_B64` | Actions Secret | PKCS12/JKS keystore 的 Base64 内容 |
| `RELEASE_STORE_PASSWORD` | Actions Secret | keystore 密码 |
| `RELEASE_KEY_ALIAS` | Actions Secret | key alias |
| `RELEASE_KEY_PASSWORD` | Actions Secret | 私钥密码 |
| `OTA_SIGNER_SHA256` | Actions Variable | 正式签名证书的 64 位 SHA-256 指纹 |

工作流会检查 Secrets/Variable 是否存在、验证 APK 签名证书，并在已有 Release 时核对上一版 APK 的证书指纹。正式发布流程不能绕过这些检查。

**配置状态（2026-11-28 检查）：**
- 工作流已引用上述四个 Secrets 和一个 Variable。
- GitHub 不会向普通仓库读取接口返回 Secret 的值；本次检查无法确认这些值是否已经配置、是否彼此匹配。
- 正式签名证书的最终 SHA-256 指纹尚未在本文件中登记。第一次正式发布前，必须从实际 keystore 导出证书并与 `OTA_SIGNER_SHA256`、构建产物指纹逐字核对。
- 如果现有 Secrets 已经包含长期使用的有效 keystore，应继续使用它，**不要另行生成新密钥覆盖**。

## 4. 旧 R58.5 Debug 安装包的已知情况

用户提供的原安装包：`mcarplay-R58.5-0.1.45-standard-debug(1).apk`

已检查信息：
- applicationId：`com.mcarplay.app`
- versionName：`0.1.45-debug`
- versionCode：`1450000`
- Debuggable：`true`
- 旧 Debug 证书 SHA-256：

```text
24abcd283ba26f3d92c7d1d2d683ac02abc4791c52dc10f55e4f3217e46a6176
```

用户确认没有保存生成该 APK 的原始 `debug.keystore`。APK 中的证书是公钥，不能从 APK 还原签名私钥。

因此：
- 新的固定 Release 签名不能冒充上述旧 Debug 签名。
- Android 不允许不同签名证书的 APK 直接覆盖同一已安装应用。
- 第一次从旧 Debug 安装切换到固定签名的 StandardRelease，需要单独制定一次性迁移/重装方案；不要承诺旧包可无缝覆盖，也不要在没有备份和用户确认时要求卸载。
- 此后所有 StandardRelease 更新必须持续使用同一份正式 keystore 和同一证书指纹。

## 5. 正式发布前检查清单

- [ ] 确认 GitHub Actions Secrets 中已有正确的长期 keystore；如果不存在，先由用户在自己的可信电脑上生成。
- [ ] 将 keystore 另存至少一份加密离线备份；记录备份位置，不把密码写入本文件。
- [ ] 将四项 Secrets 配置到仓库 Settings → Secrets and variables → Actions → Secrets。
- [ ] 从 keystore 导出证书，计算 SHA-256，并将小写/大写无关的 64 位十六进制值配置到 Actions Variable `OTA_SIGNER_SHA256`。
- [ ] 用实际正式工作流生成 StandardRelease，使用 `apksigner verify --verbose --print-certs` 检查签名。
- [ ] 确认 APK 签名证书指纹与 `OTA_SIGNER_SHA256` 完全一致。
- [ ] 确认发布版本的 versionCode 严格递增，且上一版 Release APK 使用相同证书。
- [ ] 完成模拟器同签名覆盖安装测试；再由用户确认实际设备迁移方案和车辆验证结果。
- [ ] 只有全部检查通过，才允许把 Release 草稿公开。

### Windows 本地检查命令（密钥只在本机操作）

导出证书并计算指纹（命令会要求输入 keystore 密码）：

```powershell
keytool -exportcert -keystore .\release-signing.p12 -storetype PKCS12 -alias <你的别名> -file .\release-cert.der
certutil -hashfile .\release-cert.der SHA256
```

把 keystore 编码为 Base64 后粘贴到 GitHub Secret 时，只在本机 PowerShell 操作；不要把输出发到聊天或提交到仓库：

```powershell
[Convert]::ToBase64String([IO.File]::ReadAllBytes(".\release-signing.p12")) | Set-Clipboard
```

如果需要创建新的正式 keystore，必须先确认 GitHub Secrets 中没有现存的正式密钥。生成操作、密码和离线备份都在用户自己的电脑完成；助手不需要接收 keystore 或密码。

## 6. CI 与 OTA 工作流行为

- `.github/workflows/verify-r56-source.yml`：负责源码重建、测试、Lint 和 Debug 候选包验证。Debug 包是验证产物，不是正式 OTA。
- `.github/workflows/publish-lacrosse-ota.yml`：
  - PR：生成一次性 rehearsal keystore，构建前后两个测试版本，并在 Android 模拟器上验证同签名覆盖安装；临时密钥只用于本次测试。
  - Tag / 手动发布：读取持久化 Release Secrets 和 `OTA_SIGNER_SHA256`，构建固定签名的 StandardRelease，并验证签名与版本连续性。
- 正式 APK 必须来自上述 OTA 工作流，不得用 Debug artifact 替代。

## 7. 新聊天窗口继续项目时

把以下内容发给新窗口：

> 请先读取仓库 `1092679281/Android-` 的 `docs/ANDROID_SIGNING.md`，严格遵守里面的签名、包名和 OTA 规则。正式包只使用固定签名的 StandardRelease；不要生成或轮换签名密钥，不要索取 keystore/密码，不要把 Debug APK 当正式更新包。开始修改前先核对当前维护分支、提交和 CI 状态。

每次更换正式签名密钥、修改 Secret 名称、正式包名或 OTA 工作流时，都必须先更新本文件并通过 PR 审查。
