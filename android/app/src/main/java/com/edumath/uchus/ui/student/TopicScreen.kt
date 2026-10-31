package com.edumath.uchus.ui.student

import android.annotation.SuppressLint
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.BookLinkDto
import com.edumath.uchus.data.api.MethodDto
import com.edumath.uchus.data.api.TopicDetailDto
import com.edumath.uchus.data.api.TopicVideoDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.Speaker
import com.edumath.uchus.ui.common.Tag
import com.edumath.uchus.ui.common.plainAiText
import kotlinx.coroutines.launch

@Composable
fun TopicScreen(
    container: AppContainer,
    slug: String,
    onBack: () -> Unit,
    onPlay: (String, String) -> Unit,
    onQuiz: (String) -> Unit,
    onRead: (String) -> Unit,
    onBook: (Int, Int) -> Unit,
    onTopic: (String) -> Unit,
) {
    val scope = rememberCoroutineScope()
    val context = LocalContext.current
    val speaker = remember { Speaker(context) }
    var message by remember { mutableStateOf<String?>(null) }
    var aiEnabled by remember { mutableStateOf(false) }
    var explanation by remember { mutableStateOf<String?>(null) }
    var aiBusy by remember { mutableStateOf(false) }
    var aiError by remember { mutableStateOf<String?>(null) }
    var videosEnabled by remember { mutableStateOf(false) }
    var videos by remember { mutableStateOf<List<TopicVideoDto>>(emptyList()) }
    var videosBusy by remember { mutableStateOf(false) }
    var videosError by remember { mutableStateOf<String?>(null) }
    var selectedVideoId by remember { mutableStateOf<String?>(null) }

    DisposableEffect(Unit) {
        onDispose { speaker.shutdown() }
    }

    LaunchedEffect(slug) {
        aiEnabled = runCatching {
            apiCall { container.api.aiStatus() }.ai?.enabled == true
        }.getOrDefault(false)
    }

    LaunchedEffect(slug) {
        videosEnabled = false
        videos = emptyList()
        videosError = null
        selectedVideoId = null
        videosBusy = true
        runCatching { apiCall { container.api.topicVideos(slug) } }
            .onSuccess { data ->
                videosEnabled = data.youtubeEnabled
                videos = data.videos
                selectedVideoId = data.videos.firstOrNull()?.videoId
                videosError = data.error?.takeIf { it.isNotBlank() }
                    ?: data.message?.takeIf { it.isNotBlank() && data.videos.isEmpty() }
            }
            .onFailure {
                videosError = it.message ?: "Не удалось загрузить видео."
            }
        videosBusy = false
    }

    val explain: (Boolean) -> Unit = { refresh ->
        if (!aiBusy) {
            aiBusy = true
            aiError = null
            scope.launch {
                runCatching {
                    if (refresh) {
                        container.api.aiExplainRefresh(slug)
                    } else {
                        container.api.aiExplain(slug)
                    }
                }.onSuccess { data ->
                    val text = plainAiText(data.content.orEmpty())
                    if (text.isNotEmpty()) {
                        explanation = text
                        speaker.speak(text)
                    } else {
                        aiError = "ИИ не вернул объяснение. Попробуйте позже."
                    }
                }.onFailure {
                    aiError = it.message ?: "Не удалось получить объяснение."
                }
                aiBusy = false
            }
        }
    }

    ScreenScaffold(title = "Тема", onBack = onBack) { padding ->
        Load(
            key = "topic:$slug",
            block = { container.api.topic(slug) },
        ) { data, refresh ->
            LaunchedEffect(data) {
                // Сразу показываем видео из ответа темы (кэш), не ожидая
                // отдельного запроса. Если кэш устарел, он обновится ниже.
                if (data.youtubeEnabled && videos.isEmpty()) {
                    videosEnabled = true
                    videos = data.videos
                    selectedVideoId = data.videos.firstOrNull()?.videoId
                }
            }
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item { TopicHeader(data) }

                if (message != null) {
                    item { InfoBox(message!!) }
                }

                if (data.canPlay) {
                    item {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            Button(
                                onClick = { onPlay(slug, "practice") },
                                modifier = Modifier.weight(1f),
                            ) { Text("Тренировка") }
                            OutlinedButton(
                                onClick = { onPlay(slug, "boss") },
                                modifier = Modifier.weight(1f),
                            ) { Text("Босс") }
                        }
                    }
                }

                if (data.canQuiz || data.canRead) {
                    item {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            if (data.canQuiz) {
                                Button(
                                    onClick = { onQuiz(slug) },
                                    modifier = Modifier.weight(1f),
                                ) { Text("Тест по теме") }
                            }
                            if (data.canRead) {
                                OutlinedButton(
                                    onClick = { onRead(slug) },
                                    modifier = Modifier.weight(1f),
                                ) { Text("Читать") }
                            }
                        }
                    }
                }

                if (aiEnabled) {
                    item {
                        AiExplainCard(
                            explanation = explanation,
                            busy = aiBusy,
                            error = aiError,
                            speaking = speaker.speaking,
                            speechError = speaker.error,
                            onExplain = { explain(false) },
                            onRefresh = { explain(true) },
                            onSpeak = { explanation?.let { speaker.speak(it) } },
                            onStop = { speaker.stop() },
                        )
                    }
                }

                if (videosEnabled && (videos.isNotEmpty() || videosBusy || videosError != null)) {
                    item {
                        TopicVideosCard(
                            videos = videos,
                            selectedId = selectedVideoId,
                            busy = videosBusy,
                            error = videosError,
                            onSelect = { selectedVideoId = it },
                        )
                    }
                }

                if (data.canRead) {
                    item {
                        Button(
                            onClick = {
                                scope.launch {
                                    runCatching { apiCall { container.api.markRead(slug) } }
                                        .onSuccess {
                                            message = "Тема отмечена как прочитанная."
                                            refresh()
                                        }
                                        .onFailure { message = it.message }
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text("Отметить прочитанным") }
                    }
                }

                if (data.methods.isNotEmpty()) {
                    item { SectionTitle("Способы решения") }
                    items(data.methods) { method -> MethodCard(method) }
                }

                if (data.books.isNotEmpty()) {
                    item { SectionTitle("В учебнике") }
                    items(data.books) { book ->
                        BookRow(book) { onBook(book.id, book.page ?: 1) }
                    }
                }

                if (data.previous != null || data.next != null) {
                    item {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            data.previous?.let { previous ->
                                OutlinedButton(
                                    onClick = { onTopic(previous.slug) },
                                    modifier = Modifier.weight(1f),
                                ) { Text("← ${previous.displayTitle.take(14)}") }
                            }
                            data.next?.let { next ->
                                OutlinedButton(
                                    onClick = { onTopic(next.slug) },
                                    modifier = Modifier.weight(1f),
                                ) { Text("${next.displayTitle.take(14)} →") }
                            }
                        }
                    }
                }

                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }
}

