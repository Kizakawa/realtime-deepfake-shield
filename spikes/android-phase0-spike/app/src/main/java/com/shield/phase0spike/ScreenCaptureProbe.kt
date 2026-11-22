package com.shield.phase0spike

import android.content.Context
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.os.Handler
import android.os.HandlerThread
import android.os.SystemClock
import kotlin.math.pow

data class VideoProbeSnapshot(
    val running: Boolean = false,
    val sampledFrames: Long = 0,
    val measuredFps: Double = 0.0,
    val blackFrameRatio: Double = 0.0,
    val laplacianSharpness: Double = 0.0,
    val verdict: String = "IDLE",
)

/**
 * Probe 2: Samples MediaProjection frames at ~3 FPS to test whether Zalo/Messenger
 * enforce FLAG_SECURE (black frames) and measure sharpness degradation.
 * Zero screenshots are written to storage.
 */
class ScreenCaptureProbe(
    context: Context,
    private val onSnapshot: (VideoProbeSnapshot) -> Unit,
) {
    private val densityDpi = context.resources.displayMetrics.densityDpi
    private var virtualDisplay: VirtualDisplay? = null
    private var imageReader: ImageReader? = null
    private var handlerThread: HandlerThread? = null
    private var mediaProjection: MediaProjection? = null

    private var lastSampledAtMs = 0L
    private var frameCount = 0L
    private var startTimeMs = 0L
    private var projectionCallback: MediaProjection.Callback? = null

    fun start(projection: MediaProjection, width: Int = 540, height: Int = 960) {
        stop()
        mediaProjection = projection
        startTimeMs = SystemClock.elapsedRealtime()
        frameCount = 0L

        val thread = HandlerThread("Phase0ScreenProbe").apply { start() }
        handlerThread = thread
        val handler = Handler(thread.looper)

        // Required on Android 14+ (API 34+) prior to createVirtualDisplay.
        val callback = object : MediaProjection.Callback() {
            override fun onStop() {
                stop()
            }
        }
        projectionCallback = callback
        projection.registerCallback(callback, handler)

        val reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
        imageReader = reader

        reader.setOnImageAvailableListener({ r ->
            val image = r.acquireLatestImage() ?: return@setOnImageAvailableListener
            try {
                val now = SystemClock.elapsedRealtime()
                // Throttle processing to ~3 FPS (333 ms) to preserve device thermal budget.
                if (now - lastSampledAtMs < 333L) {
                    return@setOnImageAvailableListener
                }
                lastSampledAtMs = now
                frameCount++

                val plane = image.planes[0]
                val buffer = plane.buffer
                val pixelStride = plane.pixelStride
                val rowStride = plane.rowStride

                // Subsample grid to measure luma black ratio and Laplacian variance in RAM.
                val step = 8
                val cols = width / step
                val rows = height / step
                val lumaGrid = DoubleArray(cols * rows)
                var blackPixels = 0

                for (gy in 0 until rows) {
                    val y = gy * step
                    for (gx in 0 until cols) {
                        val x = gx * step
                        val offset = y * rowStride + x * pixelStride
                        val rVal = buffer.get(offset).toInt() and 0xFF
                        val gVal = buffer.get(offset + 1).toInt() and 0xFF
                        val bVal = buffer.get(offset + 2).toInt() and 0xFF
                        val luma = 0.299 * rVal + 0.587 * gVal + 0.114 * bVal
                        if (luma < 5.0) blackPixels++
                        lumaGrid[gy * cols + gx] = luma
                    }
                }

                val blackRatio = blackPixels.toDouble() / maxOf(1, cols * rows)
                var lapSum = 0.0
                var lapSqSum = 0.0
                var lapCount = 0
                for (gy in 1 until rows - 1) {
                    for (gx in 1 until cols - 1) {
                        val c = lumaGrid[gy * cols + gx]
                        val up = lumaGrid[(gy - 1) * cols + gx]
                        val down = lumaGrid[(gy + 1) * cols + gx]
                        val left = lumaGrid[gy * cols + (gx - 1)]
                        val right = lumaGrid[gy * cols + (gx + 1)]
                        val lap = up + down + left + right - 4.0 * c
                        lapSum += lap
                        lapSqSum += lap * lap
                        lapCount++
                    }
                }
                val meanLap = lapSum / maxOf(1, lapCount)
                val lapVariance = (lapSqSum / maxOf(1, lapCount)) - meanLap.pow(2)
                val elapsedSec = maxOf(0.5, (now - startTimeMs) / 1000.0)
                val fps = frameCount / elapsedSec

                val verdict = when {
                    blackRatio > 0.92 -> "BLACK_SCREEN_OR_FLAG_SECURE (FAIL)"
                    lapVariance < 15.0 -> "HEAVILY_BLURRED_STREAM"
                    else -> "VISIBLE_VIDEO_CAPTURED (PASS)"
                }

                onSnapshot(
                    VideoProbeSnapshot(
                        running = true,
                        sampledFrames = frameCount,
                        measuredFps = fps,
                        blackFrameRatio = blackRatio,
                        laplacianSharpness = lapVariance,
                        verdict = verdict,
                    ),
                )
            } finally {
                image.close()
            }
        }, handler)

        virtualDisplay = projection.createVirtualDisplay(
            "ShieldPhase0ScreenProbe",
            width,
            height,
            densityDpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            reader.surface,
            null,
            handler,
        )
    }

    fun stop() {
        virtualDisplay?.release()
        virtualDisplay = null
        imageReader?.close()
        imageReader = null
        projectionCallback?.let { cb ->
            mediaProjection?.unregisterCallback(cb)
        }
        projectionCallback = null
        mediaProjection?.stop()
        mediaProjection = null
        handlerThread?.quitSafely()
        handlerThread = null
        onSnapshot(VideoProbeSnapshot(running = false, verdict = "STOPPED"))
    }
}
