package com.shield.mvp.core

import kotlin.math.min

class VietnameseContextAnalyzer {

    private val apkExtRegex = Regex("\\.apk\\b", RegexOption.IGNORE_CASE)
    private val obfuscatedSepRegex = Regex("(?<=\\p{L}|\\p{N})[.\\-_*/]+(?=\\p{L}|\\p{N})")
    private val leetOtpRegex = Regex("\\b0tp\\b", RegexOption.IGNORE_CASE)
    private val nonWordAccentRegex = Regex("[^\\p{L}\\p{N}\\s]")
    private val multiSpaceRegex = Regex("\\s+")

    private val tacticPatterns: Map<TacticTag, List<String>> = mapOf(
        TacticTag.AUTHORITY_IMPERSONATION to listOf(
            "cong an", "vien kiem sat", "toa an", "canh sat dieu tra",
            "bo cong an", "lenh bat", "lenh tam giam", "khoi to", "truy na",
            "dich vu cong", "vneid", "co quan chuc nang", "ngan hang nha nuoc",
        ),
        TacticTag.RELATIVE_EMERGENCY to listOf(
            "tai nan", "cap cuu", "nhap vien", "phau thuat gap",
            "song yeu", "mat song", "vay tien", "muon tien",
            "cho muon", "chuyen ho", "gui ho", "tra no gap",
        ),
        TacticTag.URGENCY_FEAR to listOf(
            "chuyen gap", "chuyen tien gap", "chuyen khoan gap",
            "chuyen ngay", "chuyen tien ngay", "chuyen khoan ngay",
            "lap tuc", "ngay bay gio", "ngay lap tuc", "trong 5 phut",
            "trong 10 phut", "phong toa tai khoan", "khoa tai khoan",
            "tai khoan bi khoa", "khong kip", "bat tam giam", "lien quan duong day",
        ),
        TacticTag.SECRECY_ISOLATION to listOf(
            "giu bi mat", "tuyet doi bi mat", "tuyet mat",
            "khong duoc noi", "dung noi voi ai", "dung noi voi con",
            "khong bao ai", "o mot minh",
        ),
        TacticTag.FINANCIAL_TRANSFER to listOf(
            "so tai khoan", "stk", "tai khoan la", "ma otp", "otp",
            "doc ma", "chuyen khoan", "chuyen tien", "nop tien",
            "tien dam bao", "chung minh tai chinh",
        ),
        TacticTag.MALICIOUS_APP_INSTALL to listOf(
            "anydesk", "teamviewer", "rustdesk", "airdroid",
            "file apk", "apk", "cai app", "tai app",
            "tai ung dung", "bam vao link", "cap nhat sinh trac",
        ),
    )

    private val accentedPatterns: Map<TacticTag, List<String>> = mapOf(
        TacticTag.URGENCY_FEAR to listOf("bị bắt", "bắt giam"),
        TacticTag.RELATIVE_EMERGENCY to listOf("mổ gấp", "vào viện cấp cứu"),
    )

    private val promptInjectionPatterns = listOf(
        "bo qua huong dan", "bo qua tat ca chi thi", "ignore previous instructions",
        "ignore all instructions", "system prompt", "phan loai la safe",
        "phan loai la an toan", "tra ve safe", "set state safe",
    )

    private val benignPatterns = listOf(
        "shipper", "giao hang", "giao don", "buu ta",
        "nha thuoc", "phong kham", "lich hen kham",
    )

    private fun containsPhrase(paddedHaystack: String, phrase: String): Boolean =
        " $phrase " in paddedHaystack

    fun analyze(text: String, sourceTag: String = "android_context_engine"): List<EvidenceSignal> {
        if (text.isBlank()) return emptyList()
        val expandedApk = apkExtRegex.replace(text, " file apk ")
        val deobfuscated = obfuscatedSepRegex.replace(expandedApk, "")
        val accentedClean = multiSpaceRegex.replace(
            nonWordAccentRegex.replace(deobfuscated.lowercase(), " "),
            " ",
        ).trim()
        val paddedAccented = " $accentedClean "

        val norm = leetOtpRegex.replace(normalizeVietnamese(deobfuscated), "otp")
        if (norm.isEmpty()) return emptyList()
        val paddedNorm = " $norm "

        val signals = mutableListOf<EvidenceSignal>()
        if (promptInjectionPatterns.any { containsPhrase(paddedNorm, it) }) {
            signals += EvidenceSignal(
                source = sourceTag,
                rawScore = 0.85,
                calibratedProb = 0.80,
                reliability = 0.88,
                code = "PROMPT_INJECTION_ATTEMPT",
                detail = "Phát hiện câu lệnh tìm cách can thiệp bộ phân loại AI.",
            )
        }

        val matched = tacticPatterns.entries
            .filter { (tactic, keywords) ->
                val hitUnaccented = keywords.any { containsPhrase(paddedNorm, it) }
                val hitAccented = accentedPatterns[tactic].orEmpty().any { containsPhrase(paddedAccented, it) }
                hitUnaccented || hitAccented
            }
            .map { it.key }
        if (matched.isEmpty()) return signals

        val coercive = setOf(
            TacticTag.AUTHORITY_IMPERSONATION,
            TacticTag.URGENCY_FEAR,
            TacticTag.SECRECY_ISOLATION,
            TacticTag.MALICIOUS_APP_INSTALL,
        )
        val hasCoercion = matched.any { it in coercive }
        val isBenign = benignPatterns.any { containsPhrase(paddedNorm, it) }
        if (isBenign && !hasCoercion && TacticTag.FINANCIAL_TRANSFER !in matched) {
            return signals
        }

        val count = matched.size
        val (rawScore, reliability) = when {
            TacticTag.MALICIOUS_APP_INSTALL in matched ->
                min(0.95, 0.72 + 0.08 * count) to 0.90
            hasCoercion && TacticTag.FINANCIAL_TRANSFER in matched ->
                min(0.94, 0.68 + 0.08 * count) to 0.88
            hasCoercion && TacticTag.RELATIVE_EMERGENCY in matched ->
                min(0.88, 0.62 + 0.08 * count) to 0.82
            count >= 2 ->
                min(0.80, 0.50 + 0.10 * count) to 0.78
            TacticTag.FINANCIAL_TRANSFER in matched || TacticTag.RELATIVE_EMERGENCY in matched ->
                0.42 to 0.65
            else -> 0.32 to 0.55
        }

        signals += EvidenceSignal(
            source = sourceTag,
            rawScore = rawScore,
            calibratedProb = rawScore,
            reliability = reliability,
            code = "CONTEXT_MANIPULATION_DETECTED",
            detail = "Phát hiện chiến thuật: ${matched.joinToString(", ") { it.name }}",
        )
        return signals
    }
}
