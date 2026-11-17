# R10 模拟器实测环境

在 GitHub Actions ubuntu-24.04 + KVM + JDK 21 + Android SDK Platform 35 上，从固定上游 wangxso/mcarplay commit 8e25e0f69ab7a3bec14649542adea6eb22f74f9a 开始集成 R5-R10，执行 Spotless、JVM 回归单测、Android Lint 及 APK 构建。

接着用 Android 15（API 35）Google APIs Pixel 6 x86_64 模拟器安装该 APK，实际启动 MainActivity、保存竖屏与横屏截图、UI 层次和完整 logcat，检查进程是否崩溃。构建失败、安装失败或进程退出会阻断测试，成功失败均保存报告。运行入口：GitHub → Actions → R10 Android emulator installation and UI smoke test，或在已有 Android 15 模拟器上使用 adb 执行：
bash tools/emulator_r10_smoke.sh /path/to/R10.apk /path/to/report

该环境 **没有小米专有 CarWith、CarLife 或车机端无线 CarPlay 接收器**，不能测试真实车机配对与 7 路 TCP、真实 H.264 60 帧解码、物理车机触控/音频端到端延迟、原生 iOS 界面。源端 30/60FPS 协商链路另有 Kotlin 单测；最终呈现 FPS 仍需停车状态实车测试与视频/日志证据。
