package com.shield.mvp.services

import android.content.Intent
import android.net.Uri
import com.shield.mvp.core.LeastPrivilegeSosPayload
import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import kotlin.concurrent.thread

/**
 * Dispatches authenticated Least-Privilege SOS payloads (code-only, no free-text fields)
 * and surfaces delivery outcomes so offline SMS fallback is never silently skipped.
 */
object SosDispatcher {

    fun toJson(payload: LeastPrivilegeSosPayload): String {
        val decision = JSONObject().apply {
            put("state", payload.state.name)
            put("calibrated_risk_prob", payload.calibratedRiskProb)
            put("active_session_minutes", payload.activeSessionMinutes)
        }
        return JSONObject().apply {
            put("alert_id", payload.alertId)
            put("schema_version", payload.schemaVersion)
            put("timestamp_sec", payload.timestampSec)
            put("elderly_profile_id", payload.elderlyProfileId)
            put("event_type", payload.eventType)
            put("decision", decision)
            put("evidence_codes", JSONArray(payload.evidenceCodes))
            put("transcript_included", false)
        }.toString()
    }

    fun dispatchAsync(
        backendBaseUrl: String,
        deviceToken: String,
        payload: LeastPrivilegeSosPayload,
        onDeliveryResult: (Boolean) -> Unit = {},
    ) {
        thread(name = "ShieldSosDispatch") {
            val delivered = runCatching {
                val url = URL("${backendBaseUrl.trimEnd('/')}/api/v1/sos/alert")
                val conn = (url.openConnection() as HttpURLConnection).apply {
                    requestMethod = "POST"
                    connectTimeout = 5000
                    readTimeout = 5000
                    doOutput = true
                    setRequestProperty("Content-Type", "application/json; charset=utf-8")
                    if (deviceToken.isNotBlank()) {
                        setRequestProperty("X-Device-Token", deviceToken)
                    }
                }
                OutputStreamWriter(conn.outputStream, Charsets.UTF_8).use { writer ->
                    writer.write(toJson(payload))
                }
                val code = conn.responseCode
                conn.disconnect()
                code in 200..299
            }.getOrDefault(false)
            onDeliveryResult(delivered)
        }
    }

    fun buildOfflineSmsSummary(payload: LeastPrivilegeSosPayload): String {
        val pct = (payload.calibratedRiskProb * 100).toInt()
        return "[LA CHAN SOS] Canh bao khan cap ${payload.eventType} ($pct%). " +
            "Vui long goi kiem chung cho Bo/Me NGAY!"
    }

    fun buildOfflineSmsIntent(guardianPhoneE164: String, smsBody: String): Intent {
        return Intent(Intent.ACTION_SENDTO).apply {
            data = Uri.parse("smsto:${Uri.encode(guardianPhoneE164)}")
            putExtra("sms_body", smsBody)
        }
    }
}
