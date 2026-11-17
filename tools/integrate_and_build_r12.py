#!/usr/bin/env python3
"""R12: safe auto-observation of connected car Wi-Fi without altering iAP2 security."""
from pathlib import Path
import hashlib, os, shutil, subprocess, sys, zipfile
import integrate_and_build_r10 as r10

def patch(base: Path, kit: Path) -> None:
    copy = r10.r9.r8.copy_new
    for name, dst in (
        ("R12WifiNetworkSelectionTest.kt", "app/src/test/java/com/mcarplay/app/net/R12WifiNetworkSelectionTest.kt"),
        ("R12WifiHandoffIsolationTest.kt", "app/src/test/java/com/mcarplay/app/iap2/R12WifiHandoffIsolationTest.kt"),
        ("PendingWifiCandidatePolicy.kt", "app/src/main/java/com/mcarplay/app/net/PendingWifiCandidatePolicy.kt"),
        ("PendingWifiCandidatePolicyTest.kt", "app/src/test/java/com/mcarplay/app/net/PendingWifiCandidatePolicyTest.kt"),
    ):
        copy(kit, base, name, dst)

    def change(path: str, old: str, new: str, label: str) -> None:
        p=base/path
        s=p.read_text(encoding="utf-8")
        p.write_text(r10.checked(s,old,new,"R12 "+label),encoding="utf-8")

    wifi="app/src/main/java/com/mcarplay/app/net/WifiCarPlayConnector.kt"
    change(wifi,
        "        return chooseWifiNetworkTarget(binding.current(), connectivityManager.activeNetwork, ::isWifi)\n",
        "        return chooseWifiNetworkTarget(\n"
        "            binding.current(), connectivityManager.activeNetwork,\n"
        "            runCatching { connectivityManager.allNetworks.toList() }.getOrDefault(emptyList()), ::isWifi,\n"
        "        )\n",
        "current Wi-Fi when cellular default")
    change(wifi,
        "        val target =\n"
        "            chooseWifiNetworkTarget(binding.current(), connectivityManager.activeNetwork, ::isWifi)\n"
        "                ?: return null\n",
        "        val target = currentWifiNetwork() ?: return null\n",
        "SSID uses identical network selection")
    old = (
        "        internal fun <T> chooseWifiNetworkTarget(\n"
        "            bound: T?,\n            active: T?,\n            isWifi: (T) -> Boolean,\n"
        "        ): T? = bound?.takeIf(isWifi) ?: active?.takeIf(isWifi)\n"
    )
    change(wifi,old,old+
        "\n"
        "        /** A no-internet car Wi-Fi may exist while cellular stays active.\n"
        "         * Never guess between multiple candidate Wi-Fi networks.\n"
        "         * Observing one is NOT authorization to bind it as a car.\n"
        "         */\n"
        "        internal fun <T> chooseWifiNetworkTarget(\n"
        "            bound: T?, active: T?, available: Collection<T>, isWifi: (T) -> Boolean,\n"
        "        ): T? = chooseWifiNetworkTarget(bound, active, isWifi) ?: available.filter(isWifi).distinct().singleOrNull()\n",
        "unambiguous observed network fallback")

    controller="app/src/main/java/com/mcarplay/app/SessionController.kt"
    change(controller,
        "import com.mcarplay.app.net.EndpointHosts\\n",
        "import com.mcarplay.app.net.EndpointHosts\\nimport com.mcarplay.app.net.PendingWifiCandidatePolicy\\n",
        "candidate prompt import")
    change(controller,
        "    private fun liveWifiSsid(): String? =\n",
        "    /** Read-only current WLAN name for UI; never grants pairing or network ownership. */\n"
        "    fun observedWifiSsid(): String? = liveWifiSsid()\n\n"
        "    private fun liveWifiSsid(): String? =\n",
        "expose passive UI observation")
    change(controller,
        "                if (ssid.isNullOrEmpty() && !hasRecentUnverifiedInvite()) continue\\n",
        "                // Unknown SSID is allowed to PROMPT (never auto-bind) only when\\n"
        "                // the user selected one car and there is exactly one Wi-Fi Network.\\n"
        "                if (!PendingWifiCandidatePolicy.mayPrompt(\\n"
        "                        readableSsid = !ssid.isNullOrEmpty(),\\n"
        "                        freshInvite = hasRecentUnverifiedInvite(),\\n"
        "                        selectedTarget = appContext?.let(TargetDevicePrefs::get) != null,\\n"
        "                        uniqueWifi = wifiConnector?.singleWifiNetwork() == network,\\n"
        "                    )) continue\\n",
        "unknown WLAN must require explicit consent")

    main="app/src/main/java/com/mcarplay/app/MainActivity.kt"
    change(main,"    private lateinit var ssidInput: EditText\n",
        "    private lateinit var ssidInput: EditText\n"
        "    private lateinit var wifiObservedDesc: TextView\n"
        "    private var lastWifiObservationMs = 0L\n"
        "    private val wifiObservationBusy = java.util.concurrent.atomic.AtomicBoolean(false)\n",
        "Wi-Fi observation UI fields")
    change(main,"        ssidInput = findViewById(R.id.ssidInput)\n",
        "        ssidInput = findViewById(R.id.ssidInput)\n"
        "        wifiObservedDesc = findViewById(R.id.wifiObservedDesc)\n",
        "bind Wi-Fi status text")
    change(main,
        "        SessionController.ssidSink = ssidSink\n",
        "        SessionController.ssidSink = ssidSink\n"
        "        if (SessionController.isSessionRunning() || SessionController.sessionStarting.get()) {\n"
        "            SessionController.lastCarWifiSsid?.let(ssidSink)\n"
        "        }\n",
        "backfill protocol-supplied SSID")
    change(main,
        "    private val ssidSink: (String) -> Unit = { ssid ->\n"
        "        runOnUiThread { ssidInput.setText(ssid) }\n"
        "    }\n",
        "    private val ssidSink: (String) -> Unit = { ssid ->\n"
        "        runOnUiThread {\n"
        "            if (!isFinishing && !isDestroyed) {\n"
        "                ssidInput.setText(ssid)\n"
        "                updateReadyRow()\n"
        "            }\n"
        "        }\n"
        "    }\n",
        "safe protocol SSID UI callback")
    change(main,
        "        updateReadyRow()\n        updateShizukuChip()\n        updateCarLifeSelfTestRow()\n",
        "        updateReadyRow()\n        refreshObservedWifiUi()\n"
        "        updateShizukuChip()\n        updateCarLifeSelfTestRow()\n",
        "schedule periodic read-only UI sync")
    change(main,
        "    /** 连接准备计数：CarWith/CarLife 组件 / 热点 SSID / 蓝牙配对 / 音频来源。 */\n",
        "    /** Current Wi-Fi is a candidate. Never substitute it for 0x5703/0x4301 credentials. */\n"
        "    private fun refreshObservedWifiUi() {\n"
        "        if (!::wifiObservedDesc.isInitialized) return\n"
        "        val now = SystemClock.uptimeMillis()\n"
        "        if (now - lastWifiObservationMs < 6_000L || !wifiObservationBusy.compareAndSet(false, true)) return\n"
        "        lastWifiObservationMs = now\n"
        "        Bg.run(\"wifi-ui-observer\") {\n"
        "            val live = runCatching { SessionController.observedWifiSsid() }.getOrNull()\n"
        "            runOnUiThread {\n"
        "                wifiObservationBusy.set(false)\n"
        "                if (isDestroyed || isFinishing) return@runOnUiThread\n"
        "                if (live.isNullOrBlank()) {\n"
        "                    val missing = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) !=\n"
        "                        PackageManager.PERMISSION_GRANTED\n"
        "                    wifiObservedDesc.visibility = if (missing) View.VISIBLE else View.GONE\n"
        "                    if (missing) wifiObservedDesc.setText(R.string.ma_r12_wifi_need_ssid_permission)\n"
        "                } else {\n"
        "                    val known = SessionController.lastCarWifiSsid\n"
        "                    wifiObservedDesc.visibility = View.VISIBLE\n"
        "                    wifiObservedDesc.text = getString(\n"
        "                        when {\n"
        "                            known.isNullOrBlank() -> R.string.ma_r12_wifi_observed_candidate\n"
        "                            known == live -> R.string.ma_r12_wifi_observed_match\n"
        "                            else -> R.string.ma_r12_wifi_observed_other\n"
        "                        }, live,\n"
        "                    )\n"
        "                }\n"
        "            }\n"
        "        }\n"
        "    }\n\n"
        "    /** 连接准备计数：CarWith/CarLife 组件 / 热点 SSID / 蓝牙配对 / 音频来源。 */\n",
        "nonblocking actual Wi-Fi UI status")
    change(main,
        "            onReady()\n            return\n        }\n        val granted =\n",
        "            val prefs = getSharedPreferences(\"settings\", Context.MODE_PRIVATE)\n"
        "            if (ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION) !=\n"
        "                PackageManager.PERMISSION_GRANTED && !prefs.getBoolean(\"r12_wifi_ssid_permission_asked\", false)\n"
        "            ) {\n"
        "                // Optional, once: on Android 13+ NEARBY_WIFI_DEVICES lets us join,\n"
        "                // but precise location is still needed to read the connected SSID.\n"
        "                prefs.edit().putBoolean(\"r12_wifi_ssid_permission_asked\", true).apply()\n"
        "                afterOptionalWifiPermission = onReady\n"
        "                optionalWifiPermission.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))\n"
        "                return\n"
        "            }\n"
        "            onReady()\n            return\n        }\n        val granted =\n",
        "one-time optional SSID read permission")
    change(main,
        "    /** 位置权限授权后自动继续启动连接（仅 Android 12/12L）。 */\n",
        "    private var afterOptionalWifiPermission: (() -> Unit)? = null\n"
        "    private val optionalWifiPermission =\n"
        "        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { result ->\n"
        "            val granted = result[Manifest.permission.ACCESS_FINE_LOCATION] == true\n"
        "            log(\"WIFI: 可选 SSID 读取权限 granted=\" + granted)\n"
        "            val next = afterOptionalWifiPermission\n"
        "            afterOptionalWifiPermission = null\n"
        "            next?.invoke() // Rejection is never an iAP2/CarPlay blocker.\n"
        "        }\n\n"
        "    /** 位置权限授权后自动继续启动连接（仅 Android 12/12L）。 */\n",
        "optional permission return path")

    change("app/src/main/res/layout/activity_main.xml",
        "                            android:textColorHint=\"@color/ui_text_disabled\"\n"
        "                            android:textSize=\"13.5sp\"\n"
        "                            android:textStyle=\"bold\" />\n                    </LinearLayout>\n",
        "                            android:textColorHint=\"@color/ui_text_disabled\"\n"
        "                            android:textSize=\"13.5sp\"\n"
        "                            android:textStyle=\"bold\" />\n"
        "                        <TextView\n"
        "                            android:id=\"@+id/wifiObservedDesc\"\n"
        "                            android:layout_width=\"match_parent\"\n"
        "                            android:layout_height=\"wrap_content\"\n"
        "                            android:layout_marginTop=\"2dp\"\n"
        "                            android:ellipsize=\"end\"\n"
        "                            android:maxLines=\"2\"\n"
        "                            android:textColor=\"@color/m3_on_var\"\n"
        "                            android:textSize=\"11sp\"\n"
        "                            android:visibility=\"gone\" />\n"
        "                    </LinearLayout>\n",
        "view for candidate not trusted hotspot")
    for lang in ("values", "values-en"):
        content = (
            '    <string name="ma_r12_wifi_need_ssid_permission">当前 WLAN 名称不可读取：授权精确定位后可自动显示（不影响蓝牙连接）</string>\n'
            '    <string name="ma_r12_wifi_observed_candidate">已连接 Wi-Fi：%1$s（待确认是否为车机热点）</string>\n'
            '    <string name="ma_r12_wifi_observed_match">已连接 Wi-Fi：%1$s（与车机下发的网络名称一致）</string>\n'
            '    <string name="ma_r12_wifi_observed_other">已连接 Wi-Fi：%1$s（与车机下发的网络名称不同）</string>\n'
            if lang=="values" else
            '    <string name="ma_r12_wifi_need_ssid_permission">Cannot read current WLAN name. Optional precise location enables SSID detection.</string>\n'
            '    <string name="ma_r12_wifi_observed_candidate">Connected Wi-Fi: %1$s (not yet verified as car hotspot)</string>\n'
            '    <string name="ma_r12_wifi_observed_match">Connected Wi-Fi: %1$s (matches car-provided SSID)</string>\n'
            '    <string name="ma_r12_wifi_observed_other">Connected Wi-Fi: %1$s (differs from car-provided SSID)</string>\n'
        )
        change(f"app/src/main/res/{lang}/strings_ma.xml","</resources>",content+"</resources>","strings "+lang)
    print("R12 safe single-WiFi detection + passive auto-sync UI + optional identity read",flush=True)

