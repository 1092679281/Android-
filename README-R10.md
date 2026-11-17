# R10 — 源端真实帧率协商，非伪 60FPS

R9 虽有 30/60 设置，但 CarLifeStateMachine 仍按 CarLifeProtocol.DEFAULT_FPS(30) 初始化 CarWith 源。R10 在不修改安全认证和传输格式的情况下，把用户选择的目标帧率向下传递到 CarWith VIDEO_ENCODER_INIT。

改动：CarLifeSession 新增源帧率参数；CarLifeStateMachine 编码请求携带 fps 字段；SessionController 在车机明确报告 maxFPS 时取 min(用户要求, 车机上限)。未知上限按用户要求发起请求，绝不声称车机有此能力。CarWith 的 VIDEO_INIT_DONE 实际响应帧率单独记录，不能当成车机最终显示帧率。

现有 100% 画面缩放默认值保留。CarWith 请求源的长边仍受 1920 像素上限约束；把缩放调到 160% 并不会增加源画面细节，反而可能造成转码和卡顿。优先保持车机实际纵横比，使用接收端声明的原生画布。60FPS 模式只有车机、CarWith、手机编码能力、网络和显示刷新同步支持时才可能实现。

### 未包含
真正的 iOS 系统、苹果 CarPlay 界面和 Siri 无法由 Android 安装包变成原生功能。R10 仍显示 CarWith 车载画面。实现高度还原的 CarPlay 风格车载桌面，需要单独开发可交互 Android 渲染层，替代当前 CarWith 作为视频源，并完成触控、媒体、导航与应用生命周期重构。

CI 单测和安卓编译不能证明实车持续 60 帧；需驻车测试真实车机的解码画面、掉帧、输入延迟和连接稳定性。R9/R8 保留作回退。
