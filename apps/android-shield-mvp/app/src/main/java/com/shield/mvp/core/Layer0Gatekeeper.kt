package com.shield.mvp.core

import java.text.Normalizer
import kotlin.math.max

object Layer0Constants {
    val EMERGENCY_NUMBERS = setOf("113", "114", "115")

    val VN_BANKING_PACKAGES = setOf(
        "com.VCB",
        "com.vnpay.bidv",
        "com.mbmobile",
        "vn.com.techcombank.bb.app",
        "com.vietinbank.ipay",
        "com.vnpay.Agribank3g",
        "mobile.acb.com.vn",
        "com.vnpay.vpbankonline",
        "com.mservice.momotransfer",
        "vn.com.vng.zalopay",
    )

    val REMOTE_ACCESS_PACKAGES = setOf(
        "com.anydesk.anydeskandroid",
        "com.teamviewer.teamviewer.market.mobile",
        "com.carriez.flutter_hbb",
        "com.sand.airdroid",
    )

    val TRUSTED_INSTALLER_STORES = setOf(
        "com.android.vending",
        "com.sec.android.app.samsungapps",
        "com.xiaomi.mipicks",
        "com.heytap.market",
        "com.oppo.market",
        "com.vivo.appstore",
        "com.huawei.appmarket",
    )
}

fun normalizeVietnamese(input: String): String {
    if (input.isBlank()) return ""
    val replaced = input.replace('đ', 'd').replace('Đ', 'D')
    val nfd = Normalizer.normalize(replaced, Normalizer.Form.NFD)
    val stripped = buildString {
        for (ch in nfd) {
            if (Character.getType(ch) != Character.NON_SPACING_MARK.toInt()) {
                val lower = ch.lowercaseChar()
                if (lower in 'a'..'z' || lower in '0'..'9' || lower.isWhitespace()) {
                    append(lower)
                } else {
                    append(' ')
                }
            }
        }
    }
    return stripped.trim().replace(Regex("\\s+"), " ")
}

fun isEmergencyNumber(callerId: String): Boolean {
    val digits = callerId.filter { it.isDigit() }
    return digits in Layer0Constants.EMERGENCY_NUMBERS
}

data class FamilyAllowlist(
    val verifiedCallerIds: Set<String> = emptySet(),
    val verifiedRelativeNames: Set<String> = emptySet(),
) {
    private val normalizedIds = verifiedCallerIds.map { it.trim().lowercase() }.filter { it.isNotEmpty() }.toSet()
    private val normalizedNames = verifiedRelativeNames.map { normalizeVietnamese(it) }.filter { it.isNotEmpty() }.toSet()

    fun isVerifiedId(callerId: String): Boolean {
        val norm = callerId.trim().lowercase()
        return norm.isNotEmpty() && norm in normalizedIds
    }

    fun findLookalikeRelative(displayName: String, threshold: Double = 0.82): String? {
        val normDisp = normalizeVietnamese(displayName)
        if (normDisp.isEmpty()) return null
        for (relName in normalizedNames) {
            if (normDisp == relName) return relName
            if (relName.length >= 6 && (relName in normDisp || normDisp in relName)) {
                return relName
            }
            if (diceSimilarity(normDisp, relName) >= threshold) {
                return relName
            }
        }
        return null
    }

    private fun diceSimilarity(a: String, b: String): Double {
        if (a == b) return 1.0
        if (a.length < 2 || b.length < 2) return 0.0
        val bigramsA = (0 until a.length - 1).map { a.substring(it, it + 2) }.toSet()
        val bigramsB = (0 until b.length - 1).map { b.substring(it, it + 2) }.toSet()
        val intersection = bigramsA.intersect(bigramsB).size
        return (2.0 * intersection) / max(1, bigramsA.size + bigramsB.size)
    }
}

data class GatekeeperDecision(
    val status: String, // EMERGENCY_BYPASS | ALLOWLISTED | INSPECT
    val signals: List<EvidenceSignal> = emptyList(),
)

/**
 * Layer 0 gatekeeper hardened against OTT display-name spoofing:
 * `isVerifiedChannelId` must ONLY be true when `callerId` comes from an authentic
 * channel identifier (e.g., PSTN number or OS-verified conversation shortcut ID),
 * NEVER when derived solely from `Notification.EXTRA_TITLE`.
 */
class Layer0Gatekeeper(var allowlist: FamilyAllowlist = FamilyAllowlist()) {
    fun evaluateCounterparty(
        callerId: String,
        displayName: String,
        isVerifiedChannelId: Boolean = true,
    ): GatekeeperDecision {
        if (isEmergencyNumber(callerId)) {
            return GatekeeperDecision(status = "EMERGENCY_BYPASS")
        }
        if (isVerifiedChannelId && allowlist.isVerifiedId(callerId)) {
            return GatekeeperDecision(status = "ALLOWLISTED")
        }

        val signals = mutableListOf<EvidenceSignal>()
        val matchedName = allowlist.findLookalikeRelative(displayName)
        if (matchedName != null) {
            if (isVerifiedChannelId) {
                signals += EvidenceSignal(
                    source = "layer0_gatekeeper",
                    rawScore = 0.75,
                    calibratedProb = 0.68,
                    reliability = 0.72,
                    code = "LOOKALIKE_RELATIVE_NAME",
                    detail = "Số/ID lạ mạo danh tên người thân '$matchedName'.",
                )
            } else {
                // Display-name-only OTT notification: do not auto-allowlist (blocks spoofing),
                // and keep baseline signal moderate until combined with short-call or money tactics.
                signals += EvidenceSignal(
                    source = "layer0_gatekeeper",
                    rawScore = 0.40,
                    calibratedProb = 0.36,
                    reliability = 0.55,
                    code = "OTT_UNVERIFIED_RELATIVE_NAME",
                    detail = "Thông báo OTT trùng tên '$matchedName' nhưng chưa xác thực khóa tài khoản.",
                )
            }
        }

        val cid = callerId.trim().lowercase()
        val isForeignOrAnon = (cid.startsWith("+") && !cid.startsWith("+84")) ||
            cid.startsWith("unknown") || cid.startsWith("zalo_new_") || cid.startsWith("fb_new_")
        if (isForeignOrAnon) {
            signals += EvidenceSignal(
                source = "layer0_gatekeeper",
                rawScore = 0.35,
                calibratedProb = 0.30,
                reliability = 0.45,
                code = "FOREIGN_OR_UNKNOWN_CALLER",
                detail = "Số/tài khoản chưa lưu trong danh bạ gia đình.",
            )
        }
        return GatekeeperDecision(status = "INSPECT", signals = signals)
    }
}
