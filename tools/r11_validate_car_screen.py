#!/usr/bin/env python3
"""R11 visually validate known colourful testsrc2 output, not just decode counters.

The head-unit renderer must create actual RGB image detail. Flat green or
black fail even when decoder/presenter counters are positive.
This is deliberately specific to the multicolour synthetic input testsrc2.
"""
import json
from pathlib import Path
import statistics
import sys

path=Path(sys.argv[1])
out=Path(sys.argv[2])
raw=path.read_bytes()
if not raw.startswith(b"P6\n"):
    raise SystemExit("FAIL: not a P6 screenshot")
lines=raw.split(b"\n",3)
if len(lines)!=4 or lines[2]!=b"255":
    raise SystemExit("FAIL: PPM header invalid")
try:
    width,height=[int(v) for v in lines[1].split()]
except Exception as ex:
    raise SystemExit(f"FAIL: invalid frame dimensions: {ex}")
pixels=lines[3]
if width!=1920 or height!=720:
    raise SystemExit(f"FAIL: wrong rendered dimensions {width}x{height}")
if len(pixels)!=width*height*3:
    raise SystemExit(f"FAIL: wrong pixel count, got {len(pixels)}")
channels=[[],[],[]]
colors=set()
for y in range(0,height,13):
    for x in range(0,width,19):
        k=(y*width+x)*3
        rgb=tuple(pixels[k:k+3])
        colors.add(rgb)
        for i,value in enumerate(rgb):channels[i].append(value)
stdev=[round(statistics.pstdev(c),2) for c in channels]
means=[round(statistics.mean(c),2) for c in channels]
ranges=[[min(c),max(c)] for c in channels]
report={
    "source":"synthetic ffmpeg testsrc2 H264; expected multi-colour 1920x720",
    "screen_size":[width,height],
    "channel_mean_RGB":means,
    "channel_std_RGB":stdev,
    "channel_range_RGB":ranges,
    "sampled_unique_RGB_colors":len(colors),
    "rendered_content_valid":all(v>=35 for v in stdev) and len(colors)>=35
}
out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
print(json.dumps(report,indent=2))
if not report["rendered_content_valid"]:
    raise SystemExit("FAIL: head-unit screenshot is flat/green/black or otherwise missing expected colour variation")
print("PASS: actual car-side RGB screenshot contains high-contrast picture; not a green frame")