def main() -> None:
    kit=Path(__file__).resolve().parent.parent
    out=Path(os.environ.get("R12_OUTPUT","apk-output-r12")).resolve()
    stage=out.parent/(out.name+"-staging")
    if out.exists() or stage.exists(): raise r10.r9.r8.r7.Blocked("R12 output exists")
    orig=r10.improve_fps
    def with_r12(base: Path, patchkit: Path) -> None:
        orig(base,patchkit)
        patch(base,patchkit)
    r10.improve_fps=with_r12
    os.environ["R10_OUTPUT"]=str(stage)
    r10.main()
    apk=stage/"mcarplay-LaCrosse-R10-source60-debug.apk"
    if not apk.is_file() or not zipfile.is_zipfile(apk):
        raise r10.r9.r8.r7.Blocked("R12 APK not verified")
    out.mkdir(parents=True,exist_ok=False)
    dest=out/"mcarplay-LaCrosse-R12-auto-wifi-sync-debug.apk"
    shutil.copy2(apk,dest)
    sha=hashlib.sha256(dest.read_bytes()).hexdigest()
    (out/"SHA256SUMS.txt").write_text(sha+"  "+dest.name+"\n")
    (out/"SCOPE.txt").write_text(
        "R12 R5-R10 preserved: selected single connected WLAN visible even with cellular default. "
        "Current WLAN displayed separately from unreceived CarPlay credentials. "
        "Unknown WLAN cannot be automatically trusted/bound; existing confirmation/receiver-invite gate remains. "
        "No real Buick car compatibility guarantee.\n")
    shutil.rmtree(stage)
    print("R12 VERIFIED BUILD:",dest,sha,flush=True)

if __name__=="__main__":
    try: main()
    except (r10.r9.r8.r7.Blocked,subprocess.CalledProcessError,OSError,AssertionError,ValueError) as e:
        sys.exit("BLOCKED; NO VERIFIED R12 APK: "+str(e))
