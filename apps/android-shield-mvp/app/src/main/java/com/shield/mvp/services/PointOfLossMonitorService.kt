package com.shield.mvp.services

import android.app.AppOpsManager
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.app.usage.UsageEvents
import android.app.usage.UsageStatsManager
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import android.os.IBinder
import android.os.Process
import androidx.core.app.NotificationCompat
import com.shield.mvp.core.Layer0Constants
import com.shield.mvp.core.ShieldRuntime
import kotlin.concurrent.thread

/**
 * Monitors foreground app launches ONLY while an active cross-channel suspicion session
 * exists, re-intercepting reliably if the user switches away and re-opens a banking app.
 */
class PointOfLossMonitorService : Service() {

    companion object {
        private const val CHANNEL_ID = "shield_point_of_loss_channel"
        private const val NOTIF_ID = 2001
        private const val REINTERCEPT_COOLDOWN_MS = 3000L

        @Volatile
        var isRunning: Boolean = false
            private set

        fun hasUsageStatsPermission(context: Context): Boolean {
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

        fun startIfSessionActive(context: Context) {
            if (!isRunning) {
                context.startForegroundService(Intent(context, PointOfLossMonitorService::class.java))
            }
        }
    }

    private var worker: Thread? = null
    private var lastObservedForegroundPkg: String = ""
    private var lastInterceptTimeMs: Long = 0L

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        ShieldRuntime.ensureInitialized(applicationContext)
        createChannel()
        val notif: Notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Lá chắn Đang Bảo vệ Giao dịch")
            .setContentText("Đang canh gác mở app Ngân hàng / AnyDesk trong phiên nghi vấn.")
            .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
            .setOngoing(true)
            .build()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIF_ID, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC)
        } else {
            startForeground(NOTIF_ID, notif)
        }

        if (!isRunning) {
            isRunning = true
            startPollingLoop()
        }
        return START_STICKY
    }

    private fun startPollingLoop() {
        val usageStats = getSystemService(Context.USAGE_STATS_SERVICE) as UsageStatsManager
        worker = thread(name = "PointOfLossPoll") {
            while (isRunning) {
                if (!ShieldRuntime.fusionEngine.hasActiveSession()) {
                    stopSelf()
                    break
                }
                if (hasUsageStatsPermission(applicationContext)) {
                    val now = System.currentTimeMillis()
                    val events = usageStats.queryEvents(now - 2000L, now)
                    val ev = UsageEvents.Event()
                    var latestPkg = ""
                    var latestTs = 0L
                    while (events.hasNextEvent()) {
                        events.getNextEvent(ev)
                        if (ev.eventType == UsageEvents.Event.ACTIVITY_RESUMED && ev.timeStamp >= latestTs) {
                            latestTs = ev.timeStamp
                            latestPkg = ev.packageName.orEmpty()
                        }
                    }
                    if (latestPkg.isNotEmpty() && latestPkg != lastObservedForegroundPkg) {
                        // Always update observed foreground app (including our own overlay),
                        // so switching back to VCB re-fires interception after cooldown.
                        lastObservedForegroundPkg = latestPkg
                        val sensitive = latestPkg in Layer0Constants.VN_BANKING_PACKAGES ||
                            latestPkg in Layer0Constants.REMOTE_ACCESS_PACKAGES
                        if (sensitive && (now - lastInterceptTimeMs) >= REINTERCEPT_COOLDOWN_MS) {
                            lastInterceptTimeMs = now
                            val res = ShieldRuntime.fusionEngine.processAppUsage(
                                timestampSec = now / 1000.0,
                                packageName = latestPkg,
                                isSideloadInstall = false,
                            )
                            ShieldRuntime.handleDecision(applicationContext, res)
                        }
                    }
                }
                Thread.sleep(400L)
            }
        }
    }

    private fun createChannel() {
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL_ID, "Point-of-Loss Guard", NotificationManager.IMPORTANCE_LOW),
        )
    }

    override fun onDestroy() {
        isRunning = false
        worker?.join(400)
        worker = null
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}

/**
 * Intercepts unknown sideloaded APK installations while ignoring routine updates
 * and trusted OEM app stores (Play Store, Samsung Galaxy Store, Xiaomi GetApps, Oppo/Vivo/Huawei).
 */
class PackageSideloadReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action != Intent.ACTION_PACKAGE_ADDED) return
        ShieldRuntime.ensureInitialized(context)
        val pkg = intent.data?.schemeSpecificPart.orEmpty()
        if (pkg.isBlank()) return

        val isRemoteTool = pkg in Layer0Constants.REMOTE_ACCESS_PACKAGES
        val isReplacingUpdate = intent.getBooleanExtra(Intent.EXTRA_REPLACING, false)
        if (isReplacingUpdate && !isRemoteTool) {
            return
        }

        val installer = runCatching {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                context.packageManager.getInstallSourceInfo(pkg).installingPackageName
            } else {
                @Suppress("DEPRECATION")
                context.packageManager.getInstallerPackageName(pkg)
            }
        }.getOrNull()

        val isUntrustedSideload = installer.isNullOrBlank() ||
            installer !in Layer0Constants.TRUSTED_INSTALLER_STORES
        if (isUntrustedSideload || isRemoteTool) {
            val res = ShieldRuntime.fusionEngine.processAppUsage(
                timestampSec = System.currentTimeMillis() / 1000.0,
                packageName = pkg,
                isSideloadInstall = isUntrustedSideload,
            )
            ShieldRuntime.handleDecision(context, res)
        }
    }
}
