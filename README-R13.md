# R13 — CarPlay 握手状态、MFi 证据和端点建立审计

以 `feature/r12-safe-automatic-car-wifi-sync` 为基线，保留小米 CarWith → 七路 CarLife → H.264/音频转发 → AirPlay/CarPlay 接收端，不替换车载界面或假称真正的 iOS。

## 改动

1. **显式 iAP2 状态机**：LINK_READY → IDENTIFIED → CHALLENGE_OBSERVED → AUTH_SIGNAL_SENT_UNVERIFIED → WAITING/DISCOVERING/DIRECT_ENDPOINT。顺序错误会在调试构建中报错；车机是否接受仍由后续 AirPlay 配对、SETUP 和 RECORD 证明。
2. **MFi 结果分离**：
   - 收到 0xAA03：`RESPONSE_UNVERIFIED`，只代表看到挑战响应。项目尚未进行 Apple MFi 证书或签名验证。
   - 全部静默但蓝牙仍存活：`TIMED_OUT`。为了避免破坏既有车机兼容性，仍可发送 0xAA05，但日志明确标识为**未验证的兼容尝试**，不能视为认证成功。
   - 收到明确 0xAA04 拒绝且其他候选长度均未成功，或链路已断：`ABORT`，不再假装完成认证。
   - AirPlay 事件/隧道 iAP2 同步修复：显式拒绝后不发送虚假的成功+资源 burst，未进入待挑战阶段的空响应不能报成功。
3. **端点决策与网络归属分开**：
   - 无有效 SSID/网络身份信息：等待，并由现有确认或 ctrl 邀请机制获得授权。
   - 已知/已验证网络但缺少可用地址、合法端口：绑定之后继续 `_airplay._tcp` / ctrl 邀请发现。
   - 0x4301 携带合法端口（1–65535）和可用地址：**网络绑定完成后**可走直接连接。
   - 同一 SSID 的晚到不完整 0x4301 不能让状态机从 DIRECT 降级；换热点仍允许重新发现。
   - 不更改 `WifiHandoffPolicy` 的身份核验/用户确认，未知 Wi-Fi 不会因此获得配对许可。
4. **回归测试**：MFi 真实响应/全部静默/明确拒绝/断链、认证时序、空 SSID、无权限/身份、坏端口、地址缺失、迟到升级/降级、热点变化。
5. **保留 R12 自动识别系统已连接 WLAN 修复**及 R5–R10 补丁。没有修改苹果认证密钥、蓝牙伪造 MAC、AirPlay 加密层、视频传输格式或 CarWith 原始画面。

## 编译

GitHub → Actions → **LaCrosse R13 CarPlay handshake state and endpoint audit** → Run workflow。
CI 克隆固定上游 `wangxso/mcarplay@8e25e0f69ab7a3bec14649542adea6eb22f74f9a`，顺序运行 R5–R13 注入及全套 JVM 单测、Spotless、Lint、Debug APK 编译。成功才发布 `LaCrosse-R13-handshake-state-debug`，附 `SHA256SUMS.txt`。

## 如何验收（须在停车状态）

- 蓝牙 iAP2 有 `0xAA03` 时应看到 `RESPONSE_UNVERIFIED`；只有 `0xAA05` 不能写成“车机认证成功”。
- 明确 `0xAA04` 且无任何可用挑战成功时要停止当前认证；不得进入假成功资源突发。
- 热点 SSID 读取不到时不得伪造密码、开放网络或 AirPlay 端点；空端点允许保活并等待新 `0x4301`。
- 已授权且确有合法 IP:port 时可直接尝试连接；无有效端点时仍等待 ctrl 邀请或 mDNS。
- 最终成功必须确认车机屏幕实际出画、触摸回传、音频与断开重连；APK 编译通过**不等于**上述实车验证通过。

**限制**：本仓库没有提供 Apple 授权的 MFi 证书/签名校验，因此任何内部 `IAP2_AUTHENTICATED` 旧里程碑只表示发送过本机 `0xAA05`，不代表真正 iPhone 身份或对端认证通过。实际车辆兼容性仍需要停车实测与脱敏日志。
