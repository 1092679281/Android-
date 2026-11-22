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

# This inherited JUnit assertion incorrectly expects the REMOTE build flavor to
# have system-wide WiFi power-save privileges. Keep the production gate strict;
# assert the policy matches the flavor instead of force-enabling remote.
policy_test=root/'app/src/test/java/com/mcarplay/app/service/WifiLowLatencyPolicyTest.kt'
source=policy_test.read_text(encoding='utf-8')
old='        assertTrue(WifiLowLatencyPolicy.supportsForce(BuildConfig.FLAVOR))'
new='        assertEquals(BuildConfig.FLAVOR == "standard", WifiLowLatencyPolicy.supportsForce(BuildConfig.FLAVOR))'
if source.count(old)!=1:
    raise RuntimeError(f'Expected one incorrect remote flavor test assertion, found {source.count(old)}')
source=source.replace(old,new,1)
old_import='import org.junit.Assert.assertFalse\n'
if source.count(old_import)!=1:
    raise RuntimeError('Missing WifiLowLatencyPolicyTest JUnit import')
source=source.replace(old_import,'import org.junit.Assert.assertEquals\n'+old_import,1)
policy_test.write_text(source,encoding='utf-8')
print('R20 regression fix: standard/remote WiFi privilege tests validate policy without weakening gate')
