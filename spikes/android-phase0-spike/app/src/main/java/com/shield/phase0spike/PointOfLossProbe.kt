package com.shield.phase0spike

import android.app.AppOpsManager
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.Context
import android.os.Build
import android.os.Process
import kotlin.concurrent.thread

data class PointOfLossObservation(
    val detectedPackage: String,
    val category: String,
    val detectionLatencyMs: Long,
)

/**
 * Probe 4: Polls UsageStatsManager to measure detection latency when the user opens
 * a Vietnamese banking/wallet app or remote-access tool (AnyDesk/TeamViewer/RustDesk).
 */
class PointOfLossProbe(
    private val context: Context,
    private val onObservation: (PointOfLossObservation) -> Unit,
) {
    companion object {
        val BANKING_PACKAGES = setOf(
            "com.VCB",
            "com.vnpay.bidv",
            "com.mbmobile",
            "vn.com.techcombank.bb.app",
            "com.vietinbank.ipay",
            "com.vnpay.Agribank3g",
            "mobile.acb.com.vn",
            "com.vnpay.vpbankonline",
            "com.mservice.momotransfer",
            "vn.com.vng.zalopay",
        )

        val REMOTE_ACCESS_PACKAGES = setOf(
            "com.anydesk.anydeskandroid",
            "com.teamviewer.teamviewer.market.mobile",
            "com.carriez.flutter_hbb",
            "com.sand.airdroid",
        )
    }

    private val usageStatsManager =
        context.getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager

    @Volatile
    private var running = false
    private var workerThread: Thread? = null
    private var lastReportedPkg = ""

    fun hasUsageStatsPermission(): Boolean {
        val appOps = context.getSystemService(Context.APP_OPS_SERVICE) as AppOpsManager
        val mode = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            appOps.unsafeCheckOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                Process.myUid(),
                context.packageName,
            )
        } else {
            @Suppress("DEPRECATION")
            appOps.checkOpNoThrow(
                AppOpsManager.OPSTR_GET_USAGE_STATS,
                Process.myUid(),
                context.packageName,
            )
        }
        return mode == AppOpsManager.MODE_ALLOWED
    }

    fun start() {
        if (running) return
        running = true
        lastReportedPkg = ""
        workerThread = thread(name = "Phase0UsageProbe") {
            while (running) {
                if (hasUsageStatsPermission()) {
                    val now = System.currentTimeMillis()
                    val events = usageStatsManager.queryEvents(now - 3000L, now)
                    val evt = UsageEvents.Event()
                    var latestPkg = ""
                    var latestTime = 0L
                    while (events.hasNextEvent()) {
                        events.getNextEvent(evt)
                        if (evt.eventType == UsageEvents.Event.ACTIVITY_RESUMED && evt.timeStamp >= latestTime) {
                            latestTime = evt.timeStamp
                            latestPkg = evt.packageName.orEmpty()
                        }
                    }
                    if (latestPkg.isNotEmpty() && latestPkg != lastReportedPkg) {
                        val category = when (latestPkg) {
                            in REMOTE_ACCESS_PACKAGES -> "REMOTE_ACCESS_TOOL"
                            in BANKING_PACKAGES -> "BANKING_OR_WALLET"
                            else -> ""
                        }
                        if (category.isNotEmpty()) {
                            lastReportedPkg = latestPkg
                            val latency = maxOf(0L, System.currentTimeMillis() - latestTime)
                            onObservation(PointOfLossObservation(latestPkg, category, latency))
                        }
                    }
                }
                Thread.sleep(300L)
            }
        }
    }

    fun stop() {
        running = false
        workerThread?.join(500)
        workerThread = null
    }
}
