# R17 — 可重复执行的 CarPlay 接收端模拟联调

本分支叠加 R16（君越 E2LB SETUP500、真实邀请恢复）、R15（应用内更新）及 R14（SETUP/TCP/RECORD 门控），**没有宣称真实君越已能投屏**。

## 测试环境：真实 JVM TCP 套接字与模拟 AirPlay 接收器

`src/CarPlayReceiverSimulationTest.kt` 包含一个只绑定 `127.0.0.1` 的虚拟车机。它接收真正的 `AirPlayClient` RTSP 请求，解析实际发送的二进制 plist：

- 模拟车机应答初始 `SETUP /setup` 和 `GET /info`，声明横屏 `1280 × 720`、显示屏 UUID
- 模拟第二次主屏流 `SETUP /`、返回一个真正监听中的 **随机本地 TCP 视频 dataPort**
- 通过真实 `VideoSender.openDataPort()` 完成 TCP 连接；在这个连接成功之前，`RECORD` 必须被门控拦截
- 模拟接收端收到 `RECORD /` 后回复 RTSP 200，然后用真实 `VideoSender` 外部 H.264 输入路径发送一帧包含 SPS/PPS/IDR 的测试帧
- 接收端真正从 TCP 读出 128 字节 AirPlay 屏幕消息头、VideoConfig(avcC) 与 VideoFrame 的 **两个 opcode（1、0）**，验证消息边界
- 模拟你真实日志的 `RTSP 500`：初始化失败不执行后续 SETUP/RECORD，记录真正确切的响应码和占位蓝牙 MAC 判据，只在假设“网关端点且从未邀请”的条件下进入等待新邀请策略
- 模拟 200 但是 plist 损坏：**不能**认为会话建立
- 模拟第二次 SETUP 正常，但 TCP 端口未打开：阻止 RECORD
- 另一个测试复用上游参考 SRP6a 接收端模型 `AirPlayPairingTest.MockReceiver`，做完整 PairSetup + PairVerify，核对收发加密密钥方向

此套件比只编译 APK 或跑状态机纯函数更能验证当前实现。它对实际代码走 Loopback socket、二进制 plist、真实 TCP 视频端口、VideoSender 封装及密码学算法。

## 自动执行

创建 PR 后，`.github/workflows/build-lacrosse-r17-apk.yml` 取得固定上游源码，注入 R7→R16→R17 全部修改，执行：

```bash
./gradlew --no-daemon spotlessApply spotlessCheck \
  :app:testStandardDebugUnitTest :app:lintStandardDebug :app:assembleStandardDebug
```

R17 脚本会额外检查模拟套件 JUnit XML 中的**全部 5 个用例必须存在，且 0 failed / 0 skipped**。通过后才上传 APK，同时生成：

- `mcarplay-LaCrosse-R17-simulator-tested-debug.apk`
- `SHA256SUMS.txt`
- `SIMULATION-RESULTS.md`
- `CARPLAY_SIMULATION_JUNIT.xml`

## 重要限制

本地模拟器 **不是** Apple CarPlay 认证车机、也不是君越 E2LB 固件。它无法模拟手机与汽车的实际蓝牙 RFCOMM/iAP2 链路、MFi 芯片认证、车机的 `0x4301` 发包时序、Wi-Fi mDNS、车机 UI 切屏策略、实际 CarWith 采集或手机硬件编码器。测试中的 AirPlay 配对是参考密码学接收器，**没有**把参考密码学模型与加密 RTSP TCP 全链路连成一套真实车机替代品。测试 H.264 数据只能证明封装和发送，不证明车机解码或出画。

**因此**：本地测试全绿 = 软件能和我们定义的模拟接收器握手并发视频，**不等于**真实 2023 款别克君越能完成 SETUP/RECORD。

### 接下来真实车机要达到的证据链

`0x4301 / ctrl 正式邀请 → 已知真实 AirPlay 端点 → 配对 → SETUP RTSP 200 → /info → 屏幕流 SETUP RTSP 200(dataPort) → TCP 连接成功 → RECORD 200 → 视频首帧 → 车机出画`

如果真车仍回 500，应继续分析其合法请求字段、真实本机身份、接收端启动前置条件，而不是修改模拟接收器让它返回 200 来假装问题解决。
