# R19 — 对抗审查：唯一蓝牙会话所有权 + 严格验证

此分支基于 R18 的真实身份快照、R16 SETUP500 诊断与 R15 更新客户端。针对用户上传的 Buick Link+（其公开源代码在 `imbakings/link_plus`，基于 MIT 项目）进行架构对照，**借鉴设计思路，重新实现本项目自己的会话仲裁，并非直接复制其高权限服务或私有协议代码**。

## 审查一：连接架构/并发 — 当前实施

原来 `BtSessionGate.inboundActive` 只是一个易竞争的全局布尔值：出站 `BluetoothSocket.connect()` 可能已进入系统调用，车机同时 `accept()`，两套 `Iap2LinkChannel` 各自进入 SYN/身份/MFi，直到入站任务晚设置标志才阻止后续新出站尝试。实车日志确实看到主动和被动两条会话交错。

R19 的 `BluetoothSessionArbiter` 提供：

- **唯一 owner/lease**：出站尝试必须在 RFCOMM Socket 创建/连接与 iAP2 会话执行期间持有凭据；完整阻塞操作受 `dispatchIfCurrent` 保护。
- **入站优先但有限制**：入站只可抢占未完成端点交付的出站尝试。已确认的出站 / 已存在的入站不能被抢占。
- **先退出旧，再握手新**：入站抢占后先关闭旧 socket、最多等待五秒旧 lease 退役；未清理则拒绝本次入站，不允许两条 iAP2 同时发消息。
- **迟到连接拦截**：旧出站 Socket 创建、connect() 迟到成功、端点交付、热点回调、代际/观察报告都必须验证当前 lease；Socket 创建后立即注册针对该 Socket 的抢占清理，解决回调先于 `currentSocket` 登记的竞态。旧 lease 清理不能释放新 lease。
- **会话门闸原子性**：AirPlay `sessionActive` 与出站 lease 获取共用仲裁器锁，避免“先检查 false、后被设置 true、仍成功获取 lease”的窗口。
- **异常收敛**：Socket 创建/连接、流构造、会话启动异常都进入统一清理；失败尝试释放 lease，客户端连接循环不因普通运行时异常直接死亡。
- **无死锁原则**：关闭 socket、发回调/日志、等待线程都不在仲裁器锁内进行；取消/超时皆有失败路径。
- **不更改 MFi/SETUP 成功判据**：RTSP 500 仍为失败；没有 0x4301 不能伪报成功。

## 审查二：权限/身份 — 本轮明确边界

- 沿用 R18：后台一次解析并冻结蓝牙 MAC，出站 iAP2 / 入站 iAP2 / ctrl mDNS / AirPlay SETUP 共用。真车不给占位身份放行；测试台可显式选择。
- Android 普通应用读取本机真实经典蓝牙 MAC 是系统级限制；仅凭蓝牙连接授权无法解除。未凭空宣称已新增无需授权的自动 MAC 读取。
- **未移植 Buick Link+ 的内置无线 ADB 服务**：它涉及本机调试配对、密钥持久化、shell 权限和服务启动，需要独立安全审计、用户明确授权、依赖许可证及系统版本测试。不能把第三方特权服务直接复制进本应用，或把 shell 权限当作 CarPlay MFi 身份。
- 自动连接仍必须尊重车机真实认证和系统安装/录屏授权。

## 审查三：协议/回归 — 新增自动化红线

`BluetoothSessionArbiterTest` 独立在纯 JVM 上覆盖 14 个场景：互斥出站、抢占回调恰好一次、旧 owner 不能释放新 owner、迟到回调、健康出站抗抢占、重复入站拒绝、抢占后不得确认、12 线程并发启动、两个实例隔离、AirPlay 活跃门闸、抢占后禁止迟到传输操作、回调异常、退役后的迟到回调。

完整 R7→R18→R19 补丁重放，运行所有既有 JVM 单元测试、Spotless、Lint、Debug APK 构建。CI 使用 `if: always()` 另存原始 JUnit HTML/XML：失败时同样提供可复核证据。构建成功**不代表实车已经显示 CarWith**。

## 当前未宣称完成的事项

1. 本机 ADB 首次配对/自动恢复方案（需要独立权限安全审查）。
2. 车机 E2LB 未发送 0x4301 以及 SETUP 500 的车端原因（需要停车实测）。
3. R17 全链路模拟套件仍有失败记录，不可当作通过；其后续整合需要先稳定实际 TCP 视频用例。
4. 从私有 GitHub 源仓库直接在线更新不可用：需要公开 APK 发行仓库、固定密钥签名、发布证据及版本升级验证。
5. 未把车机桌面/分屏/天气作为本轮连接修复的必要前提。

## 实车验收标准

真实车机在安全停车状态下：`BT-C` 与 `BT` 不再同时执行两套 iAP2 身份交换；完整收到有效 `0x4301` 或其他明确端点证据；`pair-verify` 成功；初始 SETUP RTSP200 且有效 plist；screen SETUP200 + dataPort；真实 TCP 连接；RECORD200；视频首帧被车机显示。任何一环失败都按该阶段报告，不标为“已真实连接”。

## 回滚/保留

R18 最新通过版保留不动，R19 为独立 PR/调试分支。R19 APK 也是 Debug 签名，不能假定可覆盖已装 R18。不会合并到 main 或自动发布正式 OTA。

## R19 本轮二次对抗修复（源码审查中）

- 修复 inbound 在 `createRfcommSocketToServiceRecord()` 期间抢占时，清理回调可能早于 `currentSocket.set()` 执行的窗口；出站 connect 与完整 session 现在都受 lease action 保护，Socket 创建后立即注册针对该 Socket 的清理回调。
- 将 AirPlay `sessionActive` 迁入 arbiter 同一把锁，和 `acquireOutbound()` 原子化。
- 统一 outbound Socket / lease 转移：异常、取消、过期、正常会话分别保证关闭 Socket 与释放 lease，不再把连接线程异常直接抛出而终止循环。
- 将流与 channel 构造纳入 `try/finally`，修复构造阶段抛异常时旧代码未清理 `currentSocket` 的问题。
- 新增 4 个纯 JVM 对抗用例；源审查 CI 必须核验 14 项全通过。
