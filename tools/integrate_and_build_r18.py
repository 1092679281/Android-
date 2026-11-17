#!/usr/bin/env python3
"""R18: use one Bluetooth identity for iAP2, ctrl and AirPlay SETUP."""
from pathlib import Path
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
import integrate_and_build_r16 as r16


class PatchMismatch(RuntimeError):
    pass


def patch(base: Path, kit: Path) -> None:
    copy = r16.r15.r14.r13.r12.r10.r9.r8.copy_new
    copy(kit, base, "BluetoothIdentitySessionPolicy.kt",
         "app/src/main/java/com/mcarplay/app/util/BluetoothIdentitySessionPolicy.kt")
    copy(kit, base, "BluetoothIdentitySessionPolicyTest.kt",
         "app/src/test/java/com/mcarplay/app/util/BluetoothIdentitySessionPolicyTest.kt")
    for name in ("r18-connection-identity.patch", "r18-identity-preflight.patch"):
        subprocess.run(
            ["git", "apply", "--whitespace=error", str(kit / "tools" / name)],
            cwd=base,
            check=True,
        )
    print("R18: gate vehicle startup on a shared Bluetooth identity", flush=True)


def main() -> None:
    output = Path(os.environ.get("R18_OUTPUT", "apk-output-r18")).resolve()
    stage = output.parent / (output.name + "-staging")
    if output.exists() or stage.exists():
        raise PatchMismatch("R18 output already exists")

    previous_patch = r16.patch

    def with_r18(base: Path, kit: Path) -> None:
        previous_patch(base, kit)
        patch(base, kit)

    r16.patch = with_r18
    os.environ["R16_OUTPUT"] = str(stage)
    r16.main()

    previous = stage / "mcarplay-LaCrosse-R16-buick-setup500-diagnostics-debug.apk"
    if not previous.is_file() or not zipfile.is_zipfile(previous):
        raise PatchMismatch("R18 Android test / APK build failed")
    output.mkdir(parents=True, exist_ok=False)
    target = output / "mcarplay-LaCrosse-R18-identity-snapshot-debug.apk"
    shutil.copy2(previous, target)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    (output / "SHA256SUMS.txt").write_text(f"{digest}  {target.name}\n", encoding="utf-8")
    (output / "SCOPE.txt").write_text(
        "R18 resolves the Bluetooth MAC before transport startup and uses one snapshot for "
        "iAP2, ctrl TXT and AirPlay SETUP. Vehicle startup requires a real Bluetooth address. "
        "Buick E2LB session acceptance requires vehicle testing. "
        "Debug APK uses a debug signing certificate.\n",
        encoding="utf-8",
    )
    shutil.rmtree(stage)
    print("R18 APK:", target, digest, flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        sys.exit("R18 BUILD BLOCKED: " + str(error))
