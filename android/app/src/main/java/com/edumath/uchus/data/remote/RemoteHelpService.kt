package com.edumath.uchus.data.remote

import android.app.Activity
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.os.Looper
import android.os.SystemClock
import android.util.DisplayMetrics
import android.view.WindowManager
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import com.edumath.uchus.MainActivity
import com.edumath.uchus.R
import com.edumath.uchus.UchusApp
import com.edumath.uchus.data.api.RemoteCommandDto
import com.edumath.uchus.data.api.apiCall
import java.io.ByteArrayOutputStream
import java.util.concurrent.atomic.AtomicBoolean
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Показывает экран ребёнка родителю и выполняет его нажатия.
 *
 * Запускается только после того, как ребёнок нажал «Разрешить» и подтвердил
 * системное окно показа экрана. Всё время работы видно уведомление с кнопкой
 * «Остановить». Кадры уходят на сервер сжатыми (JPEG), не чаще двух в секунду.
 */
class RemoteHelpService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val uploading = AtomicBoolean(false)

    private var sessionId = 0
    private var projection: MediaProjection? = null
    private var virtualDisplay: VirtualDisplay? = null
    private var reader: ImageReader? = null
    private var captureThread: HandlerThread? = null
    private var captureHandler: Handler? = null
    private var commandJob: Job? = null
    private var controlReady = false
    private var lastFrameAt = 0L
    private var lastNotificationControl: Boolean? = null

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        val command = intent ?: run {
            stopSelf()
            return START_NOT_STICKY
        }
        val id = command.getIntExtra(EXTRA_SESSION_ID, 0)
        if (id <= 0) {
            stopSelf()
            return START_NOT_STICKY
        }
        sessionId = id

        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION
        } else {
            0
        }
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            buildNotification(false),
            type,
        )

        val resultCode = command.getIntExtra(EXTRA_RESULT_CODE, Activity.RESULT_CANCELED)
        val resultData = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            command.getParcelableExtra(EXTRA_RESULT_DATA, Intent::class.java)
        } else {
            @Suppress("DEPRECATION")
            command.getParcelableExtra(EXTRA_RESULT_DATA)
        }
        if (resultCode != Activity.RESULT_OK || resultData == null) {
            stopSelf()
            return START_NOT_STICKY
        }

        running = true
        startCapture(resultCode, resultData)
        startCommandLoop()
        return START_NOT_STICKY
    }

    // ------------------------------------------------------------- захват
    private fun startCapture(resultCode: Int, resultData: Intent) {
        val manager = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        val mediaProjection = runCatching {
            manager.getMediaProjection(resultCode, resultData)
        }.getOrNull() ?: run {
            stopSelf()
            return
        }
        projection = mediaProjection

        val metrics = screenMetrics()
        val targetWidth = 720.coerceAtMost(metrics.widthPixels)
        val targetHeight = (metrics.heightPixels.toLong() * targetWidth / metrics.widthPixels)
            .toInt()
            .coerceAtLeast(1)
            .let { if (it % 2 == 0) it else it + 1 }

        captureThread = HandlerThread("remote-help-capture").also { it.start() }
        val handler = Handler(captureThread!!.looper)
        captureHandler = handler

        mediaProjection.registerCallback(
            object : MediaProjection.Callback() {
                override fun onStop() {
                    stopSelf()
                }
            },
            Handler(Looper.getMainLooper()),
        )

        val imageReader = ImageReader.newInstance(
            targetWidth,
            targetHeight,
            PixelFormat.RGBA_8888,
            2,
        )
        reader = imageReader

        virtualDisplay = mediaProjection.createVirtualDisplay(
            "uchus-remote-help",
            targetWidth,
            targetHeight,
            metrics.densityDpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            imageReader.surface,
            null,
            handler,
        )

        imageReader.setOnImageAvailableListener({ source ->
            val image = source.acquireLatestImage() ?: return@setOnImageAvailableListener
            val now = SystemClock.elapsedRealtime()
            if (now - lastFrameAt < FRAME_INTERVAL_MS || !uploading.compareAndSet(false, true)) {
                image.close()
                return@setOnImageAvailableListener
            }
            lastFrameAt = now
            try {
                val bitmap = image.toBitmap(targetWidth, targetHeight)
                if (bitmap == null) {
                    uploading.set(false)
                    return@setOnImageAvailableListener
                }
                val bytes = ByteArrayOutputStream(64 * 1024).use { output ->
                    bitmap.compress(Bitmap.CompressFormat.JPEG, JPEG_QUALITY, output)
                    output.toByteArray()
                }
                bitmap.recycle()
                if (bytes.isEmpty()) {
                    uploading.set(false)
                    return@setOnImageAvailableListener
                }
                upload(targetWidth, targetHeight, bytes)
            } catch (_: Throwable) {
                uploading.set(false)
            } finally {
                image.close()
            }
        }, handler)
    }

    private fun upload(width: Int, height: Int, bytes: ByteArray) {
        val container = (application as? UchusApp)?.container
        if (container == null) {
            uploading.set(false)
            stopSelf()
            return
        }
        scope.launch {
            try {
                apiCall {
                    container.api.uploadRemoteFrame(
                        sessionId = sessionId,
                        width = width,
                        height = height,
                        body = bytes.toRequestBody("image/jpeg".toMediaType()),
                    )
                }
            } catch (_: Throwable) {
                // Сеть пропала — попробуем со следующим кадром.
            } finally {
                uploading.set(false)
            }
        }
    }

    private fun android.media.Image.toBitmap(width: Int, height: Int): Bitmap? {
        val plane = planes.firstOrNull() ?: return null
        val pixelStride = plane.pixelStride
        val rowStride = plane.rowStride
        val rowPadding = rowStride - pixelStride * width
        if (pixelStride <= 0 || rowPadding < 0) return null
        val paddedWidth = width + rowPadding / pixelStride
        val padded = Bitmap.createBitmap(paddedWidth, height, Bitmap.Config.ARGB_8888)
        padded.copyPixelsFromBuffer(plane.buffer)
        if (paddedWidth == width) {
            return padded
        }
        val cropped = Bitmap.createBitmap(padded, 0, 0, width, height)
        padded.recycle()
        return cropped
    }

    // ------------------------------------------------------------- команды
    private fun startCommandLoop() {
        commandJob?.cancel()
        commandJob = scope.launch {
            val container = (application as? UchusApp)?.container ?: run {
                stopSelf()
                return@launch
            }
            var afterId = 0
            var lastHeartbeat = 0L
            while (isActive) {
                controlReady = RemoteControlAccessibilityService.isReady(this@RemoteHelpService)
                if (!controlReady) afterId = 0

                val now = SystemClock.elapsedRealtime()
                if (now - lastHeartbeat >= HEARTBEAT_INTERVAL_MS) {
                    lastHeartbeat = now
                    val state = runCatching {
                        apiCall {
                            container.api.remoteHeartbeat(
                                com.edumath.uchus.data.api.RemoteHeartbeatRequest(
                                    sessionId = sessionId,
                                    canControl = controlReady,
                                )
                            )
                        }
                    }.getOrNull()
                    if (state != null && state.session?.isActive == false) {
                        stopSelf()
                        return@launch
                    }
                    updateNotificationIfNeeded()
                }

                if (controlReady) {
                    val batch = runCatching {
                        apiCall { container.api.remoteCommands(sessionId, afterId) }
                    }.getOrNull()
                    if (batch != null) {
                        val service = RemoteControlAccessibilityService.instance
                        for (command in batch.commands) {
                            afterId = maxOf(afterId, command.id)
                            if (service == null) break
                            execute(service, command)
                        }
                    }
                }
                delay(COMMAND_INTERVAL_MS)
            }
        }
    }

    private fun execute(service: RemoteControlAccessibilityService, command: RemoteCommandDto) {
        when (command.kind) {
            "tap" -> service.perform(command)
            "swipe" -> service.perform(command)
            "back", "home", "recents", "notifications" -> service.perform(command)
        }
    }

    // --------------------------------------------------------- уведомление
    private fun buildNotification(control: Boolean): Notification {
        val open = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val openPending = PendingIntent.getActivity(
            this,
            NOTIFICATION_ID,
            open,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val stop = Intent(this, RemoteHelpService::class.java).apply {
            action = ACTION_STOP
        }
        val stopPending = PendingIntent.getService(
            this,
            NOTIFICATION_ID + 1,
            stop,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("Родитель смотрит ваш экран")
            .setContentText(
                if (control) {
                    "Идёт удалённая помощь. Родитель может нажимать за вас."
                } else {
                    "Идёт удалённая помощь. Экран передаётся родителю."
                }
            )
            .setStyle(
                NotificationCompat.BigTextStyle().bigText(
                    if (control) {
                        "Идёт удалённая помощь. Родитель видит экран и может нажимать за вас. " +
                            "Нажмите «Остановить», чтобы сразу завершить."
                    } else {
                        "Идёт удалённая помощь. Родитель видит экран. " +
                            "Нажмите «Остановить», чтобы сразу завершить."
                    }
                )
            )
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setContentIntent(openPending)
            .addAction(0, "Остановить", stopPending)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    private fun updateNotificationIfNeeded() {
        if (lastNotificationControl == controlReady) return
        lastNotificationControl = controlReady
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        runCatching { manager.notify(NOTIFICATION_ID, buildNotification(controlReady)) }
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Удалённая помощь",
            NotificationManager.IMPORTANCE_LOW,
        ).apply {
            description = "Показ экрана родителю во время удалённой помощи"
            setShowBadge(false)
        }
        manager.createNotificationChannel(channel)
    }

    private fun screenMetrics(): DisplayMetrics {
        val metrics = DisplayMetrics()
        @Suppress("DEPRECATION")
        val display = (getSystemService(Context.WINDOW_SERVICE) as WindowManager).defaultDisplay
        @Suppress("DEPRECATION")
        display.getRealMetrics(metrics)
        return metrics
    }

    // ------------------------------------------------------------- остановка
    override fun onDestroy() {
        running = false
        commandJob?.cancel()
        reader?.setOnImageAvailableListener(null, null)
        virtualDisplay?.release()
        virtualDisplay = null
        reader?.close()
        reader = null
        projection?.stop()
        projection = null
        captureHandler = null
        captureThread?.quitSafely()
        captureThread = null

        val container = (application as? UchusApp)?.container
        if (container != null && sessionId > 0) {
            CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
                runCatching {
                    apiCall { container.api.remoteStop(mapOf("session_id" to sessionId)) }
                }
            }
        }
        scope.coroutineContext[Job]?.cancel()
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    companion object {
        private const val CHANNEL_ID = "remote_help"
        private const val NOTIFICATION_ID = 4200
        private const val FRAME_INTERVAL_MS = 450L
        private const val JPEG_QUALITY = 45
        private const val COMMAND_INTERVAL_MS = 600L
        private const val HEARTBEAT_INTERVAL_MS = 5_000L

        const val ACTION_STOP = "com.edumath.uchus.REMOTE_HELP_STOP"
        const val EXTRA_SESSION_ID = "remote_session_id"
        const val EXTRA_RESULT_CODE = "remote_result_code"
        const val EXTRA_RESULT_DATA = "remote_result_data"

        fun start(context: Context, sessionId: Int, resultCode: Int, data: Intent) {
            val intent = Intent(context, RemoteHelpService::class.java).apply {
                putExtra(EXTRA_SESSION_ID, sessionId)
                putExtra(EXTRA_RESULT_CODE, resultCode)
                putExtra(EXTRA_RESULT_DATA, data)
            }
            ContextCompat.startForegroundService(context, intent)
        }

        fun stop(context: Context) {
            context.stopService(Intent(context, RemoteHelpService::class.java))
        }

        fun isRunning(context: Context): Boolean = running

        @Volatile
        var running: Boolean = false
            private set
    }
}
