package com.edumath.uchus.ui.sound

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.edumath.uchus.MainActivity
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.SessionDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.data.location.LocationTrackingService
import com.edumath.uchus.data.sound.SoundAlertService
import com.edumath.uchus.data.sound.SoundAlertState
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive

/**
 * Звуковой вызов на телефоне ребёнка.
 *
 * Основной опрос идёт в фоновой службе геолокации. Этот экран страхует,
 * когда служба ещё не запущена: пока приложение открыто, команда тоже
 * проверяется. Диалог позволяет остановить громкий сигнал в любой момент.
 */
@Composable
fun SoundAlertGate(container: AppContainer, session: SessionDto?) {
    if (session?.user?.role != "student" || session.learner == null) return

    val context = LocalContext.current
    val ringing by SoundAlertState.ringing.collectAsState()

    LaunchedEffect(Unit) {
        while (isActive) {
            if (!MainActivity.isInForeground || LocationTrackingService.isRunning) {
                delay(5_000)
                continue
            }
            val lastSeen = SoundAlertService.lastCommandId(context)
            val command = runCatching {
                apiCall { container.api.soundCommand(lastSeen) }
            }.getOrNull()?.command
            if (command != null && command.id > lastSeen) {
                if (SoundAlertService.ring(context, command.id)) {
                    SoundAlertService.markCommandSeen(context, command.id)
                }
            }
            delay(10_000)
        }
    }

    if (ringing <= 0) return

    val dndGranted = SoundAlertService.hasDndAccess(context)
    AlertDialog(
        onDismissRequest = { SoundAlertService.stop(context) },
        title = { Text("🔊 Родитель зовёт") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "Телефон звонит громко, чтобы ты услышал. " +
                        "Нажми «Остановить», если не можешь ответить."
                )
                if (!dndGranted) {
                    Text(
                        "Обычные звонки могут оставаться беззвучными. Разреши " +
                            "приложению управлять звуком — это нужно сделать один раз.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        },
        confirmButton = {
            Button(onClick = { SoundAlertService.stop(context) }) {
                Text("Остановить")
            }
        },
        dismissButton = if (dndGranted) null else {
            {
                TextButton(onClick = { SoundAlertService.openDndSettings(context) }) {
                    Text("Разрешить звонки")
                }
            }
        },
    )
}
