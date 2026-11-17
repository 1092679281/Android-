# R14 — AirPlay SETUP / RECORD 正确性门控

基于 R13，不改小米 CarWith 采集、CarLife 七通道、H.264 / PCM 路径、iAP2/MFi 发包或原有 HomeKit 加密方式。集中修复 AirPlay 初始 SETUP、屏幕流 SETUP、视频 TCP 数据连接和 RECORD 的顺序/结果判断。

## 已确认的旧问题

- **未检查视频数据端口**：SessionController 原来调用 `videoSender?.openDataPort()` 后丢弃结果，即使连接失败也继续 `RECORD`，导致“会话已激活”但没有可发送视频的连接。
- **请求顺序存在不必要阻塞**：屏幕流 SETUP 200 后先运行可选 type-130 iAP 隧道，再连接关键视频 TCP；部分车机在 SETUP 后很快关闭未连接的数据端口。
- **假成功诊断**：初始 SETUP 200 后立即记录 `SESSION_SETUP`，之后 plist 解析失败仍留有成功里程碑；`statusLine.contains("200")` 可能误识别非状态码中的 200。
- **重建状态**：屏幕被车机收回后重建视频流，必须重新连接新 dataPort，才允许 `RECORD(force=true)`。

## R14 修复

1. AirPlayActivationState 明确要求 `SESSION_SETUP_ACCEPTED → SCREEN_SETUP_ACCEPTED → DATA_PORT_CONNECTED → RECORD_ACCEPTED`。原生按流程运行；有一步缺失就不发送 RECORD。
2. 校验**实际 RTSP 200 状态码**；初始 SETUP 200 **且合法 plist 响应可解析**后，才记 `SESSION_SETUP`；屏幕流 SETUP 还需 `streams[].dataPort` 位于 1–65535。
3. 车机 video dataPort TCP `connect()` 成功后才调用 `confirmVideoDataPortConnected()`；失败就结束本轮，记录 `SETUP_FAILED`，不启动后续 RECORD/CarWith。
4. 可选 type-130 iAP 隧道延后至视频 TCP 已建立之后，但仍在 RECORD 前，避免延误车机的视频数据连接窗口。
5. 屏幕 TEARDOWN、会话 TEARDOWN、close、新一轮 SETUP 会使 readiness 失效。恢复屏幕时的 `force=true` RECORD 也要重新完成屏幕流 SETUP+TCP连接。
6. 保留此前车型单次 RECORD/音频补 RECORD 兼容策略，不强制第二次 RECORD，也不自报实车已出画。

## 测试与实际验收

- `AirPlayActivationStateTest.kt` 验证 RTSP 状态码、两次 SETUP、视频 TCP 门控、RECORD 200、重建、取消/重置、音频重复 RECORD。
- `build-lacrosse-r14-apk.yml` 在 R13+R14 基础上运行 Gradle 全套 JVM 单测、Spotless、Lint、Debug APK；成功发布 `LaCrosse-R14-airplay-setup-record-debug` 和 SHA256。
- 驻车实测须依次看到 `SESSION_SETUP`、屏幕流 dataPort、`VIDEO: 数据端口已连通`、`RECORD 完成`、首帧/持续出画。收到 RECORD 200 **只能证明会话请求被对端接受，不能证明车机已渲染**。
- 若无实车日志，不能声称你这台 2023 款君越的 SETUP/RECORD 已真正完成。
