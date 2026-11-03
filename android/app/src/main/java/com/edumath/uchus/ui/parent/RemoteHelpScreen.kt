package com.edumath.uchus.ui.parent

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
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
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.lifecycle.LifecycleEventObserver
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.RemoteCommandRequest
import com.edumath.uchus.data.api.RemoteSessionInfoDto
import com.edumath.uchus.data.api.RemoteStartRequest
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.ErrorBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.ScreenScaffold
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * Экран родителя «Удалённая помощь».
 *
 * Родитель видит экран телефона ребёнка и может нажимать прямо по картинке.
 * Ребёнок сам разрешает показ и в любой момент может остановить помощь.
 */
@Composable
fun RemoteHelpScreen(
    container: AppContainer,
    learnerId: Int,
    onBack: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val lifecycleOwner = LocalLifecycleOwner.current
    var session by remember { mutableStateOf<RemoteSessionInfoDto?>(null) }
    var frame by remember { mutableStateOf<androidx.compose.ui.graphics.ImageBitmap?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var starting by remember { mutableStateOf(true) }
    var notice by remember { mutableStateOf<String?>(null) }
    var stopping by remember { mutableStateOf(false) }

    fun startSession() {
        starting = true
        error = null
        notice = null
        scope.launch {
            try {
                val response = apiCall { container.api.remoteStart(RemoteStartRequest(learnerId = learnerId)) }
                session = response.session
            } catch (failure: Exception) {
                error = failure.message ?: "Не удалось начать помощь"
            } finally {
                starting = false
            }
        }
    }

    fun stopSession() {
        val id = session?.id ?: return
        stopping = true
        scope.launch {
            runCatching {
                apiCall { container.api.remoteStop(mapOf("session_id" to id)) }
            }
            stopping = false
        }
    }

    // Завершение при уходе с экрана: отдельная область, которая не отменяется
    // вместе с композицией.
    fun stopSilently() {
        val id = session?.id ?: return
        CoroutineScope(SupervisorJob() + Dispatchers.IO).launch {
            runCatching {
                apiCall { container.api.remoteStop(mapOf("session_id" to id)) }
            }
        }
    }

    fun send(kind: String, x: Float = 0f, y: Float = 0f, x2: Float = 0f, y2: Float = 0f) {
        val current = session ?: return
        if (!current.isActive) return
        scope.launch {
            runCatching {
                apiCall {
                    container.api.remoteCommand(
                        RemoteCommandRequest(
                            sessionId = current.id,
                            kind = kind,
                            x = x,
                            y = y,
                            x2 = x2,
                            y2 = y2,
                            durationMs = if (kind == "swipe") 260 else 0,
                        )
                    )
                }
            }.onFailure { failure ->
                notice = failure.message ?: "Команда не дошла до телефона ребёнка"
            }
        }
    }

    LaunchedEffect(learnerId) { startSession() }

    // Статус сессии: ждём разрешения ребёнка и замечаем завершение.
    LaunchedEffect(session?.id, session?.status) {
        val current = session ?: return@LaunchedEffect
        while (isActive && (current.isPending || current.isActive)) {
            delay(2_000)
            val fresh = runCatching {
                apiCall { container.api.remoteCurrent(learnerId) }
            }.getOrNull()?.session
            if (fresh != null) {
                if (fresh.status != session?.status) {
                    session = fresh
                } else if (fresh.hasFrame != session?.hasFrame ||
                    fresh.canControl != session?.canControl
                ) {
                    session = fresh
                }
            }
        }
    }

    // Кадры экрана во время активной сессии.
    LaunchedEffect(session?.id, session?.status) {
        val current = session ?: return@LaunchedEffect
        if (!current.isActive) return@LaunchedEffect
        while (isActive) {
            val body = runCatching {
                apiCall { container.api.remoteFrame(current.id) }
            }.getOrNull()
            if (body != null) {
                val bytes = runCatching { body.bytes() }.getOrNull()
                val bitmap = bytes?.let { data ->
                    withContext(Dispatchers.Default) {
                        runCatching {
                            BitmapFactory.decodeByteArray(data, 0, data.size)
                        }.getOrNull()
                    }
                }
                if (bitmap != null) {
                    frame = bitmap.asImageBitmap()
                }
            }
            delay(750)
        }
    }

    // Ушли с экрана или свернули приложение — сразу завершаем помощь.
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_STOP) {
                stopSilently()
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose {
            lifecycleOwner.lifecycle.removeObserver(observer)
            stopSilently()
        }
    }

    ScreenScaffold(title = "Удалённая помощь", onBack = { stopSilently(); onBack() }) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (starting) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(Modifier.size(22.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.width(10.dp))
                    Text("Отправляем запрос ребёнку…")
                }
            }

            if (error != null) {
                ErrorBox(error!!)
                Button(onClick = { startSession() }, modifier = Modifier.fillMaxWidth()) {
                    Text("Попробовать снова")
                }
            }

            val current = session
            if (!starting && error == null && current != null) {
                when (current.status) {
                    "pending" -> WaitingCard(
                        childName = current.childName,
                        onCancel = { stopSession() },
                        pendingStop = stopping,
                    )

                    "active" -> ActiveHelpCard(
                        session = current,
                        frame = frame,
                        notice = notice,
                        onTap = { x, y -> send("tap", x, y) },
                        onCommand = { kind -> send(kind) },
                        onSwipe = { up ->
                            if (up) {
                                send("swipe", 0.5f, 0.78f, 0.5f, 0.22f)
                            } else {
                                send("swipe", 0.5f, 0.30f, 0.5f, 0.82f)
                            }
                        },
                        onStop = { stopSession() },
                        stopping = stopping,
                    )

                    "ended", "expired", "declined" -> EndedCard(
                        session = current,
                        onRestart = { startSession() },
                    )

                    else -> InfoBox("Состояние: ${current.status}")
                }
            }
        }
    }
}

