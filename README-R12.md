# R12 — 自动识别已连接车机 Wi-Fi，不破坏原 CarPlay 协议

本次根据手机连接页（蓝牙 iAP2 已认证但一直 ENDPOINT_PENDING）与君越车机 Apple CarPlay 无法连接界面修复 **安卓手机明明连接 Wi-Fi、应用却不知道** 的问题。

**原问题**：车机 Wi-Fi 经常没有互联网，所以 HyperOS 仍让移动数据作为系统默认网络。R10 的 WifiCarPlayConnector 只认 activeNetwork（可能是 4G/5G）和应用已绑定的 Wi-Fi，漏掉尚未绑定的唯一 Wi-Fi。Android 13+ 的 NEARBY_WIFI_DEVICES 权限也不能代替读取 SSID 所需的精确定位权限。因此 UI“车机热点”只等 0x5703，不显示手机实际连接的 Wi-Fi。

## R12 修复
- 优先已经绑定的 Wi-Fi / 系统 active Wi-Fi；都不存在时只在 **系统只有一张 Wi-Fi 网络** 时选择它作为 *待核验候选*。两张以上绝不猜选。
- 通过相同选网路径读取当前 SSID，使用独立状态文本显示 **手机当前 Wi-Fi**，与 **车机通过 iAP2 0x5703 / 0x4301 提供的热点 SSID** 严格区分，不把候选当作配对成功。
- Android 13+ 首次请求一次可选的“精确定位”权限以读取 Wi-Fi 名称；拒绝后仍继续此前的蓝牙／CarPlay 流程。Android 12 已有权限流程不改。
- SSID 经真正的 iAP2 下发后才进入原协议回调、填写热点输入框；UI 重开而会话仍进行时恢复已经收到的真实 SSID。
- 在 ENDPOINT_PENDING 阶段，已有的 `watchForPendingStartSession` 能观察唯一已连的车机 Wi-Fi，并向用户询问是否确认当前网络。**未经车机凭据、可信 ctrl 邀请或者用户明确确认，不绑定任何未知网络。**
- 无法凭当前 Wi-Fi 名称生成车机密码、公钥、IP 端口或 0x4301；R12 不会尝试伪造这些数据、不修改车机认证机制。
- 继承 R5–R10 的 H.264、音频队列、触控、安全配对、R9 一键连接和 R10 源端帧率协商补丁。

## 测试
新增 JVM 单测：蜂窝默认但唯一车机 Wi-Fi、多个 Wi-Fi 禁止猜选、绑定优先与失效绑定、未知 WLAN 禁止自动绑定、旧车机连接不得串车、有效邀请允许原有网络交接。CI 同时执行全套单测、Lint、Spotless 和 Debug APK 构建，导出 SHA256SUMS。

**未在 2023 款君越实车完成端到端连接测试。** 成功识别 SSID 不代表车机一定下发 0x4301。需要停车状态安装 R12，打开系统 WLAN 连接君越、在软件内尝试连接；如果显示了实际 Wi-Fi 但仍是 ENDPOINT_PENDING，导出脱敏诊断报告，排查 0x4300/0x5703、ctrl 邀请、mDNS 和 AirPlay 端点。
