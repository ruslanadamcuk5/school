package com.edumath.uchus.data.remote

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.content.ComponentName
import android.content.Context
import android.content.Intent
import android.graphics.Path
import android.provider.Settings
import android.view.accessibility.AccessibilityEvent
import com.edumath.uchus.data.api.RemoteCommandDto
import kotlin.math.max

/**
 * Служба доступности, которая выполняет нажатия и свайпы родителя.
 *
 * Она ничего не читает с экрана: только жесты и системные кнопки. Ребёнок
 * включает её вручную в настройках Android и может выключить в любой момент.
 */
class RemoteControlAccessibilityService : AccessibilityService() {

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit

    override fun onInterrupt() = Unit

    override fun onDestroy() {
        if (instance === this) instance = null
        super.onDestroy()
    }

    /** Выполнить команду родителя. Возвращает false, если жест не принят. */
    fun perform(command: RemoteCommandDto): Boolean {
        val metrics = resources.displayMetrics
        val width = max(1, metrics.widthPixels)
        val height = max(1, metrics.heightPixels)
        return when (command.kind) {
            "tap" -> gesture(
                Path().apply {
                    moveTo(command.x.coerceIn(0f, 1f) * width, command.y.coerceIn(0f, 1f) * height)
                },
                duration = 60L,
            )

            "swipe" -> {
                val startX = command.x.coerceIn(0f, 1f) * width
                val startY = command.y.coerceIn(0f, 1f) * height
                val endX = command.x2.coerceIn(0f, 1f) * width
                val endY = command.y2.coerceIn(0f, 1f) * height
                gesture(
                    Path().apply {
                        moveTo(startX, startY)
                        lineTo(endX, endY)
                    },
                    duration = command.durationMs.coerceIn(80, 1200).toLong(),
                )
            }

            "back" -> performGlobalAction(GLOBAL_ACTION_BACK)
            "home" -> performGlobalAction(GLOBAL_ACTION_HOME)
            "recents" -> performGlobalAction(GLOBAL_ACTION_RECENTS)
            "notifications" -> performGlobalAction(GLOBAL_ACTION_NOTIFICATIONS)
            else -> false
        }
    }

    private fun gesture(path: Path, duration: Long): Boolean {
        val stroke = GestureDescription.StrokeDescription(path, 0L, duration)
        val description = GestureDescription.Builder().addStroke(stroke).build()
        return dispatchGesture(description, null, null)
    }

    companion object {
        @Volatile
        var instance: RemoteControlAccessibilityService? = null
            private set

        /** Включена ли служба в настройках доступности. */
        fun isEnabled(context: Context): Boolean {
            val expected = ComponentName(context, RemoteControlAccessibilityService::class.java)
            val raw = Settings.Secure.getString(
                context.contentResolver,
                Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES,
            ) ?: return false
            return raw.split(':')
                .mapNotNull { ComponentName.unflattenFromString(it) }
                .any { it == expected }
        }

        /** Готова ли служба выполнять жесты прямо сейчас. */
        fun isReady(context: Context): Boolean =
            isEnabled(context) && instance != null

        fun openSettings(context: Context) {
            val intent = Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            runCatching { context.startActivity(intent) }
        }
    }
}
