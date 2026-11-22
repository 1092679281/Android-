#!/usr/bin/env python3
"""Verified, exact-match Android compiler fixes on top of audited R20."""
from pathlib import Path
import sys

root=Path(sys.argv[1])
video=root/'app/src/main/java/com/mcarplay/app/video/VideoSender.kt'
source=video.read_text(encoding='utf-8')
old='runCatching { externalVideoSource.requestKeyFrame() }'
new='runCatching { externalVideoSource?.requestKeyFrame() }'
if source.count(old)!=1:
    raise RuntimeError(f'Expected exactly one nullable external video source IDR call, found {source.count(old)}')
video.write_text(source.replace(old,new,1),encoding='utf-8')
print('R20 compile fix: optional video source IDR request safely guarded')