@Composable
private fun WaitingCard(
    childName: String,
    onCancel: () -> Unit,
    pendingStop: Boolean,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Запрос отправлен", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(
                "$childName должен открыть приложение и нажать «Разрешить». " +
                    "После этого его экран появится здесь.",
            )
            Text(
                "Попросите ребёнка открыть «Школьник» и посмотреть на экран. " +
                    "Запрос действует две минуты.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp)
                Spacer(Modifier.width(10.dp))
                Text("Ждём разрешения…")
            }
            OutlinedButton(
                onClick = onCancel,
                enabled = !pendingStop,
                modifier = Modifier.fillMaxWidth(),
            ) { Text(if (pendingStop) "Отменяем…" else "Отменить запрос") }
        }
    }
}

@Composable
private fun ActiveHelpCard(
    session: RemoteSessionInfoDto,
    frame: androidx.compose.ui.graphics.ImageBitmap?,
    notice: String?,
    onTap: (Float, Float) -> Unit,
    onCommand: (String) -> Unit,
    onSwipe: (Boolean) -> Unit,
    onStop: () -> Unit,
    stopping: Boolean,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("🟢", modifier = Modifier.size(20.dp))
                Spacer(Modifier.width(8.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        "Экран: ${session.childName}",
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        if (session.canControl) {
                            "Можно нажимать на экран — действия выполнятся на телефоне ребёнка."
                        } else {
                            "Только просмотр: ребёнок не включил управление."
                        },
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            if (frame == null) {
                Box(
                    Modifier
                        .fillMaxWidth()
                        .height(220.dp),
                    contentAlignment = Alignment.Center,
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator()
                        Spacer(Modifier.height(8.dp))
                        Text("Ждём изображение с телефона…", textAlign = TextAlign.Center)
                    }
                }
            } else {
                Image(
                    bitmap = frame,
                    contentDescription = "Экран телефона ребёнка",
                    contentScale = ContentScale.Fit,
                    modifier = Modifier
                        .fillMaxWidth()
                        .aspectRatio(frame.width.toFloat() / frame.height.toFloat())
                        .pointerInput(session.id) {
                            detectTapGestures { offset ->
                                if (session.canControl && size.width > 0 && size.height > 0) {
                                    onTap(
                                        (offset.x / size.width).coerceIn(0f, 1f),
                                        (offset.y / size.height).coerceIn(0f, 1f),
                                    )
                                }
                            }
                        },
                )
            }

            if (notice != null) {
                InfoBox(notice)
            }

            Text(
                "Кнопки помощи",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                ControlButton("← Назад", session.canControl) { onCommand("back") }
                ControlButton("⌂ Домой", session.canControl) { onCommand("home") }
                ControlButton("⟲ Недавние", session.canControl) { onCommand("recents") }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                ControlButton("↑ Свайп вверх", session.canControl) { onSwipe(true) }
                ControlButton("↓ Свайп вниз", session.canControl) { onSwipe(false) }
                ControlButton("🔔 Шторка", session.canControl) { onCommand("notifications") }
            }

            Button(
                onClick = onStop,
                enabled = !stopping,
                modifier = Modifier.fillMaxWidth(),
                colors = androidx.compose.material3.ButtonDefaults.buttonColors(
                    containerColor = MaterialTheme.colorScheme.error,
                ),
            ) { Text(if (stopping) "Завершаем…" else "Завершить помощь") }

            Text(
                "Ребёнок видит уведомление «Родитель смотрит ваш экран» и может " +
                    "остановить помощь в любой момент.",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun RowScope.ControlButton(
    label: String,
    enabled: Boolean,
    onClick: () -> Unit,
) {
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 8.dp),
        modifier = Modifier.weight(1f),
    ) {
        Text(label, style = MaterialTheme.typography.labelMedium, textAlign = TextAlign.Center)
    }
}

@Composable
private fun EndedCard(
    session: RemoteSessionInfoDto,
    onRestart: () -> Unit,
) {
    Card(
        Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Помощь завершена", style = MaterialTheme.typography.titleMedium)
            Text(
                when (session.status) {
                    "declined" -> "Ребёнок не разрешил показ экрана."
                    "expired" -> "Запрос устарел: ребёнок не успел разрешить показ."
                    else -> "Сеанс закрыт."
                },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Button(onClick = onRestart, modifier = Modifier.fillMaxWidth()) {
                Text("Начать снова")
            }
        }
    }
}
