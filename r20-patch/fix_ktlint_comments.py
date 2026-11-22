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


# ktlint requires a blank separator between ordinary block and KDoc/EOL comments.
BLANK_BEFORE = {
    'app/src/main/java/com/mcarplay/app/SessionController.kt': '// 40s 总窗 =',
    'app/src/main/java/com/mcarplay/app/bt/Iap2BluetoothClient.kt': '/** 链路断开：同时携带 RFCOMM',
    'app/src/main/java/com/mcarplay/app/bt/Iap2BluetoothServer.kt': '/** 链路断开：同时携带 RFCOMM',
    'app/src/main/java/com/mcarplay/app/settings/DisplayPrefs.kt': '// 默认**关**',
    'app/src/main/java/com/mcarplay/app/shizuku/CarInputServiceImpl.kt': '// BlockedPrivateApi/DEPRECATION',
    'app/src/main/java/com/mcarplay/app/transport/Iap2LinkChannel.kt': '// 预算按字节计。',
}
for rel, marker in BLANK_BEFORE.items():
    path = ROOT / rel
    text = path.read_text(encoding='utf-8')
    if text.count(marker) != 1:
        raise RuntimeError(f'Nonunique comment separator marker: {rel}')
    pos = text.index(marker)
    line_start = text.rfind('\n', 0, pos)
    if line_start < 0 or text[line_start + 1:pos].strip():
        raise RuntimeError(f'Expected indented comment: {rel}')
    text = text[:line_start + 1] + '\n' + text[line_start + 1:]
    path.write_text(text, encoding='utf-8')

path = ROOT / 'app/src/main/java/com/mcarplay/app/airplay/AirPlayClient.kt'
text = path.read_text(encoding='utf-8')
marker = '// ---- 事件通道命令发送（对照 DiPlay sendCommandLocked）----'
if text.count(marker) != 1:
    raise RuntimeError('Missing unique AirPlay event-command marker')
pos = text.index(marker)
previous = text.rfind('/**', 0, pos)
end = text.find('*/', previous)
if previous < 0 or end < 0 or end >= pos:
    raise RuntimeError('Expected preceding AirPlay event-command KDoc')
text = text[:previous] + '/*' + text[previous + 3:]
path.write_text(text, encoding='utf-8')
print('Fixed 7 additional comment-adjacency warnings')


# Two more old KDocs became orphaned when methods were inserted below them.
FORGOTTEN_DOCS = {
    'app/src/main/java/com/mcarplay/app/SessionController.kt': '/** Read-only current WLAN name for UI;',
    'app/src/main/java/com/mcarplay/app/airplay/AirPlayClient.kt': '/** Activate strict SETUP/RECORD gating',
}
for rel, marker in FORGOTTEN_DOCS.items():
    path = ROOT / rel
    source = path.read_text(encoding='utf-8')
    if source.count(marker) != 1:
        raise RuntimeError(f'Nonunique trailing KDoc in {rel}')
    pos = source.index(marker)
    previous = source.rfind('/**', 0, pos)
    end = source.find('*/', previous)
    if previous < 0 or end < 0 or end >= pos:
        raise RuntimeError(f'Expected orphaned KDoc near {marker}')
    source = source[:previous] + '/*' + source[previous + 3:]
    path.write_text(source, encoding='utf-8')

# The old one-line callback description was replaced with a fuller KDoc.
# Drop the redundant description entirely rather than keeping two adjacent comments.
for rel in (
    'app/src/main/java/com/mcarplay/app/bt/Iap2BluetoothClient.kt',
    'app/src/main/java/com/mcarplay/app/bt/Iap2BluetoothServer.kt',
):
    path = ROOT / rel
    source = path.read_text(encoding='utf-8')
    marker = '/* 发送端链路断开（保活泵退出）时通知主控（释放僵尸轮次，见 SessionController.onSenderLinkClosed）。 */\n\n'
    if source.count(marker) != 1:
        raise RuntimeError(f'Expected exactly one duplicate callback comment in {rel}')
    source = source.replace(marker, '')
    path.write_text(source, encoding='utf-8')
print('Cleaned four additional orphaned/redundant KDocs')
