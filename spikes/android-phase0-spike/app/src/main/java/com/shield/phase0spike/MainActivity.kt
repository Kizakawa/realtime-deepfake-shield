package com.shield.phase0spike

import android.Manifest
import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import androidx.activity.ComponentActivity
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import kotlinx.coroutines.delay
import org.json.JSONObject

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                Surface(modifier = Modifier.fillMaxSize()) {
                    Phase0SpikeScreen()
                }
            }
        }
    }
}

@Composable
private fun Phase0SpikeScreen() {
    val context = LocalContext.current
    var audioState by remember { mutableStateOf(AudioProbeSnapshot()) }
    var videoState by remember { mutableStateOf(VideoProbeSnapshot()) }
    var notifCount by remember { mutableStateOf(0) }
    var latestNotifSummary by remember { mutableStateOf("Chưa ghi nhận thông báo Zalo/Messenger") }
    var pointOfLossStatus by remember { mutableStateOf("Chưa bật UsageStats Probe") }
    var copyFeedback by remember { mutableStateOf("") }

    val pointOfLossProbe = remember {
        val mainExecutor = ContextCompat.getMainExecutor(context)
        PointOfLossProbe(context) { obs ->
            mainExecutor.execute {
                pointOfLossStatus = "${obs.category}: ${obs.detectedPackage} (${obs.detectionLatencyMs} ms)"
            }
        }
    }

    DisposableEffect(Unit) {
        onDispose { pointOfLossProbe.stop() }
    }

    LaunchedEffect(Unit) {
        while (true) {
            audioState = SpikeForegroundService.latestAudioSnapshot
            videoState = SpikeForegroundService.latestVideoSnapshot
            val obsList = ScamNotificationProbeService.recentObservations
            notifCount = obsList.size
            obsList.firstOrNull()?.let { latest ->
                latestNotifSummary =
                    "${latest.packageName} | title=${latest.hasTitle}(${latest.titleLength}) | " +
                    "preview=${latest.hasTextPreview}(${latest.textLength}) | keyword=${latest.containsSensitiveKeyword}"
            }
            delay(500L)
        }
    }

    val audioPermLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted ->
        if (granted) {
            val intent = Intent(context, SpikeForegroundService::class.java).apply {
                action = SpikeForegroundService.ACTION_START_AUDIO
            }
            context.startForegroundService(intent)
        }
    }

    val projectionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult(),
    ) { result ->
        if (result.resultCode == android.app.Activity.RESULT_OK && result.data != null) {
            val intent = Intent(context, SpikeForegroundService::class.java).apply {
                action = SpikeForegroundService.ACTION_START_SCREEN
                putExtra(SpikeForegroundService.EXTRA_RESULT_CODE, result.resultCode)
                putExtra(SpikeForegroundService.EXTRA_RESULT_DATA, result.data)
            }
            context.startForegroundService(intent)
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        Text(
            text = "Shield Phase 0 — Android Validation Spike",
            style = MaterialTheme.typography.titleLarge,
        )
        Text(
            text = "Thiết bị: ${Build.MANUFACTURER} ${Build.MODEL} (Android ${Build.VERSION.RELEASE} / SDK ${Build.VERSION.SDK_INT})",
            style = MaterialTheme.typography.bodyMedium,
        )

        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Probe 1: Concurrent Audio (VoIP/PSTN)", style = MaterialTheme.typography.titleMedium)
                Text("isClientSilenced: ${audioState.isClientSilenced}")
                Text("zeroSampleRatio: ${"%.2f".format(audioState.zeroSampleRatio * 100)}%")
                Text("rmsDb: ${"%.1f".format(audioState.rmsDb)} dBFS")
                Text("Verdict: ${audioState.statusVerdict}")
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = {
                        val granted = ContextCompat.checkSelfPermission(
                            context,
                            Manifest.permission.RECORD_AUDIO,
                        ) == PackageManager.PERMISSION_GRANTED
                        if (granted) {
                            context.startForegroundService(
                                Intent(context, SpikeForegroundService::class.java).apply {
                                    action = SpikeForegroundService.ACTION_START_AUDIO
                                },
                            )
                        } else {
                            audioPermLauncher.launch(Manifest.permission.RECORD_AUDIO)
                        }
                    }) { Text("Start Audio Probe") }
                    OutlinedButton(onClick = {
                        context.startService(
                            Intent(context, SpikeForegroundService::class.java).apply {
                                action = SpikeForegroundService.ACTION_STOP_ALL
                            },
                        )
                    }) { Text("Stop Probes") }
                }
            }
        }

        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Probe 2: MediaProjection Video (3 FPS)", style = MaterialTheme.typography.titleMedium)
                Text("FPS: ${"%.1f".format(videoState.measuredFps)} | BlackRatio: ${"%.2f".format(videoState.blackFrameRatio * 100)}%")
                Text("Laplacian Sharpness: ${"%.1f".format(videoState.laplacianSharpness)}")
                Text("Verdict: ${videoState.verdict}")
                Button(onClick = {
                    val pm = context.getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
                    projectionLauncher.launch(pm.createScreenCaptureIntent())
                }) { Text("Start Screen Probe") }
            }
        }

        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Probe 3: Layer 0 NotificationListener", style = MaterialTheme.typography.titleMedium)
                Text("Connected: ${ScamNotificationProbeService.listenerConnected} | Captured: $notifCount")
                Text(latestNotifSummary)
                OutlinedButton(onClick = {
                    context.startActivity(Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS))
                }) { Text("Cấp quyền Notification Access") }
            }
        }

        Card(modifier = Modifier.fillMaxWidth()) {
            Column(modifier = Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Probe 4: Point-of-Loss (Banking / AnyDesk)", style = MaterialTheme.typography.titleMedium)
                Text("UsageStats Permission: ${pointOfLossProbe.hasUsageStatsPermission()}")
                Text("Latest: $pointOfLossStatus")
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = {
                        context.startActivity(Intent(Settings.ACTION_USAGE_ACCESS_SETTINGS))
                    }) { Text("Cấp Usage Access") }
                    Button(onClick = {
                        pointOfLossProbe.start()
                        pointOfLossStatus = "Đang theo dõi (mở VCB/MoMo/AnyDesk để đo)..."
                    }) { Text("Start Usage Probe") }
                }
            }
        }

        Button(
            modifier = Modifier.fillMaxWidth(),
            onClick = {
                val json = JSONObject().apply {
                    put("device", "${Build.MANUFACTURER} ${Build.MODEL}")
                    put("android_release", Build.VERSION.RELEASE)
                    put("sdk_int", Build.VERSION.SDK_INT)
                    put("probe1_is_client_silenced", audioState.isClientSilenced)
                    put("probe1_zero_sample_ratio", audioState.zeroSampleRatio)
                    put("probe1_rms_db", audioState.rmsDb)
                    put("probe1_verdict", audioState.statusVerdict)
                    put("probe2_measured_fps", videoState.measuredFps)
                    put("probe2_black_frame_ratio", videoState.blackFrameRatio)
                    put("probe2_sharpness", videoState.laplacianSharpness)
                    put("probe2_verdict", videoState.verdict)
                    put("probe3_listener_connected", ScamNotificationProbeService.listenerConnected)
                    put("probe3_observed_count", notifCount)
                    put("probe4_usage_permission", pointOfLossProbe.hasUsageStatsPermission())
                    put("probe4_latest", pointOfLossStatus)
                }.toString(2)
                val clipboard = context.getSystemService(Context.CLIPBOARD_SERVICE) as ClipboardManager
                clipboard.setPrimaryClip(ClipData.newPlainText("Phase0MatrixReport", json))
                copyFeedback = "Đã sao chép JSON Report vào Clipboard!"
            },
        ) {
            Text("Copy JSON Matrix Report")
        }
        if (copyFeedback.isNotEmpty()) {
            Text(copyFeedback, color = MaterialTheme.colorScheme.primary)
        }
    }
}
