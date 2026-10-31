package com.edumath.uchus.data.location

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.BatteryManager
import android.os.Build
import android.os.Bundle
import android.os.IBinder
import android.os.Looper
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import com.edumath.uchus.MainActivity
import com.edumath.uchus.R
import com.edumath.uchus.UchusApp
import com.edumath.uchus.data.api.ApiException
import com.edumath.uchus.data.api.LocationPointPayload
import com.edumath.uchus.data.api.LocationPointsRequest
import com.edumath.uchus.data.api.apiCall
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Фоновая передача геолокации ребёнка.
 *
 * Работает постоянно, без согласия ребёнка. Использует системный
 * LocationManager — без Google Play Services. В строке состояния всегда
 * видно уведомление. Служба запускается после входа, при открытии экрана
 * «Геолокация» и по команде родителя (через LocationSyncWorker).
 */
class LocationTrackingService : Service() {

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val pending = mutableListOf<LocationPointPayload>()
    private val timeFormat = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).apply {
        timeZone = TimeZone.getTimeZone("UTC")
    }

    private var manager: LocationManager? = null
    private var flushJob: Job? = null
    private var listener: LocationListener? = null
    private var api: com.edumath.uchus.data.api.ApiService? = null
    private var started = false

    override fun onCreate() {
        super.onCreate()
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (!hasLocationPermission()) {
            stopSelf()
            return START_NOT_STICKY
        }
        val serviceType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION
        } else {
            0
        }
        ServiceCompat.startForeground(this, NOTIFICATION_ID, buildNotification(), serviceType)
        if (started) return START_STICKY
        started = true

        val container = (application as? UchusApp)?.container
        if (container == null) {
            stopSelf()
            return START_NOT_STICKY
        }
        api = container.api
        scope.launch {
            val stored = container.session.hydrate()
            if (stored == null || stored.token.isBlank()) {
                stopSelf()
                return@launch
            }
            registerUpdates()
        }
        flushJob = scope.launch {
            while (isActive) {
                delay(FLUSH_INTERVAL_MS)
                flush()
            }
        }
        return START_STICKY
    }

    override fun onDestroy() {
        flushJob?.cancel()
        runCatching { listener?.let { manager?.removeUpdates(it) } }
        listener = null
        scope.coroutineContext[Job]?.cancel()
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun hasLocationPermission(): Boolean {
        val fine = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_FINE_LOCATION)
        val coarse = ContextCompat.checkSelfPermission(this, Manifest.permission.ACCESS_COARSE_LOCATION)
        return fine == PackageManager.PERMISSION_GRANTED || coarse == PackageManager.PERMISSION_GRANTED
    }

    private fun registerUpdates() {
        if (!hasLocationPermission()) return
        val locationManager = getSystemService(Context.LOCATION_SERVICE) as? LocationManager ?: return
        manager = locationManager
        val callback = object : LocationListener {
            override fun onLocationChanged(location: Location) {
                addPoint(location)
            }

            override fun onStatusChanged(provider: String?, status: Int, extras: Bundle?) = Unit
            override fun onProviderEnabled(provider: String) = Unit
            override fun onProviderDisabled(provider: String) = Unit
        }
        listener = callback
        val providers = listOf(LocationManager.GPS_PROVIDER, LocationManager.NETWORK_PROVIDER)
        var requested = false
        for (provider in providers) {
            val enabled = runCatching { locationManager.isProviderEnabled(provider) }.getOrDefault(false)
            if (!enabled) continue
            runCatching {
                locationManager.requestLocationUpdates(
                    provider,
                    MIN_TIME_MS,
                    MIN_DISTANCE_M,
                    callback,
                    Looper.getMainLooper(),
                )
                requested = true
            }
        }
        if (!requested) {
            runCatching {
                locationManager.requestLocationUpdates(
                    LocationManager.GPS_PROVIDER,
                    MIN_TIME_MS,
                    MIN_DISTANCE_M,
                    callback,
                    Looper.getMainLooper(),
                )
            }
        }
        runCatching {
            locationManager.getLastKnownLocation(LocationManager.GPS_PROVIDER)
        }.getOrNull()?.let { addPoint(it) }
        runCatching {
            locationManager.getLastKnownLocation(LocationManager.NETWORK_PROVIDER)
        }.getOrNull()?.let { addPoint(it) }
    }

    private fun addPoint(location: Location) {
        val payload = LocationPointPayload(
            lat = location.latitude,
            lon = location.longitude,
            accuracy = if (location.hasAccuracy()) location.accuracy.toDouble() else null,
            altitude = if (location.hasAltitude()) location.altitude else null,
            speed = if (location.hasSpeed()) location.speed.toDouble() else null,
            source = "android",
            recordedAt = timeFormat.format(Date(location.time)),
        )
        synchronized(pending) {
            pending.add(payload)
            while (pending.size > MAX_PENDING) pending.removeAt(0)
        }
        if (synchronized(pending) { pending.size } >= FLUSH_AT_POINTS) {
            scope.launch { flush() }
        }
    }

    private suspend fun flush() {
        val api = api ?: return
        val batch = synchronized(pending) {
            if (pending.isEmpty()) return
            pending.take(MAX_BATCH).toList()
        }
        val battery = batteryLevel()
        val result = runCatching {
            apiCall { api.sendLocationPoints(LocationPointsRequest(batch, battery)) }
        }
        result.onSuccess {
            synchronized(pending) { pending.removeAll(batch.toSet()) }
        }.onFailure { error ->
            // Передачу больше нельзя выключить: останавливаемся только при
            // истёкшей авторизации.
            if (error is ApiException && error.status == 401) {
                stopSelf()
            }
        }
    }

    private fun batteryLevel(): Int? {
        val intent = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED)) ?: return null
        val level = intent.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
        val scale = intent.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
        if (level < 0 || scale <= 0) return null
        return (level * 100 / scale).coerceIn(0, 100)
    }

    private fun createChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Геолокация ребёнка",
            NotificationManager.IMPORTANCE_LOW,
        ).apply {
            description = "Показывает, что приложение передаёт местоположение родителям"
            setShowBadge(false)
        }
        manager.createNotificationChannel(channel)
    }

    private fun buildNotification(): android.app.Notification {
        val intent = Intent(this, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pendingIntent = PendingIntent.getActivity(
            this,
            0,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("Геолокация включена")
            .setContentText("Родители видят твою позицию. Нажми, чтобы открыть приложение.")
            .setOngoing(true)
            .setSilent(true)
            .setContentIntent(pendingIntent)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    companion object {
        private const val CHANNEL_ID = "child_location"
        private const val NOTIFICATION_ID = 4242
        private const val MIN_TIME_MS = 15_000L
        private const val MIN_DISTANCE_M = 10f
        private const val FLUSH_INTERVAL_MS = 30_000L
        private const val FLUSH_AT_POINTS = 5
        private const val MAX_BATCH = 100
        private const val MAX_PENDING = 500

        fun start(context: Context) {
            if (!hasPermission(context)) return
            val intent = Intent(context, LocationTrackingService::class.java)
            runCatching {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    ContextCompat.startForegroundService(context, intent)
                } else {
                    context.startService(intent)
                }
            }
        }

        fun stop(context: Context) {
            runCatching { context.stopService(Intent(context, LocationTrackingService::class.java)) }
        }

        fun hasPermission(context: Context): Boolean {
            val fine = ContextCompat.checkSelfPermission(
                context, Manifest.permission.ACCESS_FINE_LOCATION
            )
            val coarse = ContextCompat.checkSelfPermission(
                context, Manifest.permission.ACCESS_COARSE_LOCATION
            )
            return fine == PackageManager.PERMISSION_GRANTED ||
                coarse == PackageManager.PERMISSION_GRANTED
        }
    }
}
