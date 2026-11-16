# LaCrosse / HyperOS · R6 iOS-inspired UI + video cadence hardening

分支 `r6-ios-stability-hardening`，不会覆盖原有 R5 `main`。

**实际包含：** 视频发送侧 30/60 FPS 准确性修正、相同 PTS 与真实回退分离、时钟回退处理、iOS 风格分组卡片 / 字体 / 按钮布局可读性改良。没有修改协议，不强制开启 60 FPS。

GitHub Actions 工作流 **LaCrosse R6 iOS + cadence APK** 的成功产物为 `LaCrosse-R6-debug-apk`。只有通过 Kotlin 单测、UI 对抗检查、Spotless、Lint、Android APK 编译后才上传。

详见 [严格审查报告](AUDIT-R6.md)。这不是完整 R3 重构版，实车性能仍待验证。
