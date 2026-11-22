package com.shield.mvp.ui

import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.shield.mvp.core.DeviceTierManager
import com.shield.mvp.core.ShieldPreferences
import com.shield.mvp.core.ShieldRuntime
import com.shield.mvp.services.AntiTamperHeartbeatWorker
import com.shield.mvp.services.PointOfLossMonitorService
import com.shield.mvp.services.ShieldNotificationListenerService
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        ShieldRuntime.ensureInitialized(applicationContext)
        AntiTamperHeartbeatWorker.schedule(applicationContext)

        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    ShieldSetupAndTransparencyScreen()
                }
            }
        }
    }
}

@Composable
private fun ShieldSetupAndTransparencyScreen() {
    val context = LocalContext.current
    val deviceTier = remember { DeviceTierManager.detectTier(context) }

    var guardianPhone by remember { mutableStateOf(ShieldRuntime.guardianPhoneNumber) }
    var familyHint by remember { mutableStateOf(ShieldRuntime.familyPasswordHint) }
    var backendUrl by remember { mutableStateOf(ShieldRuntime.backendBaseUrl) }
    var deviceToken by remember { mutableStateOf(ShieldRuntime.deviceToken) }
    var statusMessage by remember { mutableStateOf("Lá chắn đang ở chế độ bảo vệ thụ động (Layer 0).") }

    val timeFmt = remember { SimpleDateFormat("HH:mm:ss", Locale.getDefault()) }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = "Lá Chắn Chống Lừa Đảo v2.0",
            fontSize = 24.sp,
            fontWeight = FontWeight.Bold,
        )
        Text("Hạng thiết bị: ${deviceTier.label}")
        Text(statusMessage, color = MaterialTheme.colorScheme.primary)

        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("1. Quyền Bảo vệ Tối Giản", fontWeight = FontWeight.Bold)
                Text("Notification Listener: ${if (ShieldNotificationListenerService.isConnected) "ĐÃ BẬT" else "CHƯA BẬT"}")
                Text("UsageStats (Point-of-Loss): ${if (PointOfLossMonitorService.hasUsageStatsPermission(context)) "ĐÃ BẬT" else "CHƯA BẬT"}")
                Text("Overlay Cảnh báo: ${if (Settings.canDrawOverlays(context)) "ĐÃ BẬT" else "DÙNG FULL-SCREEN NOTIFICATION"}")

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = {
                        context.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
                    }) { Text("Thông báo") }
                    OutlinedButton(onClick = {
                        context.startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
                    }) { Text("UsageStats") }
                    OutlinedButton(onClick = {
                        context.startActivity(
                            Intent(
                                Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                                Uri.parse("package:${context.packageName}"),
                            ),
                        )
                    }) { Text("Overlay") }
                }
            }
        }

        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("2. Cấu hình Gia đình & Xác thực Thiết bị (Lưu bền vững)", fontWeight = FontWeight.Bold)
                OutlinedTextField(
                    value = guardianPhone,
                    onValueChange = { guardianPhone = it },
                    label = { Text("SĐT Người giám hộ (đã lưu)") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = familyHint,
                    onValueChange = { familyHint = it },
                    label = { Text("Câu gợi ý Mật khẩu Gia đình") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = backendUrl,
                    onValueChange = { backendUrl = it },
                    label = { Text("Địa chỉ Backend SOS (HTTPS / 127.0.0.1)") },
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = deviceToken,
                    onValueChange = { deviceToken = it },
                    label = { Text("X-Device-Token (cấp khi đăng ký hồ sơ)") },
                    modifier = Modifier.fillMaxWidth(),
                )
                Button(
                    modifier = Modifier.fillMaxWidth(),
                    onClick = {
                        ShieldPreferences.saveSettings(
                            context = context,
                            guardianPhone = guardianPhone,
                            familyHint = familyHint,
                            backendUrl = backendUrl,
                            deviceToken = deviceToken,
                        )
                        ShieldPreferences.loadIntoRuntime(context)
                        statusMessage = "Đã lưu bền vững cấu hình vào bộ nhớ riêng tư."
                    },
                ) { Text("Lưu Cấu hình") }
            }
        }

        Button(
            modifier = Modifier.fillMaxWidth(),
            onClick = {
                val now = System.currentTimeMillis() / 1000.0
                ShieldRuntime.fusionEngine.processIncomingCall(
                    timestampSec = now,
                    callerId = "com.zing.zalo:unverified:Con trai Minh",
                    displayName = "Con trai Minh",
                    isShortGlitchyVideo = true,
                    isVerifiedChannelId = false,
                )
                ShieldRuntime.fusionEngine.processChatNotification(
                    timestampSec = now + 5.0,
                    senderId = "com.zing.zalo:unverified:Con trai Minh",
                    displayName = "Con trai Minh",
                    textPreview = "Sóng yếu quá mẹ chuyển gấp 20 triệu vào STK mới này",
                    isVerifiedChannelId = false,
                )
                val finalRes = ShieldRuntime.fusionEngine.processAppUsage(
                    timestampSec = now + 10.0,
                    packageName = "com.VCB",
                    isSideloadInstall = false,
                )
                ShieldRuntime.handleDecision(context, finalRes)
                statusMessage = "Đã kích hoạt mô phỏng T1 -> ${finalRes.state}"
            },
        ) {
            Text("Mô phỏng Kịch bản T1 (Gọi 5s + Chat + Mở VCB)")
        }

        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("3. Nhật ký Minh bạch (Transparency Log)", fontWeight = FontWeight.Bold)
                Text("Ghi nhận mọi cảnh báo từng gửi cho con cái (luôn ẩn nội dung hội thoại):")
                val logs = ShieldRuntime.transparencyLogs
                if (logs.isEmpty()) {
                    Text("Chưa có cảnh báo nào được gửi đi.")
                } else {
                    for (entry in logs) {
                        Text("[${timeFmt.format(Date(entry.timestampMs))}] ${entry.eventType}: ${entry.summaryVn}")
                    }
                }
            }
        }
    }
}
