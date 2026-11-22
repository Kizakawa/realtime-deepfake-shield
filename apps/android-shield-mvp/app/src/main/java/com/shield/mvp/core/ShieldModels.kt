package com.shield.mvp.core

enum class SystemState {
    IDLE_ALLOWLISTED,
    MONITORING,
    SUSPICION_SESSION,
    YELLOW_VERIFY,
    RED_INTERCEPT,
}

enum class TacticTag {
    AUTHORITY_IMPERSONATION,
    RELATIVE_EMERGENCY,
    URGENCY_FEAR,
    SECRECY_ISOLATION,
    FINANCIAL_TRANSFER,
    MALICIOUS_APP_INSTALL,
}

enum class ChannelType {
    ZALO_VIDEO,
    ZALO_VOICE,
    ZALO_CHAT,
    MESSENGER_VIDEO,
    MESSENGER_CHAT,
    PSTN_CALL,
    SMS,
    APP_LAUNCH,
}

data class EvidenceSignal(
    val source: String,
    val rawScore: Double,
    val calibratedProb: Double,
    val reliability: Double,
    val code: String,
    val detail: String = "",
)

data class SuspicionSession(
    val sessionId: String,
    val startedAtSec: Double,
    var lastEventSec: Double,
    val ttlSec: Double,
    val counterpartyName: String,
    val signals: MutableMap<String, EvidenceSignal> = mutableMapOf(),
    var maxRiskProb: Double = 0.0,
    var state: SystemState = SystemState.SUSPICION_SESSION,
) {
    fun isExpired(currentTsSec: Double): Boolean = (currentTsSec - lastEventSec) > ttlSec
}

data class LeastPrivilegeSosPayload(
    val alertId: String,
    val schemaVersion: String = "2.0",
    val timestampSec: Double,
    val elderlyProfileId: String,
    val eventType: String,
    val state: SystemState,
    val calibratedRiskProb: Double,
    val activeSessionMinutes: Double,
    val evidenceCodes: List<String>,
    val transcriptIncluded: Boolean = false,
    val recommendedAction: String =
        "Gọi lại trực tiếp bằng số di động đã lưu để kiểm chứng với Cha/Mẹ ngay.",
)

data class DecisionResult(
    val timestampSec: Double,
    val state: SystemState,
    val calibratedRiskProb: Double,
    val activeEvidence: List<EvidenceSignal>,
    val pointOfLossTriggered: Boolean = false,
    val outOfBandPrompt: String = "",
    val sosPayload: LeastPrivilegeSosPayload? = null,
)

data class TransparencyLogEntry(
    val timestampMs: Long,
    val alertId: String,
    val eventType: String,
    val summaryVn: String,
    val guardianCount: Int,
)
