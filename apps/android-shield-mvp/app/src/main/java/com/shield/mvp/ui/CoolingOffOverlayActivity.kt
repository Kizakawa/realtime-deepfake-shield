package com.shield.mvp.ui

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.shield.mvp.core.ShieldRuntime
import com.shield.mvp.services.SosDispatcher
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Panic-breaking 30-second Cooling-Off & Out-of-Band Verification screen.
 * Intentionally avoids "HANG UP NOW" to prevent dropping real 113/115 emergencies
 * and uses vibration + visuals instead of speaker TTS to avoid audio loops.
 */
class CoolingOffOverlayActivity : ComponentActivity() {

    companion object {
        const val EXTRA_PROMPT = "extra_prompt"
        const val EXTRA_RISK_PCT = "extra_risk_pct"
        const val EXTRA_PASSWORD_HINT = "extra_password_hint"
        const val EXTRA_GUARDIAN_PHONE = "extra_guardian_phone"
        const val EXTRA_OFFLINE_SMS_BODY = "extra_offline_sms_body"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        triggerAlertVibration()

        val prompt = intent.getStringExtra(EXTRA_PROMPT)
            ?: "KHOAN CHUYỂN TIỀN! Phát hiện dấu hiệu giả mạo."
        val riskPct = intent.getIntExtra(EXTRA_RISK_PCT, 90)
        val passwordHint = intent.getStringExtra(EXTRA_PASSWORD_HINT)
            ?: ShieldRuntime.familyPasswordHint
        val guardianPhone = intent.getStringExtra(EXTRA_GUARDIAN_PHONE)
            ?: ShieldRuntime.guardianPhoneNumber
        val smsBody = intent.getStringExtra(EXTRA_OFFLINE_SMS_BODY).orEmpty()

        setContent {
            MaterialTheme {
                CoolingOffScreen(
                    prompt = prompt,
                    riskPct = riskPct,
                    passwordHint = passwordHint,
                    guardianPhone = guardianPhone,
                    offlineSmsBody = smsBody,
                    onSafeDismiss = {
                        ShieldRuntime.fusionEngine.clearSessionByUserConfirmation()
                        finish()
                    },
                )
            }
        }
    }

    private fun triggerAlertVibration() {
        val effect = VibrationEffect.createWaveform(longArrayOf(0, 500, 200, 500, 200, 500), -1)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val vm = getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
            vm.defaultVibrator.vibrate(effect)
        } else {
            @Suppress("DEPRECATION")
            val v = getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
            v.vibrate(effect)
        }
    }
}

@Composable
private fun CoolingOffScreen(
    prompt: String,
    riskPct: Int,
    passwordHint: String,
    guardianPhone: String,
    offlineSmsBody: String,
    onSafeDismiss: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var remainingSec by remember { mutableIntStateOf(30) }
    var holdProgressText by remember { mutableStateOf("Nhấn giữ 3 giây nếu bác chắc chắn an toàn") }

    LaunchedEffect(Unit) {
        while (remainingSec > 0) {
            delay(1000L)
            remainingSec--
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(Color(0xFF8B0000))
            .padding(20.dp),
        verticalArrangement = Arrangement.SpaceBetween,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = "CẢNH BÁO AN TOÀN ($riskPct%)",
                color = Color.White,
                fontSize = 28.sp,
                fontWeight = FontWeight.ExtraBold,
                textAlign = TextAlign.Center,
            )
            Text(
                text = prompt,
                color = Color(0xFFFFE082),
                fontSize = 22.sp,
                fontWeight = FontWeight.Bold,
                textAlign = TextAlign.Center,
            )
            Text(
                text = if (remainingSec > 0) {
                    "Vui lòng dừng lại hít thở sâu: $remainingSec giây"
                } else {
                    "Đã hết 30s làm nguội — Hãy gọi kiểm chứng trước khi chuyển tiền"
                },
                color = Color.White,
                fontSize = 18.sp,
                textAlign = TextAlign.Center,
            )

            Card(
                modifier = Modifier.fillMaxWidth(),
                colors = CardDefaults.cardColors(containerColor = Color(0xFFFFF8E1)),
            ) {
                Column(modifier = Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(
                        text = "HỎI NGAY MẬT KHẨU GIA ĐÌNH:",
                        color = Color(0xFF8B0000),
                        fontSize = 18.sp,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        text = passwordHint,
                        color = Color.Black,
                        fontSize = 20.sp,
                        fontWeight = FontWeight.Medium,
                    )
                }
            }
        }

        Column(
            modifier = Modifier.fillMaxWidth(),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Button(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(68.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color.White),
                onClick = {
                    val dial = Intent(Intent.ACTION_DIAL, Uri.parse("tel:$guardianPhone"))
                    context.startActivity(dial)
                },
            ) {
                Text(
                    text = "TẠM DỪNG — GỌI LẠI SỐ ĐÃ LƯU",
                    color = Color(0xFF8B0000),
                    fontSize = 20.sp,
                    fontWeight = FontWeight.ExtraBold,
                    textAlign = TextAlign.Center,
                )
            }

            Button(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(68.dp),
                colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF1B5E20)),
                onClick = {
                    val dial = Intent(Intent.ACTION_DIAL, Uri.parse("tel:$guardianPhone"))
                    context.startActivity(dial)
                },
            ) {
                Text(
                    text = "GỌI NGƯỜI GIÁM HỘ HỖ TRỢ",
                    color = Color.White,
                    fontSize = 20.sp,
                    fontWeight = FontWeight.ExtraBold,
                    textAlign = TextAlign.Center,
                )
            }

            if (offlineSmsBody.isNotBlank()) {
                OutlinedButton(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = {
                        context.startActivity(
                            SosDispatcher.buildOfflineSmsIntent(guardianPhone, offlineSmsBody),
                        )
                    },
                ) {
                    Text(
                        text = "Mất mạng? Bấm 1 chạm để gửi SMS SOS cho con",
                        color = Color.White,
                        fontSize = 15.sp,
                    )
                }
            }

            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 6.dp)
                    .pointerInput(Unit) {
                        detectTapGestures(
                            onPress = {
                                val job = scope.launch {
                                    holdProgressText = "Đang giữ... (3 giây)"
                                    delay(3000L)
                                    onSafeDismiss()
                                }
                                tryAwaitRelease()
                                job.cancel()
                                holdProgressText = "Nhấn giữ 3 giây nếu bác chắc chắn an toàn"
                            },
                        )
                    },
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    text = holdProgressText,
                    color = Color(0xFFFFCDD2),
                    fontSize = 15.sp,
                    textAlign = TextAlign.Center,
                    modifier = Modifier.padding(10.dp),
                )
            }
        }
    }
}
