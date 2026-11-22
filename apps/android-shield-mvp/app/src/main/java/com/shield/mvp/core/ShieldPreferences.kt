package com.shield.mvp.core

import android.content.Context

/**
 * Persistent local settings store so family protection rules survive app restarts and reboots.
 */
object ShieldPreferences {
    private const val PREF_FILE = "shield_v2_prefs"
    private const val KEY_GUARDIAN_PHONE = "guardian_phone"
    private const val KEY_FAMILY_HINT = "family_hint"
    private const val KEY_BACKEND_URL = "backend_url"
    private const val KEY_DEVICE_TOKEN = "device_token"
    private const val KEY_VERIFIED_PHONES = "verified_phones"
    private const val KEY_RELATIVE_NAMES = "relative_names"

    fun loadIntoRuntime(context: Context) {
        val prefs = context.applicationContext.getSharedPreferences(PREF_FILE, Context.MODE_PRIVATE)
        val phone = prefs.getString(KEY_GUARDIAN_PHONE, "+84901234567").orEmpty()
        val hint = prefs.getString(KEY_FAMILY_HINT, "Tên thú cưng đầu tiên của nhà mình là gì?").orEmpty()
        val url = prefs.getString(KEY_BACKEND_URL, "http://127.0.0.1:8000").orEmpty()
        val token = prefs.getString(KEY_DEVICE_TOKEN, "").orEmpty()
        val verifiedPhones = prefs.getStringSet(KEY_VERIFIED_PHONES, setOf("0901234567")).orEmpty()
        val relativeNames = prefs.getStringSet(KEY_RELATIVE_NAMES, setOf("Con trai Minh", "Con gái Lan")).orEmpty()

        ShieldRuntime.guardianPhoneNumber = phone
        ShieldRuntime.familyPasswordHint = hint
        ShieldRuntime.backendBaseUrl = url
        ShieldRuntime.deviceToken = token
        ShieldRuntime.fusionEngine.setAllowlist(
            FamilyAllowlist(
                verifiedCallerIds = verifiedPhones,
                verifiedRelativeNames = relativeNames,
            ),
        )
    }

    fun saveSettings(
        context: Context,
        guardianPhone: String,
        familyHint: String,
        backendUrl: String,
        deviceToken: String,
    ) {
        val prefs = context.applicationContext.getSharedPreferences(PREF_FILE, Context.MODE_PRIVATE)
        prefs.edit()
            .putString(KEY_GUARDIAN_PHONE, guardianPhone.trim())
            .putString(KEY_FAMILY_HINT, familyHint.trim())
            .putString(KEY_BACKEND_URL, backendUrl.trim())
            .putString(KEY_DEVICE_TOKEN, deviceToken.trim())
            .apply()
    }
}
