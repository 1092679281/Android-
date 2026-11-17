#!/usr/bin/env python3
"""R17: execute the actual Android app's JVM AirPlay receiver simulation suite.

This proves sender/loopback receiver protocol interactions, not an Apple-certified
wireless CarPlay receiver or GM E2LB firmware equivalence.
"""
from pathlib import Path
import hashlib
import os
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
import integrate_and_build_r16 as r16


class SimulationBlocked(RuntimeError):
    pass


def patch(base: Path, kit: Path) -> None:
    copy = r16.r15.r14.r13.r12.r10.r9.r8.copy_new
    copy(
        kit,
        base,
        "CarPlayReceiverSimulationTest.kt",
        "app/src/test/java/com/mcarplay/app/airplay/CarPlayReceiverSimulationTest.kt",
    )
    print("R17: installed actual loopback RTSP + H264/TCP receiver integration tests", flush=True)


def test_report(base: Path) -> tuple[list[str], int]:
    report = (
        base
        / "app/build/test-results/testStandardDebugUnitTest"
        / "TEST-com.mcarplay.app.airplay.CarPlayReceiverSimulationTest.xml"
    )
    if not report.is_file():
        raise SimulationBlocked("Required CarPlay receiver simulation JUnit XML report is missing")
    root = ET.parse(report).getroot()
    if root.tag != "testsuite":
        raise SimulationBlocked("Unexpected JUnit report structure")
    expected = {
        "endToEndCleartextRtspThroughTwoSetupsTcpRecordAndVideoFrames",
        "buickLikeSetup500MustStopBeforeScreenStreamAndRecord",
        "successStatusWithMalformedPlistIsNotSuccessfulSetup",
        "absentVideoTcpListenerMustBlockRecordDespiteTwoSuccessfulSetups",
        "independentReferenceReceiverValidatesSrpPairingAndEncryptedKeyDirections",
    }
    observed = {test.attrib.get("name", "") for test in root.findall("testcase")}
    if observed != expected:
        raise SimulationBlocked(f"Incomplete simulation coverage: expected {expected}, got {observed}")
    failed = int(root.attrib.get("failures", "0")) + int(root.attrib.get("errors", "0"))
    skipped = int(root.attrib.get("skipped", "0"))
    if failed != 0 or skipped != 0:
        raise SimulationBlocked(f"Simulation tests did not all pass: errors/failures={failed}, skipped={skipped}")
    return sorted(observed), int(root.attrib.get("tests", "0"))


def main() -> None:
    output = Path(os.environ.get("R17_OUTPUT", "apk-output-r17")).resolve()
    staging = output.parent / (output.name + "-staging")
    if output.exists() or staging.exists():
        raise SimulationBlocked("R17 output/staging already exists")

    old = r16.patch

    def extended_patch(base: Path, kit: Path) -> None:
        old(base, kit)
        patch(base, kit)

    r16.patch = extended_patch
    os.environ["R16_OUTPUT"] = str(staging)
    r16.main()

    base = Path(os.environ["R7_UPSTREAM"]).resolve()
    tests, total = test_report(base)
    previous = staging / "mcarplay-LaCrosse-R16-buick-setup500-diagnostics-debug.apk"
    if not previous.is_file() or not zipfile.is_zipfile(previous):
        raise SimulationBlocked("R17 staged APK absent or corrupt")
    output.mkdir(parents=True, exist_ok=False)
    target = output / "mcarplay-LaCrosse-R17-simulator-tested-debug.apk"
    shutil.copy2(previous, target)
    sha = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(f"{sha}  {target.name}\n", encoding="utf-8")
    report = [
        "# R17 AirPlay / CarPlay 接收端模拟联调结果",
        "",
        f"**自动联调：通过 {len(tests)}/{len(tests)} 项**（Gradle JUnit suite 总数：{total}）。",
        "",
        "| 测试用例 | 结果 |",
        "|---|---|",
    ]
    report.extend(f"| `{test}` | PASS |" for test in tests)
    report.extend(
        [
            "",
            "模拟的是 JVM 进程内的参考 SRP6a 配对接收端，以及",
            "127.0.0.1 TCP RTSP 接收端、屏幕数据 TCP 端口与 H.264 测试帧接收器。",
            "测试确实调用应用的 AirPlayClient、VideoSender 和 R14/R16 状态门控。",
            "",
            "**重要限制**：没有蓝牙 RFCOMM/iAP2 硬件、mDNS/真实热点、",
            "手机 CarWith 视频采集、Android MediaCodec 真机或 Buick E2LB 固件。",
            "模拟 200 是模拟服务端回复，不代表真实君越能够通过 SETUP/RECORD/出画。",
            "Pairing cryptographic reference test 与 RTSP cleartext test 分开；",
            "当前套件不声称已测试完整加密 RTSP 流或 MFi 芯片认证。",
            "",
            f"Debug APK SHA-256: `{sha}`",
            "",
        ],
    )
    (output / "SIMULATION-RESULTS.md").write_text("\n".join(report), encoding="utf-8")
    (output / "CARPLAY_SIMULATION_JUNIT.xml").write_bytes(
        (
            base
            / "app/build/test-results/testStandardDebugUnitTest"
            / "TEST-com.mcarplay.app.airplay.CarPlayReceiverSimulationTest.xml"
        ).read_bytes(),
    )
    shutil.rmtree(staging)
    print(f"R17 VERIFIED SIMULATION {len(tests)}/{len(tests)} PASS; APK {target}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        sys.exit("R17 SIMULATION / APK BUILD BLOCKED: " + str(error))
