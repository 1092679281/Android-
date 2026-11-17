#!/usr/bin/env python3
"""CI-only repair of AllPlay video_probe screenshot timing.

The pinned upstream video_probe calls dumpRender after SDL_RenderPresent.
SDL explicitly does not guarantee the backbuffer after Present; on headless
software renderers the final image can be solid green. Capture the composited
frame before Present, following allplay_host's existing correct sequence.
Changes only the temporary checked-out test receiver, never the user's APK.
"""
from pathlib import Path
import sys

p = Path(sys.argv[1])
src = p.read_text(encoding="utf-8")
render = """        SDL_RenderPresent(ren);

        if (!reported && vw > 0 && vh > 0) {"""
fixed = """        // Snapshot the actual composited car-side image BEFORE Present.
        // The backbuffer is undefined once SDL_RenderPresent has executed.
        if (!opt.dump.empty() && !dumpCaptured &&
            ((opt.frames > 0 && fedTotal >= size_t(opt.frames)) ||
             (opt.frames == 0 && fedAll && now - doneAt > 400))) {
            if (!allplay::dumpRender(ren, opt.dump)) {
                std::fprintf(stderr, "[probe] ERROR: car-side screenshot readback failed\\n");
                return 4;
            }
            dumpCaptured = true;
        }
        SDL_RenderPresent(ren);

        if (!reported && vw > 0 && vh > 0) {"""
init = """    bool         reported = false;"""
initFixed = """    bool         reported = false;
    bool        dumpCaptured = false;"""
late = """    if (!opt.dump.empty()) allplay::dumpRender(ren, opt.dump);"""
lateFixed = """    if (!opt.dump.empty() && !dumpCaptured) {
        std::fprintf(stderr, "[probe] ERROR: failed to capture a final composited frame\\n");
        return 4;
    }"""
for old,new,label in [(render,fixed,"pre-present"),(init,initFixed,"capture guard"),(late,lateFixed,"remove invalid late readback")]:
    if src.count(old)!=1:
        raise SystemExit(f"BLOCKED: {label} anchor count={src.count(old)}, AllPlay source changed")
    src=src.replace(old,new)
p.write_text(src,encoding="utf-8")
print("AllPlay video_probe fixed: car-side snapshot read before SDL_RenderPresent")
