package com.shield.phase0spike

import android.app.Activity
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat

/**
 * Android 14+ compliant Foreground Service hosting active Audio and MediaProjection probes.
 */
class SpikeForegroundService : Service() {

    companion object {
        const val ACTION_START_AUDIO = "com.shield.phase0spike.START_AUDIO"
        const val ACTION_START_SCREEN = "com.shield.phase0spike.START_SCREEN"
        const val ACTION_STOP_ALL = "com.shield.phase0spike.STOP_ALL"
        const val EXTRA_RESULT_CODE = "extra_result_code"
        const val EXTRA_RESULT_DATA = "extra_result_data"

        private const val CHANNEL_ID = "phase0_spike_channel"
        private const val NOTIF_ID = 1001

        @Volatile
        var latestAudioSnapshot = AudioProbeSnapshot()

        @Volatile
        var latestVideoSnapshot = VideoProbeSnapshot()
    }

    private lateinit var audioProbe: AudioCaptureProbe
    private lateinit var screenProbe: ScreenCaptureProbe

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        audioProbe = AudioCaptureProbe(this) { latestAudioSnapshot = it }
        screenProbe = ScreenCaptureProbe(this) { latestVideoSnapshot = it }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START_AUDIO -> {
                promoteForeground(ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
                audioProbe.start()
            }
            ACTION_START_SCREEN -> {
                promoteForeground(ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
                val code = intent.getIntExtra(EXTRA_RESULT_CODE, Activity.RESULT_CANCELED)
                @Suppress("DEPRECATION")
                val data = intent.getParcelableExtra<Intent>(EXTRA_RESULT_DATA)
                if (code == Activity.RESULT_OK && data != null) {
                    val pm = getSystemService(MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
                    val projection = pm.getMediaProjection(code, data)
                    screenProbe.start(projection)
                }
            }
            ACTION_STOP_ALL -> {
                audioProbe.stop()
                screenProbe.stop()
                stopForeground(STOP_FOREGROUND_REMOVE)
                stopSelf()
            }
        }
        return START_NOT_STICKY
    }

    private fun promoteForeground(fgsType: Int) {
        val notification: Notification = NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("Shield Phase 0 Validation Spike")
            .setContentText("Đang kiểm chứng Audio/Screen capture trong RAM (Zero Retention)")
            .setSmallIcon(android.R.drawable.ic_lock_idle_lock)
            .setOngoing(true)
            .build()

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIF_ID, notification, fgsType)
        } else {
            startForeground(NOTIF_ID, notification)
        }
    }

    private fun createNotificationChannel() {
        val manager = getSystemService(NotificationManager::class.java)
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Phase 0 Spike Monitor",
            NotificationManager.IMPORTANCE_LOW,
        )
        manager.createNotificationChannel(channel)
    }

    override fun onDestroy() {
        audioProbe.stop()
        screenProbe.stop()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
