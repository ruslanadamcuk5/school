package com.edumath.uchus.ui.update

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInstaller
import android.os.Build
import android.os.Handler
import android.os.Looper
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.IntentCompat
import com.edumath.uchus.BuildConfig
import com.edumath.uchus.MainActivity
import com.edumath.uchus.R

/** Результат передачи APK системному установщику. */
class UpdateInstallReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != ACTION_INSTALL_STATUS) return
        when (intent.getIntExtra(
            PackageInstaller.EXTRA_STATUS,
            PackageInstaller.STATUS_FAILURE,
        )) {
            PackageInstaller.STATUS_PENDING_USER_ACTION -> {
                val confirm = IntentCompat.getParcelableExtra(
                    intent,
                    Intent.EXTRA_INTENT,
                    Intent::class.java,
                ) ?: return
                confirm.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                runCatching { context.startActivity(confirm) }
            }

            PackageInstaller.STATUS_SUCCESS -> {
                UpdateStateStore.clearError(context)
            }

            else -> {
                val message = intent.getStringExtra(
                    PackageInstaller.EXTRA_STATUS_MESSAGE
                )?.takeIf { it.isNotBlank() } ?: "Android отклонил установку обновления."
                UpdateStateStore.setError(context, message)
            }
        }
    }

    companion object {
        const val ACTION_INSTALL_STATUS = "com.edumath.uchus.UPDATE_INSTALL_STATUS"
    }
}

/**
 * После установки новой версии Android убивает старый процесс и присылает
 * MY_PACKAGE_REPLACED уже новому приложению. Пробуем сразу открыть его,
 * а если система не разрешает запуск из фона — оставляем уведомление.
 */
class UpdateRestartReceiver : BroadcastReceiver() {

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != Intent.ACTION_MY_PACKAGE_REPLACED) return

        val open = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or
                Intent.FLAG_ACTIVITY_CLEAR_TOP or
                Intent.FLAG_ACTIVITY_SINGLE_TOP
        }
        runCatching { context.startActivity(open) }

        // Если Android не разрешил запуск из фона, через пару секунд
        // покажем уведомление. Если приложение уже открылось — не мешаем.
        val pending = goAsync()
        Handler(Looper.getMainLooper()).postDelayed({
            if (!MainActivity.isInForeground) {
                UpdateNotifications.showInstalled(context)
            }
            pending.finish()
        }, 2_500L)
    }
}

/** Уведомление-запасной вариант, если автозапуск после обновления заблокирован. */
object UpdateNotifications {

    private const val CHANNEL_ID = "app_updates"
    private const val NOTIFICATION_ID = 4101

    fun showInstalled(context: Context) {
        ensureChannel(context)
        val version = UpdateStateStore.pendingName(context)
            ?.takeIf { it.isNotBlank() }
            ?: BuildConfig.VERSION_NAME
        val open = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP
        }
        val pending = PendingIntent.getActivity(
            context,
            NOTIFICATION_ID,
            open,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_notification)
            .setContentTitle("Обновление выполнено")
            .setContentText("Приложение обновлено до версии $version. Откройте его, чтобы продолжить.")
            .setStyle(
                NotificationCompat.BigTextStyle().bigText(
                    "Приложение обновлено до версии $version. Откройте его, чтобы продолжить."
                )
            )
            .setAutoCancel(true)
            .setContentIntent(pending)
            .setPriority(NotificationCompat.PRIORITY_DEFAULT)
            .build()
        runCatching {
            NotificationManagerCompat.from(context).notify(NOTIFICATION_ID, notification)
        }
    }

    private fun ensureChannel(context: Context) {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.O) return
        val manager = context.getSystemService(Context.NOTIFICATION_SERVICE)
            as NotificationManager
        val channel = NotificationChannel(
            CHANNEL_ID,
            "Обновления приложения",
            NotificationManager.IMPORTANCE_DEFAULT,
        ).apply {
            description = "Сообщения о завершении установки обновлений"
        }
        manager.createNotificationChannel(channel)
    }
}
