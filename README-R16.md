# R16 — Buick E2LB (Saic General Motors) AirPlay SETUP 500 诊断与有界恢复

## 真实问题定位（来自用户 2026-11-17 14:51 日志）

- `0x1D01` 接收端自报 `model=E2LB manufacturer=Saic General Motors`。
- 蓝牙 iAP2 链路成功；`0xaa01` 证书和 `0xaa03` 签名确实到达，但 R13 已明确标记**未验证**：`RESPONSE_UNVERIFIED`。发送 `0xaa05` 是兼容性信号，**不能据此宣称 MFi 被真实接受**。
- 接收端声明会发 `0x4301`，8s 窗口内及后续保活日志未见。接收端 `ctrl` 邀请**0 次**；`_airplay._tcp` 未发现，AirPlay 地址使用手机已核验热点的**网关:7000 猜测端点**。
- 该端点上 `/pair-setup` 和 `/pair-verify` 都收到 RTSP 200、密钥协商完成。首次 `SETUP /setup` 带 739B 二进制 plist，但车机回 **RTSP/1.0 500 Internal Server Error**。因此既没有屏幕流 SETUP，也没有 RECORD，问题不在 CarWith H.264。
- 日志 `Shizuku 未就绪`、`IDENTITY 未获取本机真实蓝牙地址`，源码 `setupDeviceId()` 会在读不到身份时使用 `02:00:00:00:00:00` 占位。**不能断言**这就是 500 唯一原因。
- 用户截图上的提示「接收端拒绝了 SETUP；请检查 deviceID」是一般排查方向，不是协议确认的错误根因。500 也可能来自尚未满足的 CarPlay 会话授权/时序/字段能力。

## R16 实际改动

- 记录真正的初始 SETUP 状态码（保留 500，不混淆为蓝牙配对失败）及响应体长度、是否使用网关猜测端点、是否使用占位蓝牙 deviceID，**不记录私密 MAC/密钥/密码**。
- 当 **SETUP 返回 500 + 原本不完整的 AirPlay 端点使用网关端口兜底 + 当前没有 ctrl 邀请** 同时满足时，本轮仍按失败清理，但通过现有 `scheduleInviteRetry` **只等待车机发出全新的 ctrl 邀请才发起有限重试**。晚到 `0x4301` 本身走现有异步热更新通道。
- 不在被拒绝的同一控制通道上反复发送 SETUP；不将 500/403/455 当成功；已有真实端点或已获 ctrl 邀请的机型保持原有行为。
- 保留 R15 在线更新功能和 R14 RECORD 门控；补纯 JVM 用例钉死各类返回码与邀请来源条件。
- 按原有 GitHub CI 运行 Gradle 全部测试、Spotless、Lint、APK；R16 测试包仍是 Debug 签名，**不是可连续在线更新的正式发布包**。

## 下次实车验收（停车状态）

1. 车机 CarPlay 设置中确认本机允许/已选 CarPlay 设备，而不只是已连 Wi-Fi 热点；蓝牙仍和同一车机配对。
2. 应用首页「设置」确认**真实本机蓝牙 MAC**（不是 `02:00:00:00:00:00`）。能启用 Shizuku 时先启用；否则先按实际系统设置能否查看/核实后手动填写真实地址，**不要猜测或填写车机 MAC**。
3. 如再次发生 SETUP 500，导出脱敏诊断：`0x4301` 到达时间、`ctrl` 邀请次数、mDNS 结果、`SETUP500 诊断`、`placeholderBluetoothId`、是否有新邀请引发重试。不要公开热点密码或真实设备地址。
4. 成功的下一里程碑是 **`SETUP RTSP 200 + 有效 plist`**，然后才是 `screen SETUP dataPort`、视频 TCP 成功、RECORD 200，最终还要看到首帧/车机出画。

结论：此补丁提高错误解释与有界恢复，不保证从未发送 `0x4301` 的接收端中强行启动 CarPlay，也不伪造 MFi 硬件身份。
