package com.edumath.uchus.ui.remote

import android.app.Activity
import android.content.Context
import android.media.projection.MediaProjectionManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.edumath.uchus.MainActivity
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.RemoteAcceptRequest
import com.edumath.uchus.data.api.RemoteSessionInfoDto
import com.edumath.uchus.data.api.SessionDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.data.remote.RemoteControlAccessibilityService
import com.edumath.uchus.data.remote.RemoteHelpService
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * Запросы удалённой помощи на телефоне ребёнка.
 *
 * Показывает предложение родителя, просит системное разрешение на показ
 * экрана и постоянную плашку «Родитель смотрит экран» с кнопкой остановки.
 * Без явного разрешения ребёнка ничего не передаётся.
 */
@Composable
fun RemoteHelpGate(container: AppContainer, session: SessionDto?) {
    if (session?.user?.role != "student" || session.learner == null) return

    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val lifecycleOwner = LocalLifecycleOwner.current
    var incoming by remember { mutableStateOf<RemoteSessionInfoDto?>(null) }
    var dismissedId by remember { mutableStateOf(0) }
    var busy by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }
    var controlEnabled by remember {
        mutableStateOf(RemoteControlAccessibilityService.isEnabled(context))
    }
    var pendingAccept by remember { mutableStateOf<RemoteSessionInfoDto?>(null) }

    val projectionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.StartActivityForResult()
    ) { result ->
        val request = pendingAccept
        pendingAccept = null
        if (request == null) return@rememberLauncherForActivityResult
        if (result.resultCode != Activity.RESULT_OK || result.data == null) {
            message = "Без разрешения показа экрана помощь невозможна."
            scope.launch {
                runCatching {
                    apiCall { container.api.remoteDecline(mapOf("session_id" to request.id)) }
                }
                incoming = null
            }
            return@rememberLauncherForActivityResult
        }
        busy = true
        scope.launch {
            try {
                val accepted = apiCall {
                    container.api.remoteAccept(
                        RemoteAcceptRequest(
                            sessionId = request.id,
                            canControl = RemoteControlAccessibilityService.isReady(context),
                        )
                    )
                }
                val active = accepted.session
                if (active != null) {
                    incoming = active
                    RemoteHelpService.start(
                        context,
                        active.id,
                        result.resultCode,
                        result.data!!,
                    )
                    message = null
                }
            } catch (failure: Exception) {
                message = failure.message ?: "Не удалось начать помощь"
                runCatching {
                    apiCall { container.api.remoteDecline(mapOf("session_id" to request.id)) }
                }
            } finally {
                busy = false
            }
        }
    }

    // Обновляем состояние службы управления при возврате из настроек.
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                controlEnabled = RemoteControlAccessibilityService.isEnabled(context)
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    // Опрос входящих запросов и состояния активной помощи.
    LaunchedEffect(Unit) {
        while (isActive) {
            if (!MainActivity.isInForeground) {
                delay(5_000)
                continue
            }
            val fresh = runCatching {
                apiCall { container.api.remoteIncoming() }
            }.getOrNull()?.session
            if (fresh == null) {
                if (incoming?.isActive == true) {
                    RemoteHelpService.stop(context)
                }
                incoming = null
            } else {
                if (fresh.isPending && fresh.id != dismissedId) {
                    incoming = fresh
                } else if (fresh.isActive) {
                    incoming = fresh
                } else if (fresh.status != "pending") {
                    incoming = null
                }
            }
            if (incoming?.isActive != true) {
                RemoteHelpService.stop(context)
            }
            delay(4_000)
        }
    }

    fun accept(request: RemoteSessionInfoDto) {
        if (busy) return
        busy = true
        message = null
        controlEnabled = RemoteControlAccessibilityService.isEnabled(context)
        val manager = context.getSystemService(Context.MEDIA_PROJECTION_SERVICE)
            as MediaProjectionManager
        pendingAccept = request
        busy = false
        runCatching { projectionLauncher.launch(manager.createScreenCaptureIntent()) }
            .onFailure {
                pendingAccept = null
                message = "Не удалось открыть запрос показа экрана"
            }
    }

    fun decline(request: RemoteSessionInfoDto) {
        if (busy) return
        busy = true
        scope.launch {
            runCatching {
                apiCall { container.api.remoteDecline(mapOf("session_id" to request.id)) }
            }
            incoming = null
            dismissedId = request.id
            busy = false
        }
    }

    val active = incoming?.takeIf { it.isActive }
    val pending = incoming?.takeIf { it.isPending && it.id != dismissedId }

    if (pending != null) {
        AlertDialog(
            onDismissRequest = {
                dismissedId = pending.id
                incoming = null
            },
            title = { Text("Родитель предлагает помощь") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "${pending.parentName} хочет подключиться к вашему экрану, " +
                            "чтобы помочь с заданиями или настройками."
                    )
                    Text(
                        "Вы увидите уведомление «Родитель смотрит ваш экран» и сможете " +
                            "остановить помощь в любой момент.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Surface(
                        color = MaterialTheme.colorScheme.surfaceVariant,
                        shape = RoundedCornerShape(10.dp),
                    ) {
                        Column(Modifier.padding(10.dp)) {
                            Text(
                                if (controlEnabled) {
                                    "Управление включено: родитель сможет нажимать за вас."
                                } else {
                                    "Управление выключено: родитель только увидит экран."
                                },
                                style = MaterialTheme.typography.bodySmall,
                                fontWeight = FontWeight.Medium,
                            )
                            if (!controlEnabled) {
                                TextButton(
                                    onClick = {
                                        RemoteControlAccessibilityService.openSettings(context)
                                    },
                                ) { Text("Включить управление") }
                            }
                        }
                    }
                    TextButton(
                        onClick = { decline(pending) },
                        enabled = !busy,
                    ) { Text("Отклонить запрос") }
                }
            },
            confirmButton = {
                Button(
                    onClick = { accept(pending) },
                    enabled = !busy,
                ) { Text(if (busy) "Открываем…" else "Разрешить") }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        dismissedId = pending.id
                        incoming = null
                    },
                ) { Text("Позже") }
            },
        )
    }

    if (message != null) {
        AlertDialog(
            onDismissRequest = { message = null },
            title = { Text("Удалённая помощь") },
            text = { Text(message!!) },
            confirmButton = {
                TextButton(onClick = { message = null }) { Text("Понятно") }
            },
        )
    }

    if (active != null) {
        Box(Modifier.fillMaxSize()) {
            Surface(
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .padding(top = 44.dp, start = 12.dp, end = 12.dp),
                color = MaterialTheme.colorScheme.errorContainer,
                shape = RoundedCornerShape(14.dp),
                shadowElevation = 6.dp,
            ) {
                Row(
                    Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text("🔴")
                    Spacer(Modifier.width(8.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            "Родитель смотрит ваш экран",
                            style = MaterialTheme.typography.labelLarge,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            if (active.canControl) "С управлением" else "Только просмотр",
                            style = MaterialTheme.typography.labelSmall,
                        )
                    }
                    TextButton(
                        onClick = {
                            scope.launch {
                                runCatching {
                                    apiCall {
                                        container.api.remoteStop(
                                            mapOf("session_id" to active.id)
                                        )
                                    }
                                }
                                RemoteHelpService.stop(context)
                                incoming = null
                            }
                        },
                    ) { Text("Остановить") }
                }
            }
        }
    }

    if (busy && pending == null) {
        // Небольшой индикатор, пока готовим показ экрана.
        Box(Modifier.fillMaxSize(), contentAlignment = Alignment.BottomCenter) {
            Row(
                Modifier
                    .padding(bottom = 60.dp)
                    .padding(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                Spacer(Modifier.width(8.dp))
                Text("Готовим помощь…", style = MaterialTheme.typography.labelMedium)
            }
        }
    }
}
