package com.edumath.uchus.data.worker

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.work.Constraints
import androidx.work.CoroutineWorker
import androidx.work.ExistingPeriodicWorkPolicy
import androidx.work.NetworkType
import androidx.work.PeriodicWorkRequestBuilder
import androidx.work.WorkManager
import androidx.work.WorkerParameters
import com.edumath.uchus.MainActivity
import com.edumath.uchus.R
import com.edumath.uchus.UchusApp
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.data.location.LocationTrackingService
import java.util.TimeZone
import java.util.concurrent.TimeUnit

/**
 * Проверяет команду родителя «включить геолокацию» и следит, чтобы служба
 * передачи местоположения была запущена.
 *
 * Полностью включить GPS без системного разрешения приложение не может,
 * поэтому при отсутствии доступа worker показывает заметное уведомление
 * и открывает экран разрешений по нажатию.
 */
class LocationSyncWorker(
    appContext: Context,
    workerParams: WorkerParameters,
) : CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): Result {
        val container = (applicationContext as? UchusApp)?.container
            ?: return Result.success()
        val stored = container.session.hydrate()
        if (stored == null || stored.token.isBlank()) return Result.success()

        val tzMinutes = TimeZone.getDefault().getOffset(System.currentTimeMillis()) / 60000
        val status = runCatching {
            apiCall { container.api.locationStatus(tzMinutes) }
        }.getOrNull() ?: return Result.retry()

        val forcePending = status.forcePending || status.settings?.forcePending == true
        val hasPermission = LocationTrackingService.hasPermission(applicationContext)

        if (hasPermission) {
            // Повторный запуск безопасен: служба сама игнорирует дубли.
            runCatching { LocationTrackingService.start(applicationContext) }
            if (forcePending) {
                runCatching { apiCall { container.api.ackLocationForce() } }
            }
            NotificationManagerCompat.from(applicationContext)
                .cancel(NOTIFICATION_ID)
        } else if (forcePending) {
            ensureChannel()
            postPermissionNotification()
        }
        return Result.success()
    }

    private fun ensureChannel() {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = applicationContext.getSystemService(Context.NOTIFICATION_SERVICE)
            as NotificationManager
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Геолокация ребёнка",
            NotificationManager.IMPORTANCE_HIGH,
        ).apply {
            description = "Запросы родителя включить геолокацию на телефоне"
            setShowBadge(true)
        }
        manager.createNotificationChannel(channel)
    }

    private fun postPermissionNotification() {
        val openApp = Intent(applicationContext, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val openAppPending = PendingIntent.getActivity(
            applicationContext,
            0,
            openApp,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val settingsIntent = Intent(
            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
            Uri.parse("package:" + applicationContext.packageName),
        ).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK
        }
        val settingsPending = PendingIntent.getActivity(
            applicationContext,
            1,
            settingsIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(applicationContext, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("Родитель включил геолокацию")
            .setContentText("Разрешите доступ к местоположению, чтобы родитель видел, где вы.")
            .setStyle(
                NotificationCompat.BigTextStyle().bigText(
                    "Родитель просит включить геолокацию на этом телефоне. " +
                        "Откройте приложение и разрешите доступ к местоположению."
                )
            )
            .setAutoCancel(true)
            .setContentIntent(openAppPending)
            .addAction(0, "Разрешить", openAppPending)
            .addAction(0, "Настройки", settingsPending)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()
        runCatching {
            NotificationManagerCompat.from(applicationContext)
                .notify(NOTIFICATION_ID, notification)
        }
    }

    companion object {
        private const val CHANNEL_ID = "child_location_alert"
        private const val NOTIFICATION_ID = 4243
        private const val UNIQUE_NAME = "child_location_sync"

        /** Периодическая проверка команды родителя и состояния службы. */
        fun enqueue(context: Context) {
            val request = PeriodicWorkRequestBuilder<LocationSyncWorker>(15, TimeUnit.MINUTES)
                .setConstraints(
                    Constraints.Builder()
                        .setRequiredNetworkType(NetworkType.CONNECTED)
                        .build()
                )
                .build()
            runCatching {
                WorkManager.getInstance(context).enqueueUniquePeriodicWork(
                    UNIQUE_NAME,
                    ExistingPeriodicWorkPolicy.KEEP,
                    request,
                )
            }
        }
    }
}
