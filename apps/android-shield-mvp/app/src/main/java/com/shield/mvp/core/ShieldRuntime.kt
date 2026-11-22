package com.shield.mvp.core

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.provider.Settings
import androidx.core.app.NotificationCompat
import com.shield.mvp.services.PointOfLossMonitorService
import com.shield.mvp.services.SosDispatcher
import com.shield.mvp.ui.CoolingOffOverlayActivity
import java.util.concurrent.CopyOnWriteArrayList

/**
 * Thread-safe runtime coordinator backed by persistent preferences and FullScreenIntent fallback.
 */
object ShieldRuntime {
    private const val ALERT_CHANNEL_ID = "shield_red_intercept_high_channel"
    private const val ALERT_NOTIF_ID = 9001

    val fusionEngine = CrossChannelFusionEngine()
    val transparencyLogs = CopyOnWriteArrayList<TransparencyLogEntry>()

    @Volatile
    private var initialized: Boolean = false

    @Volatile
    var familyPasswordHint: String = "Tên thú cưng đầu tiên của nhà mình là gì?"

    @Volatile
    var guardianPhoneNumber: String = "+84901234567"

    @Volatile
    var backendBaseUrl: String = "http://127.0.0.1:8000"

    @Volatile
    var deviceToken: String = ""

    fun ensureInitialized(context: Context) {
        if (!initialized) {
            synchronized(this) {
                if (!initialized) {
                    ShieldPreferences.loadIntoRuntime(context)
                    initialized = true
                }
            }
        }
    }

    fun handleDecision(context: Context, result: DecisionResult) {
        val appCtx = context.applicationContext
        if (result.state == SystemState.SUSPICION_SESSION || result.state == SystemState.YELLOW_VERIFY) {
            PointOfLossMonitorService.startIfSessionActive(appCtx)
        }

        if (result.state == SystemState.RED_INTERCEPT) {
            result.sosPayload?.let { sos ->
                SosDispatcher.dispatchAsync(backendBaseUrl, deviceToken, sos) { delivered ->
                    val deliveryTag = if (delivered) {
                        "ĐÃ GỬI SERVER"
                    } else {
                        "MẤT MẠNG/CHƯA XÁC THỰC — DÙNG NÚT SMS NGOẠI TUYẾN"
                    }
                    transparencyLogs.add(
                        0,
                        TransparencyLogEntry(
                            timestampMs = System.currentTimeMillis(),
                            alertId = sos.alertId,
                            eventType = sos.eventType,
                            summaryVn = "[$deliveryTag] Mã dấu hiệu: ${sos.evidenceCodes.joinToString()} (không gửi nội dung chat).",
                            guardianCount = 1,
                        ),
                    )
                }
            }

            val overlayIntent = Intent(appCtx, CoolingOffOverlayActivity::class.java).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
                putExtra(CoolingOffOverlayActivity.EXTRA_PROMPT, result.outOfBandPrompt)
                putExtra(CoolingOffOverlayActivity.EXTRA_RISK_PCT, (result.calibratedRiskProb * 100).toInt())
                putExtra(CoolingOffOverlayActivity.EXTRA_PASSWORD_HINT, familyPasswordHint)
                putExtra(CoolingOffOverlayActivity.EXTRA_GUARDIAN_PHONE, guardianPhoneNumber)
                putExtra(
                    CoolingOffOverlayActivity.EXTRA_OFFLINE_SMS_BODY,
                    result.sosPayload?.let { SosDispatcher.buildOfflineSmsSummary(it) }.orEmpty(),
                )
            }

            // Always post FullScreenIntent notification so Android 10-15 Background Activity
            // Launch (BAL) restrictions cannot silently swallow the warning.
            postFullScreenInterceptNotification(appCtx, overlayIntent, result.outOfBandPrompt)

            if (Settings.canDrawOverlays(appCtx)) {
                runCatching { appCtx.startActivity(overlayIntent) }
            }
        }
    }

    private fun postFullScreenInterceptNotification(
        context: Context,
        overlayIntent: Intent,
        prompt: String,
    ) {
        val nm = context.getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(
            ALERT_CHANNEL_ID,
            "Cảnh Báo Chặn Lừa Đảo Khẩn Cấp",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            enableVibration(true)
        }
        nm.createNotificationChannel(channel)

        val piFlags = PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        val fullScreenPi = PendingIntent.getActivity(context, 0, overlayIntent, piFlags)

        val notif = NotificationCompat.Builder(context, ALERT_CHANNEL_ID)
            .setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle("CẢNH BÁO LỪA ĐẢO — TẠM DỪNG GIAO DỊCH")
            .setContentText(prompt)
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setAutoCancel(true)
            .setFullScreenIntent(fullScreenPi, true)
            .build()

        nm.notify(ALERT_NOTIF_ID, notif)
    }
}
