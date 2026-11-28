from pathlib import Path

def replace_once(path: str, old: str, new: str) -> None:
    target = Path(path)
    source = target.read_text()
    old_count = source.count(old)
    new_count = source.count(new)
    if old_count == 1:
        target.write_text(source.replace(old, new, 1))
        print(f"{path}: normalized")
    elif old_count == 0 and new_count == 1:
        print(f"{path}: canonical formatting already present")
    else:
        raise SystemExit(
            f"{path}: expected exactly one old or canonical block; "
            f"old={old_count} canonical={new_count}"
        )

replace_once(
    "app/src/main/java/com/mcarplay/app/net/EndpointHosts.kt",
    """                        it in 'a'..'z' || it in 'A'..'Z' || it in '0'..'9' ||
                            it == '_' || it == '-' || it == '.'""",
    """                        it in 'a'..'z' ||
                            it in 'A'..'Z' ||
                            it in '0'..'9' ||
                            it == '_' ||
                            it == '-' ||
                            it == '.'""",
)

replace_once(
    "app/src/main/java/com/mcarplay/app/video/ProjectedDashboardRenderer.kt",
    """        if (next !== layout || nextSourceStatus != sourceStatus || pressed != pressTarget || focused != focusBounds ||
            animating()
        ) {""",
    """        if (next !== layout ||
            nextSourceStatus != sourceStatus ||
            pressed != pressTarget ||
            focused != focusBounds ||
            animating()
        ) {""",
)

replace_once(
    "app/src/main/java/com/mcarplay/app/diagnostics/ConnectionProgress.kt",
    """        snapshot.stage == ConnectionStage.BLUETOOTH && snapshot.status == "failed" &&
            snapshot.code == DiagnosticCode.BT_LINK_CLOSED && bluetoothWasEstablished(snapshot)""",
    """        snapshot.stage == ConnectionStage.BLUETOOTH &&
            snapshot.status == "failed" &&
            snapshot.code == DiagnosticCode.BT_LINK_CLOSED &&
            bluetoothWasEstablished(snapshot)""",
)

replace_once(
    "app/src/main/java/com/mcarplay/app/video/ProjectionRuntimePolicy.kt",
    """            writeNs >= 80_000_000L || queueMs >= 250 ||
                (renderRecent && lastRenderDurationNs >= 80_000_000L)""",
    """            writeNs >= 80_000_000L ||
                queueMs >= 250 ||
                (renderRecent && lastRenderDurationNs >= 80_000_000L)""",
)

replace_once(
    "app/src/main/java/com/mcarplay/app/video/ProjectionRuntimePolicy.kt",
    """                writeNs < 4_000_000L && queueMs < 60 && thermal < 2 &&
                    (!renderRecent || lastRenderDurationNs < renderBudget * 3 / 4)""",
    """                writeNs < 4_000_000L &&
                    queueMs < 60 &&
                    thermal < 2 &&
                    (!renderRecent || lastRenderDurationNs < renderBudget * 3 / 4)""",
)

replace_once(
    "app/src/main/java/com/mcarplay/app/MainActivity.kt",
    """            if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) !=
                PackageManager.PERMISSION_GRANTED && !prefs.getBoolean("r12_wifi_ssid_permission_asked", false)
            ) {""",
    """            if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) !=
                PackageManager.PERMISSION_GRANTED &&
                !prefs.getBoolean("r12_wifi_ssid_permission_asked", false)
            ) {""",
)

replace_once(
    "app/src/main/java/com/mcarplay/app/MainActivity.kt",
    """                if (!isFinishing && !isDestroyed && hero.parent === contentArea && hero.isShown &&
                    contentArea.height > 0 && hero.height >= contentArea.height
                ) {""",
    """                if (!isFinishing &&
                    !isDestroyed &&
                    hero.parent === contentArea &&
                    hero.isShown &&
                    contentArea.height > 0 &&
                    hero.height >= contentArea.height
                ) {""",
)

replace_once(
    "app/src/main/java/com/mcarplay/app/airplay/VirtualIap2Link.kt",
    """                if (!response.valid || response.value == null || certificate == null || receiverIdentification == null ||
                    challenge == null
                ) {""",
    """                if (!response.valid ||
                    response.value == null ||
                    certificate == null ||
                    receiverIdentification == null ||
                    challenge == null
                ) {""",
)
