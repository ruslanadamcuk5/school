package com.edumath.uchus.data.sound

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.AudioManager
import android.media.MediaPlayer
import android.media.RingtoneManager
import android.net.Uri
import android.os.Build
import android.os.IBinder
import android.os.PowerManager
import android.provider.Settings
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import com.edumath.uchus.MainActivity
import com.edumath.uchus.R
import com.edumath.uchus.UchusApp
import com.edumath.uchus.data.api.SoundAckRequest
import com.edumath.uchus.data.api.apiCall
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withTimeoutOrNull

/**
 * Громкий вызов ребёнка по команде родителя.
 *
 * Звук идёт через поток будильника: он слышен даже в беззвучном режиме.
 * Если ребёнок один раз разрешил приложению доступ к «Не беспокоить»,
 * телефон дополнительно переводится в обычный режим, чтобы дозвонились
 * и обычные звонки. Подтверждение каждой команды не требуется.
 */
class SoundAlertService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val ackScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private var player: MediaPlayer? = null
    private var stopJob: Job? = null
    private var api: com.edumath.uchus.data.api.ApiService? = null
    private var commandId = 0
    private var mode = "alarm"

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            // Служба уже запущена и показывает уведомление. Если система
            // перезапустила её только ради остановки — сначала выполняем
            // требование foreground service, затем сразу останавливаемся.
            ServiceCompat.startForeground(
                this,
                NOTIFICATION_ID,
                buildNotification(),
                foregroundType(),
            )
            stopRinging("stopped")
            return START_NOT_STICKY
        }

        val id = intent?.getIntExtra(EXTRA_COMMAND_ID, 0) ?: 0
        if (id <= 0) {
            stopSelf()
            return START_NOT_STICKY
        }
        ServiceCompat.startForeground(
            this,
            NOTIFICATION_ID,
            buildNotification(),
            foregroundType(),
        )
        if (commandId == id && player?.isPlaying == true) return START_NOT_STICKY

        val previous = commandId
        if (previous > 0 && previous != id) {
            scope.launch { ackRequest(previous, "done", mode, "replaced") }
        }
        commandId = id
        mode = "alarm"
        SoundAlertState.ringing.value = id
        markCommandSeen(this, id)
        api = (application as? UchusApp)?.container?.api

        startRinging()
        return START_NOT_STICKY
    }

    private fun startRinging() {
        runCatching { player?.stop() }
        runCatching { player?.release() }
        player = null
        val audio = getSystemService(Context.AUDIO_SERVICE) as? AudioManager
        if (audio != null) {
            runCatching {
                val alarmMax = audio.getStreamMaxVolume(AudioManager.STREAM_ALARM)
                audio.setStreamVolume(AudioManager.STREAM_ALARM, alarmMax, 0)
                val ringMax = audio.getStreamMaxVolume(AudioManager.STREAM_RING)
                audio.setStreamVolume(AudioManager.STREAM_RING, ringMax, 0)
            }
            if (hasDndAccess(this)) {
                runCatching {
                    audio.ringerMode = AudioManager.RINGER_MODE_NORMAL
                    val manager = getSystemService(Context.NOTIFICATION_SERVICE)
                        as NotificationManager
                    manager.setInterruptionFilter(
                        NotificationManager.INTERRUPTION_FILTER_ALL
                    )
                    mode = "ringer"
                }
            }
        }

        val started = playAlarm()
        ack("ringing", mode, if (started) "alarm" else "failed")
        updateNotification()
        if (!started) {
            ack("failed", mode, "player")
            stopRinging("failed")
            return
        }
        stopJob?.cancel()
        stopJob = scope.launch {
            delay(RING_DURATION_MS)
            stopRinging("timeout")
        }
    }

    private fun playAlarm(): Boolean {
        val uri = RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM)
            ?: RingtoneManager.getDefaultUri(RingtoneManager.TYPE_RINGTONE)
            ?: return false
        return runCatching {
            val mp = MediaPlayer()
            mp.setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ALARM)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION)
                    .build()
            )
            mp.setWakeMode(this, PowerManager.PARTIAL_WAKE_LOCK)
            mp.setDataSource(this, uri)
            mp.isLooping = true
            mp.prepare()
            mp.start()
            player = mp
            true
        }.getOrDefault(false)
    }

    private fun stopRinging(detail: String) {
        val id = commandId
        stopJob?.cancel()
        stopJob = null
        runCatching { player?.stop() }
        runCatching { player?.release() }
        player = null
        if (SoundAlertState.ringing.value == id) {
            SoundAlertState.ringing.value = 0
        }
        ServiceCompat.stopForeground(this, ServiceCompat.STOP_FOREGROUND_REMOVE)
        commandId = 0
        if (id <= 0) {
            stopSelf()
            return
        }
        // Ответ серверу отправляем после остановки звука, но службу держим
        // живой ещё несколько секунд — иначе запрос может не успеть уйти.
        ackScope.launch {
            withTimeoutOrNull(6_000) { ackRequest(id, "done", mode, detail) }
            stopSelf()
        }
    }

    private fun ack(status: String, mode: String, detail: String) {
        val id = commandId
        if (id <= 0) return
        scope.launch { ackRequest(id, status, mode, detail) }
    }

    private suspend fun ackRequest(
        id: Int,
        status: String,
        mode: String,
        detail: String,
    ) {
        val service = api ?: return
        runCatching {
            apiCall {
                service.ackSoundCommand(
                    id,
                    SoundAckRequest(status = status, mode = mode, detail = detail)
                )
            }
        }
    }

    override fun onDestroy() {
        stopJob?.cancel()
        runCatching { player?.stop() }
        runCatching { player?.release() }
        player = null
        if (SoundAlertState.ringing.value == commandId) {
            SoundAlertState.ringing.value = 0
        }
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun foregroundType(): Int {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK
        } else {
            0
        }
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Звук вызова от родителя",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "Громкий сигнал, когда родитель зовёт ребёнка"
            setSound(null, null)
            enableVibration(true)
            vibrationPattern = longArrayOf(0, 800, 400, 800, 400, 800)
            setShowBadge(true)
        }
        manager.createNotificationChannel(channel)
    }

    private fun buildNotification(): Notification {
        val openApp = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val openPending = PendingIntent.getActivity(
            this,
            0,
            openApp,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val stopPending = PendingIntent.getService(
            this,
            1,
            Intent(this, SoundAlertService::class.java).setAction(ACTION_STOP),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val text = if (mode == "ringer") {
            "Телефон включён на звук и громко звонит. Нажми, чтобы остановить."
        } else {
            "Телефон громко звонит, даже если был на беззвучном. Нажми, чтобы остановить."
        }
        val builder = NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("🔊 Родитель зовёт")
            .setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setPriority(NotificationCompat.PRIORITY_MAX)
            .setCategory(NotificationCompat.CATEGORY_ALARM)
            .setVisibility(NotificationCompat.VISIBILITY_PUBLIC)
            .setOngoing(true)
            .setAutoCancel(false)
            .setContentIntent(openPending)
            .setFullScreenIntent(openPending, true)
            .addAction(0, "Остановить", stopPending)
        if (!hasDndAccess(this)) {
            val settingsIntent = Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS)
            val settingsPending = PendingIntent.getActivity(
                this,
                2,
                settingsIntent,
                PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
            )
            builder.addAction(0, "Разрешить звонки", settingsPending)
        }
        return builder.build()
    }

    private fun updateNotification() {
        runCatching {
            val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.notify(NOTIFICATION_ID, buildNotification())
        }
    }

    companion object {
        private const val CHANNEL_ID = "child_sound_call"
        private const val NOTIFICATION_ID = 4251
        private const val EXTRA_COMMAND_ID = "command_id"
        private const val ACTION_STOP = "com.edumath.uchus.sound.STOP"
        private const val RING_DURATION_MS = 45_000L
        private const val PREFS = "child_sound"
        private const val KEY_LAST_COMMAND = "last_command_id"

        /** Запустить громкий сигнал. true — служба приняла команду. */
        fun ring(context: Context, commandId: Int): Boolean {
            return runCatching {
                val intent = Intent(context, SoundAlertService::class.java)
                    .putExtra(EXTRA_COMMAND_ID, commandId)
                ContextCompat.startForegroundService(context, intent)
                true
            }.getOrDefault(false)
        }

        fun stop(context: Context) {
            runCatching {
                val intent = Intent(context, SoundAlertService::class.java)
                    .setAction(ACTION_STOP)
                ContextCompat.startForegroundService(context, intent)
            }
        }

        /** Последняя команда, которую уже видело приложение. */
        fun lastCommandId(context: Context): Int {
            return context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .getInt(KEY_LAST_COMMAND, 0)
        }

        fun markCommandSeen(context: Context, commandId: Int) {
            context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
                .edit()
                .putInt(KEY_LAST_COMMAND, commandId)
                .apply()
        }

        /** Есть ли у приложения доступ к режиму «Не беспокоить». */
        fun hasDndAccess(context: Context): Boolean {
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE)
                as? NotificationManager ?: return false
            return manager.isNotificationPolicyAccessGranted
        }

        fun openDndSettings(context: Context) {
            runCatching {
                context.startActivity(
                    Intent(Settings.ACTION_NOTIFICATION_POLICY_ACCESS_SETTINGS).apply {
                        flags = Intent.FLAG_ACTIVITY_NEW_TASK
                    }
                )
            }
        }
    }
}

/** Текущий звонок — чтобы показать ребёнку диалог с кнопкой «Остановить». */
object SoundAlertState {
    val ringing = MutableStateFlow(0)
}
