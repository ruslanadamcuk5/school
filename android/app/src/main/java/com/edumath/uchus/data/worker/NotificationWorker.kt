package com.edumath.uchus.data.worker

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.os.Build
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
import java.util.concurrent.TimeUnit

/**
 * Фоновый опрос уведомлений: каждые 15 минут получает новые уведомления
 * с сервера и показывает их как системные (push-подобные) уведомления Android.
 *
 * Внешние push-сервисы не используются — только собственный API платформы.
 */
class NotificationWorker(
    appContext: Context,
    workerParams: WorkerParameters,
) : CoroutineWorker(appContext, workerParams) {

    override suspend fun doWork(): Result {
        val container = (applicationContext as? UchusApp)?.container ?: return Result.success()
        // Если пользователь не вошёл — опрашивать нечего.
        val stored = container.session.hydrate()
        if (stored == null || stored.token.isBlank()) return Result.success()

        ensureChannel(applicationContext)

        val response = runCatching {
            apiCall { container.api.notifications(limit = 50) }
        }.getOrNull() ?: return Result.retry()

        val prefs = applicationContext.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val lastSeen = prefs.getInt(KEY_LAST_SEEN, 0)
        var newest = lastSeen

        response.notifications
            .asReversed()
            .filter { !it.isRead && it.id > lastSeen }
            .forEach { item ->
                postNotification(item.id, item.title ?: "Школьник", item.body ?: "")
                if (item.id > newest) newest = item.id
            }

        if (newest > lastSeen) {
            prefs.edit().putInt(KEY_LAST_SEEN, newest).apply()
        }
        return Result.success()
    }

    private fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "Школьник — уведомления",
                NotificationManager.IMPORTANCE_DEFAULT,
            ).apply {
                description = "Новые задания, выполненные и пропущенные работы"
            }
            val manager = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
            manager.createNotificationChannel(channel)
        }
    }

    private fun postNotification(id: Int, title: String, body: String) {
        val intent = Intent(applicationContext, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pending = PendingIntent.getActivity(
            applicationContext,
            id,
            intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(applicationContext, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(pending)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()
        runCatching {
            NotificationManagerCompat.from(applicationContext).notify(id, notification)
        }
    }

    companion object {
        private const val CHANNEL_ID = "school_notifications"
        private const val PREFS = "school_notifications"
        private const val KEY_LAST_SEEN = "last_seen_id"
        private const val UNIQUE_NAME = "school_notification_poll"

        /** Зарегистрировать периодический опрос (каждые 15 минут). */
        fun enqueue(context: Context) {
            val request = PeriodicWorkRequestBuilder<NotificationWorker>(15, TimeUnit.MINUTES)
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
