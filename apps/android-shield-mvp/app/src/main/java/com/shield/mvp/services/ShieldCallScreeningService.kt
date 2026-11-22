package com.shield.mvp.services

import android.telecom.Call
import android.telecom.CallScreeningService
import com.shield.mvp.core.ShieldRuntime
import com.shield.mvp.core.isEmergencyNumber

/**
 * Layer 0 PSTN call gatekeeper. Never blocks calls (especially 113/114/115);
 * only updates the in-RAM cross-channel session when unverified callers arrive.
 */
class ShieldCallScreeningService : CallScreeningService() {

    override fun onScreenCall(callDetails: Call.Details) {
        ShieldRuntime.ensureInitialized(applicationContext)
        val number = callDetails.handle?.schemeSpecificPart.orEmpty()
        respondToCall(callDetails, CallResponse.Builder().build())

        if (isEmergencyNumber(number)) {
            return
        }

        val nowSec = System.currentTimeMillis() / 1000.0
        val displayName = callDetails.callerDisplayName.orEmpty().ifBlank { number }
        val result = ShieldRuntime.fusionEngine.processIncomingCall(
            timestampSec = nowSec,
            callerId = number,
            displayName = displayName,
            isShortGlitchyVideo = false,
            isVerifiedChannelId = true,
        )
        ShieldRuntime.handleDecision(applicationContext, result)
    }
}
