# R15 — 手机应用内在线检查与下载新版本（不需要连接车机）

基于 R14 的 CarPlay/AirPlay/CarWith 路径不变。**上游 mcarplay 本来就有「检查更新」界面及 HTTPS 下载、SHA-256、包名/签名/版本验证和 Android 安装确认。**R15 复用该实现，将更新源改为本项目独立的公开二进制发布仓库，源码仍放在私有仓库。

## 手机操作

1. 打开 CarPlay 应用主页，点击 **「检查更新」**（MainActivity 已有入口）。
2. 页面自动检查 `https://github.com/1092679281/CarPlay-Updates/releases` 的版本；也可点「检查更新」。
3. 如果找到 **比本机版本更新** 的发布包，点「下载并校验 APK」；显示进度，支持取消。
4. 下载后校验 SHA-256、APK 包名、版本号、Android SDK 最低要求和**当前安装应用的签名证书**。点「安装更新」，由 Android 系统安装器提示确认。Android 13+/14 对未知来源安装可能需要额外授权。
5. 有 CarPlay/CarWith 活跃连接时禁止更新。不会绕过系统安装许可，不会自动卸载应用/删除数据。

## 配置一次：公开发布仓库（必须由 GitHub 账号所有者创建）

当前源码仓库 `1092679281/Android-` 是 **private**。GitHub Actions artifact 只对授权账号可下载，不能让手机应用直接当公开更新源。**不要把 GitHub Token 放进 APK**。

1. 在 GitHub 创建 **Public** 仓库 `1092679281/CarPlay-Updates`，选择初始化一个 README，确保存在 `main` 分支。此仓库**只发布 APK 和 SHA256SUMS，不包含私有源码**。名称必须与 R15 的 `UpdateSource.REPOSITORY` 一致。
2. 在私有源码仓库 `Android-` 的 Settings → Secrets and variables → Actions 中设置：
   - `RELEASE_KEYSTORE_B64`：用自己保管的 Android **永久签名 keystore** 转 Base64 的内容
   - `RELEASE_STORE_PASSWORD`：keystore 口令
   - `RELEASE_KEY_ALIAS`：密钥别名
   - `RELEASE_KEY_PASSWORD`：密钥口令
   - `UPDATE_PUBLISH_TOKEN`：对 **CarPlay-Updates 单独公开仓库**具有 Contents: Read and write 的 fine-grained token（不要赋予私有源码仓库读权限）
3. 将 `.github/workflows/publish-lacrosse-ota.yml` 放到可用工作流的默认分支。运行手动 workflow_dispatch，输入 `v0.1.8`，构建正式签名 APK，校验后把 `mcarplay-0.1.8.apk` 和 `SHA256SUMS.txt` 发到公开发行页。
4. 在手机 R15 正式签名包上测试「检查更新」。下一个版本应先提升 appVersionName（例 `0.1.9`），使用**同一个** keystore 签名，再发布 `v0.1.9`；手机才会提示新版本。

### 永久签名密钥

可以在本机离线使用 Android Studio 或 Java `keytool` 生成 PKCS#12 密钥。**长期安全备份，不要上传到源码仓库或公开发行页**。需要时可按下例操作：

```bash
keytool -genkeypair -v -keystore carplay-release.p12 -storetype PKCS12 \
  -alias carplay -keyalg RSA -keysize 3072 -validity 10000
# Linux:
base64 -w0 carplay-release.p12
# macOS:
base64 < carplay-release.p12 | tr -d '\n'
# Windows PowerShell:
[Convert]::ToBase64String([IO.File]::ReadAllBytes("carplay-release.p12"))
```

在 Secrets 中输入这些值而非提交到 Git。签名一旦更换，Android 会拒绝覆盖安装原应用。

### 现有 R14 Debug APK 的重要限制

R14 来自临时 GitHub Runner 的 **debug signing key**。本项目没有保存该证书的私钥，因此**无法可靠地用新的正式签名直接覆盖已安装的 R14 Debug 包**。这是 Android 安装安全机制，不能通过修改下载代码绕过。

需要从 R14 Debug 迁移到 R15 正式版本时，要先在手机备份重要设置，再卸载旧 Debug 包并安装一次 R15 正式签名版本。**这一次可能丢失旧应用数据与 Shizuku 授权**。此后使用同一个发布密钥签名的 R16/R17 等版本，才能通过应用内更新保留数据地覆盖安装。

R15 Debug 工作流只是验证更新界面和逻辑；**不能作为未来连续在线升级的签名基线**。签名正式包只有在配置好仓库 Secrets 后由发布工作流生成。

### 安全策略

- 更新 API 固定为 `api.github.com/repos/1092679281/CarPlay-Updates/releases`，只接受 HTTPS `github.com/1092679281/CarPlay-Updates/releases/download/<tag>/<name>` 下载地址及 GitHub 官方 CDN 跳转。
- 不接受其他仓库或自定义主机替换下载地址；不在手机中保存 PAT。
- 必须有可验证的 SHA-256（来自 GitHub API asset digest，或同 release 的唯一 SHA256SUMS）。下载时检查长度、摘要，安装前再校验。
- Android PackageManager 校验包名、`versionCode`、`versionName`、minSdk 和**签名证书**是否匹配。系统安装界面由用户确认。
- 发布脚本**拒绝覆盖已发布标签**、拒绝无签名私钥、拒绝签名版本不一致。用户不能从 private Actions artifact 直接匿名下载安装。

## R15 代码与验证

- `tools/integrate_and_build_r15.py`：在 R14 的完整 patch/JVM test/Lint/Spotless/Debug APK 构建之后，切换自己的 update release 源、调整版本到 `0.1.8`、增加来源防混淆回归测试。带 `R15_SIGNED_RELEASE=1` 时二次构建独立的正式签名 APK。
- `.github/workflows/build-lacrosse-r15-apk.yml`：完整 Android 回归构建（Debug 测试包）。
- `.github/workflows/publish-lacrosse-ota.yml`：配置发布 Secrets 之后，生成**固定签名**的 APK 并发布到公开二进制仓库。
- 未配置公开仓库/发布 Secrets 时，R15 客户端可能显示「没有版本」或 GitHub 404，这是分发渠道尚未上线，不意味着在线更新已可用。
