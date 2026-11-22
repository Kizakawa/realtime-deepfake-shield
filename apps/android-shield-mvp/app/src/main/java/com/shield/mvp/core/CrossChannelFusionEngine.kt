package com.shield.mvp.core

data class ProvisionalThresholds(
    val tauUncertain: Double = 0.35,
    val tauYellow: Double = 0.70,
    val tauRed: Double = 0.85,
    val sessionTtlSec: Double = 3600.0,
)

/**
 * Thread-safe (`@Synchronized`), per-counterparty v2.0 cross-channel fusion engine.
 */
class CrossChannelFusionEngine(
    private val gatekeeper: Layer0Gatekeeper = Layer0Gatekeeper(),
    private val contextAnalyzer: VietnameseContextAnalyzer = VietnameseContextAnalyzer(),
    var thresholds: ProvisionalThresholds = ProvisionalThresholds(),
    var elderlyProfileId: String = "usr_parent_001",
) {
    private val sessions = mutableMapOf<String, SuspicionSession>()
    private var sessionCounter = 0
    private var sosCounter = 0

    @get:Synchronized
    var currentState: SystemState = SystemState.IDLE_ALLOWLISTED
        private set

    @Synchronized
    fun setAllowlist(allowlist: FamilyAllowlist) {
        gatekeeper.allowlist = allowlist
    }

    @Synchronized
    fun hasActiveSession(): Boolean = sessions.isNotEmpty()

    @Synchronized
    fun getTopActiveSession(): SuspicionSession? {
        return sessions.values.maxWithOrNull(
            compareBy<SuspicionSession>({ it.state.ordinal }, { it.maxRiskProb }, { it.lastEventSec }),
        )
    }

    fun computeNoisyOr(signals: List<EvidenceSignal>): Double {
        if (signals.isEmpty()) return 0.0
        var survival = 1.0
        for (s in signals) {
            val p = s.calibratedProb.coerceIn(0.0, 1.0)
            val r = s.reliability.coerceIn(0.0, 1.0)
            survival *= (1.0 - r * p)
        }
        return (1.0 - survival).coerceIn(0.0, 1.0)
    }

    @Synchronized
    fun processIncomingCall(
        timestampSec: Double,
        callerId: String,
        displayName: String,
        isShortGlitchyVideo: Boolean = false,
        isVerifiedChannelId: Boolean = true,
    ): DecisionResult {
        expireIfNeeded(timestampSec)
        val gate = gatekeeper.evaluateCounterparty(callerId, displayName, isVerifiedChannelId)
        if (gate.status == "EMERGENCY_BYPASS" || gate.status == "ALLOWLISTED") {
            return DecisionResult(timestampSec, currentState, 0.0, emptyList())
        }
        val signals = gate.signals.toMutableList()
        if (isShortGlitchyVideo) {
            signals += EvidenceSignal(
                source = "layer0_call_behavior",
                rawScore = 0.65,
                calibratedProb = 0.60,
                reliability = 0.65,
                code = "SHORT_GLITCHY_VIDEO_CALL",
                detail = "Cuộc gọi video ngắn bất thường từ tài khoản chưa xác thực.",
            )
        }
        val key = counterpartyKey(callerId, displayName)
        return updateSession(key, timestampSec, displayName.ifBlank { callerId }, signals)
    }

    @Synchronized
    fun processChatNotification(
        timestampSec: Double,
        senderId: String,
        displayName: String,
        textPreview: String,
        isVerifiedChannelId: Boolean = false,
    ): DecisionResult {
        expireIfNeeded(timestampSec)
        val gate = gatekeeper.evaluateCounterparty(senderId, displayName, isVerifiedChannelId)
        if (gate.status == "EMERGENCY_BYPASS" || gate.status == "ALLOWLISTED") {
            return DecisionResult(timestampSec, currentState, 0.0, emptyList())
        }
        val chatSignals = contextAnalyzer.analyze(textPreview, "android_notification_chat")
        val key = counterpartyKey(senderId, displayName)
        val existing = sessions[key]
        if (existing != null && chatSignals.isEmpty()) {
            return DecisionResult(
                timestampSec = timestampSec,
                state = existing.state,
                calibratedRiskProb = existing.maxRiskProb,
                activeEvidence = existing.signals.values.toList(),
            )
        }
        val signals = gate.signals.toMutableList().apply { addAll(chatSignals) }
        return updateSession(key, timestampSec, displayName.ifBlank { senderId }, signals)
    }

    @Synchronized
    fun processAppUsage(
        timestampSec: Double,
        packageName: String,
        isSideloadInstall: Boolean = false,
    ): DecisionResult {
        expireIfNeeded(timestampSec)
        val isRemoteTool = packageName in Layer0Constants.REMOTE_ACCESS_PACKAGES
        val isBanking = packageName in Layer0Constants.VN_BANKING_PACKAGES
        val topSession = getTopActiveSession()

        // Remote-access tools always intercept; sideloaded APKs intercept when a session is active
        // (or elevate to YELLOW/RED without false-firing on normal OEM store updates).
        if (isRemoteTool || (isSideloadInstall && topSession != null)) {
            val code = if (isRemoteTool) "REMOTE_ACCESS_APP_DETECTED" else "UNKNOWN_APK_SIDELOADED"
            val sig = EvidenceSignal(
                source = "point_of_loss_guard",
                rawScore = 0.96,
                calibratedProb = 0.95,
                reliability = 0.96,
                code = code,
                detail = "Phát hiện cài/mở công cụ nguy hiểm: $packageName",
            )
            val key = findKeyForSession(topSession) ?: "__pol_guard__"
            return updateSession(
                key,
                timestampSec,
                topSession?.counterpartyName ?: "PointOfLossGuard",
                listOf(sig),
                pointOfLoss = true,
                eventType = "POINT_OF_LOSS_REMOTE_OR_APK",
            )
        }

        if (isBanking && topSession != null) {
            val sig = EvidenceSignal(
                source = "point_of_loss_guard",
                rawScore = 0.95,
                calibratedProb = 0.94,
                reliability = 0.95,
                code = "BANKING_APP_OPENED_DURING_SESSION",
                detail = "Mở app tài chính ($packageName) ngay trong phiên nghi vấn.",
            )
            val key = findKeyForSession(topSession) ?: "__pol_guard__"
            return updateSession(
                key,
                timestampSec,
                topSession.counterpartyName,
                listOf(sig),
                pointOfLoss = true,
                eventType = "POINT_OF_LOSS_BANKING_INTERCEPT",
            )
        }

        return DecisionResult(
            timestampSec = timestampSec,
            state = currentState,
            calibratedRiskProb = topSession?.maxRiskProb ?: 0.0,
            activeEvidence = topSession?.signals?.values?.toList().orEmpty(),
        )
    }

    @Synchronized
    fun clearSessionByUserConfirmation() {
        sessions.clear()
        currentState = SystemState.IDLE_ALLOWLISTED
    }

    private fun counterpartyKey(rawId: String, displayName: String): String {
        val norm = rawId.trim().lowercase()
        return if (norm.isNotEmpty()) norm else "name:${displayName.trim().lowercase()}"
    }

    private fun findKeyForSession(target: SuspicionSession?): String? {
        if (target == null) return null
        return sessions.entries.firstOrNull { it.value.sessionId == target.sessionId }?.key
    }

    private fun expireIfNeeded(nowSec: Double) {
        val iterator = sessions.entries.iterator()
        while (iterator.hasNext()) {
            if (iterator.next().value.isExpired(nowSec)) {
                iterator.remove()
            }
        }
        currentState = getTopActiveSession()?.state ?: SystemState.IDLE_ALLOWLISTED
    }

    private fun updateSession(
        sessionKey: String,
        timestampSec: Double,
        counterpartyName: String,
        newSignals: List<EvidenceSignal>,
        pointOfLoss: Boolean = false,
        eventType: String = "CROSS_CHANNEL_SCAM_ALERT",
    ): DecisionResult {
        val existingSession = sessions[sessionKey]
        if (newSignals.isEmpty() && existingSession == null) {
            currentState = getTopActiveSession()?.state ?: SystemState.IDLE_ALLOWLISTED
            return DecisionResult(timestampSec, SystemState.IDLE_ALLOWLISTED, 0.0, emptyList())
        }

        val session = existingSession ?: run {
            sessionCounter++
            SuspicionSession(
                sessionId = "sess_%04d".format(sessionCounter),
                startedAtSec = timestampSec,
                lastEventSec = timestampSec,
                ttlSec = thresholds.sessionTtlSec,
                counterpartyName = counterpartyName,
            ).also { sessions[sessionKey] = it }
        }
        session.lastEventSec = timestampSec

        for (sig in newSignals) {
            val prev = session.signals[sig.code]
            if (prev == null || sig.calibratedProb > prev.calibratedProb) {
                session.signals[sig.code] = sig
            }
        }

        val allSignals = session.signals.values.toList()
        val pRisk = computeNoisyOr(allSignals)
        session.maxRiskProb = maxOf(session.maxRiskProb, pRisk)

        val nextState = when {
            pRisk >= thresholds.tauRed || pointOfLoss -> SystemState.RED_INTERCEPT
            pRisk >= thresholds.tauYellow -> SystemState.YELLOW_VERIFY
            pRisk >= thresholds.tauUncertain -> SystemState.SUSPICION_SESSION
            else -> SystemState.MONITORING
        }
        session.state = nextState

        var prompt = ""
        var sos: LeastPrivilegeSosPayload? = null
        if (nextState == SystemState.YELLOW_VERIFY) {
            prompt = "Cẩn trọng: Hãy hỏi Mật khẩu Gia đình hoặc Tạm dừng — Gọi lại số đã lưu."
        } else if (nextState == SystemState.RED_INTERCEPT) {
            sosCounter++
            prompt = "KHOAN CHUYỂN TIỀN! Có dấu hiệu giả mạo. Bấm TẠM DỪNG — GỌI LẠI SỐ ĐÃ LƯU."
            sos = LeastPrivilegeSosPayload(
                alertId = "sos_${session.sessionId}_%04d_${(timestampSec * 1000).toLong()}".format(sosCounter),
                timestampSec = timestampSec,
                elderlyProfileId = elderlyProfileId,
                eventType = eventType,
                state = nextState,
                calibratedRiskProb = pRisk,
                activeSessionMinutes = (timestampSec - session.startedAtSec) / 60.0,
                evidenceCodes = session.signals.keys.sorted(),
                transcriptIncluded = false,
            )
        }

        if (nextState == SystemState.MONITORING) {
            sessions.remove(sessionKey)
        }
        currentState = getTopActiveSession()?.state ?: SystemState.IDLE_ALLOWLISTED

        return DecisionResult(
            timestampSec = timestampSec,
            state = nextState,
            calibratedRiskProb = pRisk,
            activeEvidence = allSignals,
            pointOfLossTriggered = pointOfLoss,
            outOfBandPrompt = prompt,
            sosPayload = sos,
        )
    }
}
