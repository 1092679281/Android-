# R11 车机侧模拟测试台：不是 Android 手机测试

这是独立于手机 APK 的 Linux 虚拟车机接收端实验环境。CI 在 Ubuntu24.04 上检出开源 AllPlay GPLv3 项目固定版本，构建 CarPlay 接收器、密码学/配对协议测试和屏幕解码器。

- 生成 1920×720、60fps、3 秒、180 帧 H.264 测试信号；
- 通过接收端的 FFmpeg + SDL2 模拟车机屏幕解码，导出 car-screen.png；
- 记录解码帧数、接收端丢帧、present 调用计数、软件解码吞吐与渲染速度；
- 执行 RTSP /info 二进制 plist/OPTIONS、iAP2 和加密协议测试；
- 使用 AllPlay fake_phone 和独立接收端走 RTSP 配对、加密视频、触控回传，日志分别保存；
- 测试报告自动上传 Actions Artifacts，任何失败不伪装为成功。

**限制非常关键**：合成源不是用户的 R10 安卓 APK；模拟接收器也不是别克 2023 款君越原厂车机。这里的 FPS 数据来自 Linux 软件解码与虚拟 SDL 屏幕，绝不是君越的最终呈现帧率。此测试无法证明真实车机的无线配对、硬件解码、车载导航与方向盘操作。实际兼容性需要真实手机+君越以及车机固件信息、脱敏日志与停车时的屏幕录像来验收。

构建测试环境不刷写或侵入任何车机固件，也不触碰未经授权的网络。

## 绿屏缺陷修复（R11 补充验收）

旧测试用的 AllPlay `video_probe` 在 `SDL_RenderPresent` 后才调用 `dumpRender`，在 Linux/Xvfb 软件渲染下会读到无效后缓冲，产生全绿假截图。之前只检查 PNG 大小和解码计数，没有检查实际像素，因此误报通过。测试现在对 *CI 的 AllPlay 源码检出* 进行严格匹配的截图时序修正，把最终帧截图移到 Present 前；截图仍从真实 SDL 渲染输出获取。新增 `r11_validate_car_screen.py` 验证 1920x720 PPM 实际像素的 RGB 色彩对比度，防止全绿、全黑、纯色错误通过。报告另附 `car-screen-color-report.json`。这不修改用户手机 APK 或君越原厂车机。

## 严格像素验收发现真实 SDL 软件纹理绿屏

截图移到 `SDL_RenderPresent()` 前后仍产生 RGB≈(0,135,0)，证明不只是取帧时序问题，软件渲染路径还存在 YUV 空纹理/色彩输出异常。现在在 CI 检出的固定 AllPlay 版本中为 **SDL 软件渲染器**使用 FFmpeg libswscale 将真实解码 AVFrame 转换为 `RGB24`，再通过 `SDL_UpdateTexture` 上传，保留硬件渲染器原有快速路径。`r11_validate_car_screen.py` 继续检查最终截图的 RGB 分布，只有彩色画面确实呈现才允许通过。此变更是模拟车机端的实验修正，不会修改安卓 APK、君越原厂系统或宣称原厂 60FPS。
