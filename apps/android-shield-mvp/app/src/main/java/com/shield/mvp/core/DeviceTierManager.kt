package com.shield.mvp.core

import android.app.ActivityManager
import android.content.Context

enum class DeviceTier(val label: String, val maxVideoFps: Int, val enableVideoForensics: Boolean) {
    TIER_1("TIER_1 (<=4GB RAM: Layer 0 + Chat + Point-of-Loss)", 0, false),
    TIER_2("TIER_2 (6GB RAM: + MediaProjection 2 FPS)", 2, true),
    TIER_3("TIER_3 (>=8GB RAM: + Video 3-5 FPS & Edge Models)", 4, true),
}

object DeviceTierManager {
    fun detectTier(context: Context): DeviceTier {
        val am = context.getSystemService(Context.ACTIVITY_SERVICE) as ActivityManager
        val memInfo = ActivityManager.MemoryInfo()
        am.getMemoryInfo(memInfo)
        val totalGb = memInfo.totalMem / (1024.0 * 1024.0 * 1024.0)
        return when {
            totalGb >= 7.2 -> DeviceTier.TIER_3
            totalGb >= 5.2 -> DeviceTier.TIER_2
            else -> DeviceTier.TIER_1
        }
    }
}
