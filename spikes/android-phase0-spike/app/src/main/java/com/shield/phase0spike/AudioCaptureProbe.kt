package com.shield.phase0spike

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.AudioRecordingConfiguration
import android.media.MediaRecorder
import android.os.Build
import android.os.SystemClock
import androidx.core.content.ContextCompat
import kotlin.concurrent.thread
import kotlin.math.log10
import kotlin.math.sqrt

data class AudioProbeSnapshot(
    val running: Boolean = false,
    val isClientSilenced: Boolean = false,
    val zeroSampleRatio: Double = 0.0,
    val rmsDb: Double = -120.0,
    val totalFramesRead: Long = 0,
    val lastUpdatedMs: Long = 0L,
    val statusVerdict: String = "IDLE",
)

/**
 * Probe 1: Verifies Android 10+ Concurrent Audio Capture policy during active VoIP/PSTN calls.
 * Operates strictly in RAM (Zero raw audio retention).
 */
class AudioCaptureProbe(
    private val context: Context,
    private val onSnapshot: (AudioProbeSnapshot) -> Unit,
) {
    private val audioManager = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var audioRecord: AudioRecord? = null
    private var workerThread: Thread? = null

    @Volatile
    private var isRunning = false

    @Volatile
    private var clientSilenced = false

    private var recordingCallback: AudioManager.AudioRecordingCallback? = null

    @SuppressLint("MissingPermission")
    fun start() {
        if (isRunning) return
        val sampleRate = 16000
        val minBuf = AudioRecord.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
        )
        val bufferSize = maxOf(minBuf, sampleRate * 2) // ~1 second PCM16 buffer

        val recorder = AudioRecord(
            MediaRecorder.AudioSource.MIC,
            sampleRate,
            AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT,
            bufferSize,
        )
        if (recorder.state != AudioRecord.STATE_INITIALIZED) {
            onSnapshot(AudioProbeSnapshot(running = false, statusVerdict = "INIT_FAILED"))
            recorder.release()
            return
        }

        audioRecord = recorder
        val sessionId = recorder.audioSessionId

        val callback = object : AudioManager.AudioRecordingCallback() {
            override fun onRecordingConfigChanged(configs: MutableList<AudioRecordingConfiguration>) {
                val matching = configs.firstOrNull { it.clientAudioSessionId == sessionId }
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
                    clientSilenced = matching?.isClientSilenced ?: false
                }
            }
        }
        recordingCallback = callback
        audioManager.registerAudioRecordingCallback(ContextCompat.getMainExecutor(context), callback)

        isRunning = true
        recorder.startRecording()

        workerThread = thread(name = "Phase0AudioProbe") {
            val chunk = ShortArray(1600) // 100 ms chunks at 16 kHz
            var totalChunks = 0L
            while (isRunning) {
                val read = recorder.read(chunk, 0, chunk.size)
                if (read > 0) {
                    totalChunks++
                    var zeroCount = 0
                    var sumSq = 0.0
                    for (i in 0 until read) {
                        val s = chunk[i]
                        if (s.toInt() == 0) zeroCount++
                        val norm = s / 32768.0
                        sumSq += norm * norm
                    }
                    val zeroRatio = zeroCount.toDouble() / read.toDouble()
                    val rms = sqrt(sumSq / read.toDouble() + 1e-12)
                    val rmsDb = 20.0 * log10(maxOf(rms, 1e-6))

                    val verdict = when {
                        clientSilenced || zeroRatio >= 0.95 -> "SILENCED_BY_OS (FAIL FOR VOIP AUDIO)"
                        rmsDb > -55.0 -> "ACTIVE_AUDIO_RECEIVED (PASS)"
                        else -> "LOW_SIGNAL_OR_QUIET"
                    }

                    onSnapshot(
                        AudioProbeSnapshot(
                            running = true,
                            isClientSilenced = clientSilenced,
                            zeroSampleRatio = zeroRatio,
                            rmsDb = rmsDb,
                            totalFramesRead = totalChunks,
                            lastUpdatedMs = SystemClock.elapsedRealtime(),
                            statusVerdict = verdict,
                        ),
                    )
                }
            }
        }
    }

    fun stop() {
        isRunning = false
        workerThread?.join(500)
        workerThread = null
        recordingCallback?.let { audioManager.unregisterAudioRecordingCallback(it) }
        recordingCallback = null
        audioRecord?.run {
            runCatching { stop() }
            release()
        }
        audioRecord = null
        clientSilenced = false
        onSnapshot(AudioProbeSnapshot(running = false, statusVerdict = "STOPPED"))
    }
}
