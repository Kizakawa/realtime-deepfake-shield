package com.shield.mvp.services

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.shield.mvp.core.ShieldRuntime
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread

/**
 * Periodically and immediately reports service/permission health to Backend Anti-Tamper API.
 */
class AntiTamperHeartbeatWorker(
    appContext: Context,
    params: WorkerParameters,
) : CoroutineWorker(appContext, params) {

    companion object {
        private const val WORK_NAME = "shield_anti_tamper_heartbeat"

        fun schedule(context: Context) {
            val req = PeriodicWorkRequestBuilder<AntiTamperHeartbeatWorker>(15, TimeUnit.MINUTES)
                .build()
            WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                WORK_NAME,
                ExistingPeriodicWorkPolicy.KEEP,
                req,
            )
        }

        fun sendImmediateSignalAsync(
            context: Context,
            notificationOk: Boolean = ShieldNotificationListenerService.isConnected,
        ) {
            val appCtx = context.applicationContext
            thread(name = "ShieldImmediateTamper") {
                ShieldRuntime.ensureInitialized(appCtx)
                postHeartbeatSync(appCtx, notificationOk)
            }
        }

        internal fun postHeartbeatSync(
            context: Context,
            notificationOk: Boolean = ShieldNotificationListenerService.isConnected,
        ): Boolean {
            val payload = JSONObject().apply {
                put("elderly_profile_id", ShieldRuntime.fusionEngine.elderlyProfileId)
                put("timestamp_sec", System.currentTimeMillis() / 1000.0)
                put("service_running", true)
                put("notification_listener_ok", notificationOk)
                put("usage_stats_ok", PointOfLossMonitorService.hasUsageStatsPermission(context))
                put("active_suspicion_session", ShieldRuntime.fusionEngine.hasActiveSession())
            }.toString()

            return runCatching {
                val url = URL("${ShieldRuntime.backendBaseUrl.trimEnd('/')}/api/v1/heartbeat")
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    connectTimeout = 5000
                    readTimeout = 5000
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    if (ShieldRuntime.deviceToken.isNotBlank()) {
                        setRequestProperty("X-Device-Token", ShieldRuntime.deviceToken)
                    }
                }
                OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { it.write(payload) }
                val code = conn.responseCode
                conn.disconnect()
                code in 200..299
            }.getOrDefault(false)
        }
    }

    override suspend fun doWork(): Result {
        ShieldRuntime.ensureInitialized(applicationContext)
        val ok = postHeartbeatSync(applicationContext)
        return if (ok) Result.success() else Result.retry()
    }
}

/**
 * Restores persistent family settings and re-arms Anti-Tamper Heartbeat after device reboot.
 */
class BootCompletedReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action == Intent.ACTION_BOOT_COMPLETED) {
            ShieldRuntime.ensureInitialized(context)
            AntiTamperHeartbeatWorker.schedule(context)
        }
    }
}
