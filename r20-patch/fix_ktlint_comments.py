#!/usr/bin/env python3
"""Fail-closed formatting migration for inherited R19 KDoc/adjacent comments."""
from pathlib import Path
import sys

ROOT = Path(sys.argv[1])
PRIOR_KDOC = {
    'app/src/main/java/com/mcarplay/app/MainActivity.kt': '/** After a deliberate first choice, one tap reuses it. */',
    'app/src/main/java/com/mcarplay/app/SessionController.kt': '// 40s 总窗 =',
    'app/src/main/java/com/mcarplay/app/airplay/AirPlayClient.kt': '/** 取消标志（会话退役时置位）',
    'app/src/main/java/com/mcarplay/app/bt/Iap2BluetoothClient.kt': '/** 链路断开：同时携带 RFCOMM',
    'app/src/main/java/com/mcarplay/app/bt/Iap2BluetoothServer.kt': '/** 链路断开：同时携带 RFCOMM',
    'app/src/main/java/com/mcarplay/app/iap2/Iap2LinkEngine.kt': '/**\n     * 回显用的「我方参数」',
    'app/src/main/java/com/mcarplay/app/settings/DisplayPrefs.kt': '// 默认**关**',
    'app/src/main/java/com/mcarplay/app/shizuku/CarInputServiceImpl.kt': '// BlockedPrivateApi/DEPRECATION',
    'app/src/main/java/com/mcarplay/app/transport/Iap2LinkChannel.kt': '// 预算按字节计。',
    'app/src/test/java/com/mcarplay/app/airplay/BinaryPlistTest.kt': '/** 1/2/4 字节整数',
    'app/src/test/java/com/mcarplay/app/airplay/VirtualIap2LinkTest.kt': '/**\n * 按链路帧头拆分',
    'app/src/test/java/com/mcarplay/app/iap2/Iap2SenderSessionTest.kt': '/**\n     * 断开时的 0xEA01',
}
replacements = 0
for rel, marker in PRIOR_KDOC.items():
    path = ROOT / rel
    source = path.read_text(encoding='utf-8')
    if source.count(marker) != 1:
        raise RuntimeError(f'Nonunique formatting marker {rel}: {source.count(marker)}')
    pos = source.index(marker)
    previous = source.rfind('/**', 0, pos)
    end = source.find('*/', previous)
    if previous < 0 or end < 0 or end >= pos:
        raise RuntimeError(f'Expected previous orphaned KDoc in {rel}')
    gap = source[end + 2:pos]
    if gap.strip() and not gap.strip().startswith('//'):
        raise RuntimeError(f'Unexpected source between comments in {rel}')
    source = source[:previous] + '/*' + source[previous + 3:]
    path.write_text(source, encoding='utf-8')
    replacements += 1

path = ROOT / 'app/src/main/java/com/mcarplay/app/airplay/VirtualIap2Link.kt'
source = path.read_text(encoding='utf-8')
marker = '    // ---- 车机 HID 媒体键（0x6802）状态 ----\n    /** 按下/长按连发的边沿判定'
if source.count(marker) != 1:
    raise RuntimeError('Missing unique virtual iAP2 comment marker')
source = source.replace(marker, marker.replace('\n    /**', '\n\n    /**'))
path.write_text(source, encoding='utf-8')
replacements += 1
assert replacements == 13, replacements
print(f'Fixed {replacements} inherited no-consecutive-comments formatting issues')
