package com.shield.phase0spike

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import java.util.concurrent.CopyOnWriteArrayList

data class NotificationProbeObservation(
    val timestampMs: Long,
    val packageName: String,
    val hasTitle: Boolean,
    val titleLength: Int,
    val hasTextPreview: Boolean,
    val textLength: Int,
    val containsSensitiveKeyword: Boolean,
)

/**
 * Probe 3: Verifies what call/chat metadata Layer 0 can read from Zalo & Messenger
 * notifications without AccessibilityService. Stores only anonymized telemetry in RAM.
 */
class ScamNotificationProbeService : NotificationListenerService() {

    companion object {
        val TARGET_PACKAGES = setOf(
            "com.zing.zalo",
            "com.facebook.orca",
            "com.whatsapp",
            "com.google.android.apps.messaging",
            "com.android.mms",
        )

        private val SENSITIVE_TOKENS = listOf(
            "chuyển tiền", "chuyen tien", "chuyển gấp", "chuyen gap",
            "số tài khoản", "stk", "mã otp", "otp", "công an", "cong an",
            "giữ bí mật", "giu bi mat", "sóng yếu", "song yeu", "anydesk", "apk",
        )

        val recentObservations = CopyOnWriteArrayList<NotificationProbeObservation>()

        @Volatile
        var listenerConnected: Boolean = false
    }

    override fun onListenerConnected() {
        super.onListenerConnected()
        listenerConnected = true
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        listenerConnected = false
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        if (sbn == null || sbn.packageName !in TARGET_PACKAGES) return
        val extras = sbn.notification?.extras ?: return

        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString().orEmpty()
        val combinedLower = "$title $text".lowercase()
        val keywordHit = SENSITIVE_TOKENS.any { combinedLower.contains(it) }

        val obs = NotificationProbeObservation(
            timestampMs = sbn.postTime,
            packageName = sbn.packageName,
            hasTitle = title.isNotBlank(),
            titleLength = title.length,
            hasTextPreview = text.isNotBlank(),
            textLength = text.length,
            containsSensitiveKeyword = keywordHit,
        )
        recentObservations.add(0, obs)
        while (recentObservations.size > 20) {
            recentObservations.removeAt(recentObservations.lastIndex)
        }
    }
}