@Composable
private fun AiExplainCard(
    explanation: String?,
    busy: Boolean,
    error: String?,
    speaking: Boolean,
    speechError: String?,
    onExplain: () -> Unit,
    onRefresh: () -> Unit,
    onSpeak: () -> Unit,
    onStop: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(
            Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("🤖", fontSize = 22.sp)
                Spacer(Modifier.width(8.dp))
                Text("Объяснение с ИИ", fontWeight = FontWeight.SemiBold)
            }
            if (explanation == null) {
                Text(
                    "ИИ объяснит тему простыми словами и прочитает объяснение вслух.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Button(
                    onClick = onExplain,
                    enabled = !busy,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(if (busy) "Составляю объяснение…" else "Объяснить с ИИ") }
            } else {
                Text(explanation, style = MaterialTheme.typography.bodyMedium)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(
                        onClick = { if (speaking) onStop() else onSpeak() },
                        modifier = Modifier.weight(1f),
                    ) { Text(if (speaking) "Остановить" else "Озвучить") }
                    OutlinedButton(
                        onClick = onRefresh,
                        enabled = !busy,
                        modifier = Modifier.weight(1f),
                    ) { Text(if (busy) "…" else "Обновить") }
                }
                if (!speechError.isNullOrBlank()) {
                    Text(
                        speechError,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
            }
            if (!error.isNullOrBlank()) {
                Text(
                    error,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }
    }
}

@Composable
private fun TopicVideosCard(
    videos: List<TopicVideoDto>,
    selectedId: String?,
    busy: Boolean,
    error: String?,
    onSelect: (String) -> Unit,
) {
    val selected = videos.firstOrNull { it.videoId == selectedId } ?: videos.firstOrNull()
    Card(Modifier.fillMaxWidth()) {
        Column(
            Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("🎬", fontSize = 22.sp)
                Spacer(Modifier.width(8.dp))
                Text(
                    "Видео по теме",
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                Tag("YouTube")
            }
            if (selected != null) {
                key(selected.videoId) {
                    YouTubePlayer(
                        videoId = selected.videoId,
                        modifier = Modifier
                            .fillMaxWidth()
                            .aspectRatio(16f / 9f)
                            .clip(RoundedCornerShape(12.dp)),
                    )
                }
                Text(
                    selected.title ?: "Видео",
                    fontWeight = FontWeight.SemiBold,
                    style = MaterialTheme.typography.bodyMedium,
                )
                val meta = listOfNotNull(
                    selected.channel?.takeIf { it.isNotBlank() },
                    selected.durationLabel?.takeIf { it.isNotBlank() },
                ).joinToString(" · ")
                if (meta.isNotBlank()) {
                    Text(
                        meta,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            } else if (busy) {
                Text(
                    "Подбираем видео для этой темы…",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                Text(
                    "Видео по этой теме пока не найдены.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            videos.filter { it.videoId != selected?.videoId }.forEach { video ->
                VideoRow(video) { onSelect(video.videoId) }
            }

            if (!error.isNullOrBlank()) {
                Text(
                    error,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }
    }
}

@Composable
private fun VideoRow(video: TopicVideoDto, onClick: () -> Unit) {
    Card(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Row(
            Modifier.padding(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("▶", fontSize = 18.sp, color = MaterialTheme.colorScheme.primary)
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    video.title ?: "Видео",
                    fontWeight = FontWeight.SemiBold,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                val meta = listOfNotNull(
                    video.channel?.takeIf { it.isNotBlank() },
                    video.durationLabel?.takeIf { it.isNotBlank() },
                ).joinToString(" · ")
                if (meta.isNotBlank()) {
                    Text(
                        meta,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
private fun YouTubePlayer(videoId: String, modifier: Modifier = Modifier) {
    val safeId = videoId.filter { it.isLetterOrDigit() || it == '_' || it == '-' }.take(11)
    if (safeId.length != 11) return
    var webView by remember { mutableStateOf<WebView?>(null) }
    DisposableEffect(safeId) {
        onDispose {
            webView?.apply {
                stopLoading()
                loadUrl("about:blank")
                destroy()
            }
            webView = null
        }
    }
    AndroidView(
        modifier = modifier,
        factory = { context ->
            WebView(context).apply {
                setBackgroundColor(android.graphics.Color.BLACK)
                settings.javaScriptEnabled = true
                settings.domStorageEnabled = true
                settings.mediaPlaybackRequiresUserGesture = true
                settings.allowFileAccess = false
                settings.allowContentAccess = false
                settings.builtInZoomControls = false
                settings.displayZoomControls = false
                settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
                webViewClient = WebViewClient()
                webView = this
                tag = safeId
                loadVideo(safeId)
            }
        },
        update = { view ->
            if (view.tag != safeId) {
                view.tag = safeId
                view.loadVideo(safeId)
            }
        },
    )
}

private fun WebView.loadVideo(videoId: String) {
    val html = """
        <!DOCTYPE html>
        <html>
          <head>
            <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
            <style>
              html, body { margin:0; padding:0; height:100%; background:#000; overflow:hidden; }
              iframe { position:absolute; top:0; left:0; width:100%; height:100%; border:0; }
            </style>
          </head>
          <body>
            <iframe
              src="https://www.youtube-nocookie.com/embed/$videoId?rel=0&amp;playsinline=1"
              allow="accelerometer; encrypted-media; gyroscope; picture-in-picture; web-share"
              allowfullscreen></iframe>
          </body>
        </html>
    """.trimIndent()
    loadDataWithBaseURL("https://www.youtube-nocookie.com", html, "text/html", "UTF-8", null)
}

@Composable
private fun TopicHeader(data: TopicDetailDto) {
    val topic = data.topic
    val playful = (topic?.grade ?: 0) in 1..4
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(topic?.emoji ?: "⭐", fontSize = 40.sp)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        topic?.displayTitle ?: "Тема",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        if (playful) Tag(starsText(topic?.stars ?: 0))
                        Tag("${topic?.grade ?: 0} класс")
                        if (topic?.read == true) Tag("прочитано")
                    }
                }
            }
            if (!topic?.description.isNullOrBlank()) {
                Text(
                    topic?.description ?: "",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun MethodCard(method: MethodDto) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(method.icon ?: "💡", fontSize = 22.sp)
                Spacer(Modifier.width(8.dp))
                Text(
                    method.name ?: method.slug,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                if (method.mastered) Tag("освоен")
            }
            if (!method.explanation.isNullOrBlank()) {
                Text(
                    method.explanation ?: "",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (method.attempts > 0) {
                Text(
                    "попыток: ${method.attempts} · верно: ${method.correct}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun BookRow(book: BookLinkDto, onClick: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Row(
            Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text("📖", fontSize = 24.sp)
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(book.title ?: "Учебник", fontWeight = FontWeight.SemiBold)
                Text(
                    "стр. ${book.page ?: 1}" + (book.pageEnd?.let { "–$it" } ?: ""),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            OutlinedButton(onClick = onClick) { Text("Открыть") }
        }
    }
}
