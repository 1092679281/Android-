#!/usr/bin/env python3
"""Patch the pinned, temporary AllPlay test receiver's SDL software YUV path.

On the CI Xvfb/SDL software renderer, an IYUV texture updated with real FFmpeg
YUV samples can nevertheless render solid RGB (0,135,0), corresponding to
black/zero YUV instead of the actual source. Convert YUV420P to packed RGB24
with libswscale and SDL_UpdateTexture in software mode, keeping the upstream
fast IYUV/NV12 texture path unchanged for accelerated renderers.

This is a temporary receiver-side test patch, NOT the user's Android APK.
"""
from pathlib import Path
import sys

p=Path(sys.argv[1])
s=p.read_text(encoding="utf-8")
s=s.replace("#include <algorithm>", "#include <algorithm>\n#include <cstdio>\n#include <cstdlib>", 1)
old="""bool SdlVideoSink::upload(SDL_Renderer* r, const AVFrame* f)
{
    Uint32 fmt = 0;"""
new="""bool SdlVideoSink::upload(SDL_Renderer* r, const AVFrame* f)
{
    // Headless SDL software backends sometimes leave planar YUV textures
    // zero-initialized (visually: RGB 0,135,0). Use an explicit packed RGB
    // path here so the car-side virtual screen actually matches the decoder.
    SDL_RendererInfo rendererInfo{};
    if (SDL_GetRendererInfo(r, &rendererInfo) == 0 &&
        (rendererInfo.flags & SDL_RENDERER_SOFTWARE)) {
        const int pitch = f->width * 3;
        scratch_.resize(size_t(pitch) * size_t(f->height));
        sws_ = sws_getCachedContext(sws_,
            f->width, f->height, static_cast<AVPixelFormat>(f->format),
            f->width, f->height, AV_PIX_FMT_RGB24,
            SWS_FAST_BILINEAR, nullptr, nullptr, nullptr);
        if (!sws_) {
            LOG_ERROR("%s: software RGB swscale conversion unavailable", kTag);
            return false;
        }
        uint8_t* dstData[4] = {scratch_.data(), nullptr, nullptr, nullptr};
        int dstPitch[4] = {pitch, 0, 0, 0};
        const int rows = sws_scale(sws_, f->data, f->linesize, 0, f->height,
                                    dstData, dstPitch);
        if (rows != f->height) {
            LOG_ERROR("%s: RGB conversion failed, rows=%d (expected %d)",
                      kTag, rows, f->height);
            return false;
        }
        // Test-only proof of RGB pixels BEFORE SDL texture upload.
        if (presented_ == 0) {
            const char* dump = std::getenv("R11_RGB_DUMP");
            if (dump) {
                FILE* fp = std::fopen(dump, "wb");
                if (fp) {
                    std::fprintf(fp, "P6\\n%d %d\\n255\\n", f->width, f->height);
                    std::fwrite(scratch_.data(), 1, scratch_.size(), fp);
                    std::fclose(fp);
                    LOG_INFO("%s: wrote software-decoded RGB sample before SDL upload", kTag);
                }
            }
        }
        if (!tex_ || texW_ != f->width || texH_ != f->height ||
            texFmt_ != SDL_PIXELFORMAT_RGB24) {
            if (tex_) SDL_DestroyTexture(tex_);
            tex_ = SDL_CreateTexture(r, SDL_PIXELFORMAT_RGB24,
                                     SDL_TEXTUREACCESS_STREAMING, f->width, f->height);
            texW_ = f->width;
            texH_ = f->height;
            texFmt_ = SDL_PIXELFORMAT_RGB24;
            if (!tex_) {
                LOG_ERROR("%s: RGB texture allocation failed: %s", kTag, SDL_GetError());
                return false;
            }
            LOG_INFO("%s: software renderer uses RGB24 packed texture (%dx%d)",
                     kTag, f->width, f->height);
        }
        if (SDL_UpdateTexture(tex_, nullptr, scratch_.data(), pitch) != 0) {
            LOG_ERROR("%s: RGB texture upload failed: %s", kTag, SDL_GetError());
            return false;
        }
        return true;
    }

    Uint32 fmt = 0;"""
if s.count(old)!=1:
    raise SystemExit(f"BLOCKED: pinned AllPlay upload method changed (matches {s.count(old)})")
p.write_text(s.replace(old,new),encoding="utf-8")
print("Applied RGB24 packed-texture fallback for SDL software car-side renderer")
