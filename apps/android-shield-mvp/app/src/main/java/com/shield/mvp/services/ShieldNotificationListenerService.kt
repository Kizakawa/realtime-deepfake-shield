package com.shield.mvp.services

import android.app.Notification
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import com.shield.mvp.core.ShieldRuntime

/**
 * Layer 0 OTT call/chat metadata observer hardened against EXTRA_TITLE spoofing
 * and reporting immediate anti-tamper signals if notification access is revoked.
 */
class ShieldNotificationListenerService : NotificationListenerService() {

    companion object {
        private val MONITORED_PACKAGES = setOf(
            "com.zing.zalo",
            "com.facebook.orca",
            "com.whatsapp",
            "com.google.android.apps.messaging",
            "com.android.mms",
        )

        @Volatile
        var isConnected: Boolean = false
            private set
    }

    override fun onListenerConnected() {
        super.onListenerConnected()
        isConnected = true
        ShieldRuntime.ensureInitialized(applicationContext)
    }

    override fun onListenerDisconnected() {
        super.onListenerDisconnected()
        isConnected = false
        // Fire immediate tamper signal (<2s) instead of waiting 15 minutes for WorkManager.
        AntiTamperHeartbeatWorker.sendImmediateSignalAsync(
            applicationContext,
            notificationOk = false,
        )
    }

    override fun onNotificationPosted(sbn: StatusBarNotification?) {
        if (sbn == null || sbn.packageName !in MONITORED_PACKAGES) return
        ShieldRuntime.ensureInitialized(applicationContext)
        val extras = sbn.notification?.extras ?: return

        val title = extras.getCharSequence(Notification.EXTRA_TITLE)?.toString().orEmpty()
        val text = extras.getCharSequence(Notification.EXTRA_TEXT)?.toString().orEmpty()
        if (title.isBlank() && text.isBlank()) return

        val tsSec = sbn.postTime / 1000.0
        val shortcutId = sbn.notification?.shortcutId.orEmpty()
        // Never treat attacker-controlled EXTRA_TITLE alone as a verified channel ID.
        val hasVerifiedShortcut = shortcutId.isNotBlank()
        val senderId = if (hasVerifiedShortcut) {
            "${sbn.packageName}:sc:$shortcutId"
        } else {
            "${sbn.packageName}:unverified:$title"
        }

        val result = if (text.contains("cuộc gọi", ignoreCase = true) ||
            text.contains("calling", ignoreCase = true) ||
            text.contains("video", ignoreCase = true)
        ) {
            ShieldRuntime.fusionEngine.processIncomingCall(
                timestampSec = tsSec,
                callerId = senderId,
                displayName = title,
                isShortGlitchyVideo = text.contains("nhỡ", ignoreCase = true),
                isVerifiedChannelId = hasVerifiedShortcut,
            )
        } else {
            ShieldRuntime.fusionEngine.processChatNotification(
                timestampSec = tsSec,
                senderId = senderId,
                displayName = title,
                textPreview = text,
                isVerifiedChannelId = hasVerifiedShortcut,
            )
        }
        ShieldRuntime.handleDecision(applicationContext, result)
    }
}
