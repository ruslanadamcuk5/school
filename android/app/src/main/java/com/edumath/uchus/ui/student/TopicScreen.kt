package com.edumath.uchus.ui.student

import android.annotation.SuppressLint
import android.content.Intent
import android.net.Uri
import android.webkit.CookieManager
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.FrameLayout
import androidx.activity.compose.BackHandler
import androidx.browser.customtabs.CustomTabsIntent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.key
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.webkit.WebViewCompat
import androidx.webkit.WebViewFeature
import coil.compose.AsyncImage
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.BookLinkDto
import com.edumath.uchus.data.api.MethodDto
import com.edumath.uchus.data.api.ReasoningVariantDto
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
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun TopicScreen(
    container: AppContainer,
    slug: String,
    onBack: () -> Unit,
    onPlay: (String, String) -> Unit,
    onQuest: (String) -> Unit,
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
    var reasoning by remember { mutableStateOf<List<ReasoningVariantDto>>(emptyList()) }
    var reasoningBusy by remember { mutableStateOf(false) }
    var reasoningError by remember { mutableStateOf<String?>(null) }
    var videosEnabled by remember { mutableStateOf(false) }
    var videos by remember { mutableStateOf<List<TopicVideoDto>>(emptyList()) }
    var videosBusy by remember { mutableStateOf(false) }
    var videosError by remember { mutableStateOf<String?>(null) }
    var selectedVideoId by remember { mutableStateOf<String?>(null) }
    var playingVideoId by remember { mutableStateOf<String?>(null) }

    DisposableEffect(Unit) {
        onDispose { speaker.shutdown() }
    }

    LaunchedEffect(slug) {
        aiEnabled = runCatching {
            apiCall { container.api.aiStatus() }.ai?.enabled == true
        }.getOrDefault(false)
    }

    LaunchedEffect(slug, aiEnabled) {
        if (!aiEnabled) return@LaunchedEffect
        reasoningBusy = true
        reasoningError = null
        runCatching { apiCall { container.api.aiReasoning(slug) } }
            .onSuccess { data ->
                reasoning = data.variants
                if (data.variants.isEmpty()) {
                    reasoningError = "ИИ не вернул варианты объяснения. Попробуйте позже."
                }
            }
            .onFailure {
                reasoningError = it.message ?: "Не удалось получить варианты объяснения."
            }
        reasoningBusy = false
    }

    val refreshReasoning: () -> Unit = {
        if (!reasoningBusy) {
            scope.launch {
                reasoningBusy = true
                reasoningError = null
                runCatching { apiCall { container.api.aiReasoningRefresh(slug) } }
                    .onSuccess { data ->
                        reasoning = data.variants
                        if (data.variants.isEmpty()) {
                            reasoningError = "ИИ не вернул варианты объяснения. Попробуйте позже."
                        }
                    }
                    .onFailure {
                        reasoningError = it.message ?: "Не удалось обновить варианты объяснения."
                    }
                reasoningBusy = false
            }
        }
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

    Box(Modifier.fillMaxSize()) {
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

                    if (data.canQuest || data.canPlay) {
                        item {
                            Button(
                                onClick = { onQuest(slug) },
                                modifier = Modifier.fillMaxWidth(),
                            ) { Text("🎮  3D-квест по теме") }
                        }
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
                            AiReasoningCard(
                                variants = reasoning,
                                busy = reasoningBusy,
                                error = reasoningError,
                                onRefresh = refreshReasoning,
                            )
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
                                serverBaseUrl = container.session.baseUrl,
                                onSelect = { selectedVideoId = it },
                                onWatch = { playingVideoId = it },
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

        playingVideoId?.let { id ->
            BackHandler { playingVideoId = null }
            var playerAttempt by remember(id) { mutableIntStateOf(0) }
            Box(
                Modifier
                    .fillMaxSize()
                    .background(Color.Black),
            ) {
                key(id, playerAttempt) {
                    YouTubePlayer(
                        videoId = id,
                        serverBaseUrl = container.session.baseUrl,
                        modifier = Modifier.fillMaxSize(),
                    )
                }
                IconButton(
                    onClick = { playerAttempt++ },
                    modifier = Modifier
                        .align(Alignment.TopStart)
                        .statusBarsPadding()
                        .padding(8.dp),
                ) {
                    Icon(
                        Icons.Default.Refresh,
                        contentDescription = "Перезагрузить видео",
                        tint = Color.White,
                    )
                }
                Row(
                    modifier = Modifier
                        .align(Alignment.TopEnd)
                        .statusBarsPadding()
                        .padding(8.dp),
                ) {
                    IconButton(
                        onClick = {
                            openInBrowser(
                                context,
                                "https://www.youtube.com/watch?v=$id",
                            )
                        },
                    ) {
                        Text("↗", color = Color.White, fontSize = 22.sp)
                    }
                    IconButton(onClick = { playingVideoId = null }) {
                        Icon(
                            Icons.Default.Close,
                            contentDescription = "Закрыть",
                            tint = Color.White,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun AiReasoningCard(
    variants: List<ReasoningVariantDto>,
    busy: Boolean,
    error: String?,
    onRefresh: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(
            Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("✨", fontSize = 20.sp)
                Spacer(Modifier.width(8.dp))
                Text(
                    "Как можно рассуждать",
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                if (variants.isNotEmpty()) Tag("ИИ")
            }
            when {
                busy && variants.isEmpty() -> {
                    Text(
                        "ИИ подбирает несколько вариантов объяснения…",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }

                !error.isNullOrBlank() && variants.isEmpty() -> {
                    Text(
                        error,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                    OutlinedButton(onClick = onRefresh, enabled = !busy) {
                        Text("Попробовать снова")
                    }
                }

                variants.isEmpty() -> {
                    Text(
                        "Для этой темы пока нет вариантов объяснения.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }

                else -> {
                    Text(
                        "Несколько разных подходов к одной теме. Выберите понятный.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    variants.forEachIndexed { index, variant ->
                        ReasoningVariantCard(index + 1, variant)
                    }
                    OutlinedButton(
                        onClick = onRefresh,
                        enabled = !busy,
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text(if (busy) "Обновляем…" else "Другие варианты") }
                }
            }
        }
    }
}

@Composable
private fun ReasoningVariantCard(number: Int, variant: ReasoningVariantDto) {
    Column(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(14.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.35f))
            .padding(12.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        Row(verticalAlignment = Alignment.Top) {
            Box(
                Modifier
                    .size(24.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primary),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    "$number",
                    color = MaterialTheme.colorScheme.onPrimary,
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                )
            }
            Spacer(Modifier.width(8.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    variant.title ?: "Вариант $number",
                    fontWeight = FontWeight.SemiBold,
                )
                if (!variant.idea.isNullOrBlank()) {
                    Text(
                        variant.idea,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
        variant.steps.forEachIndexed { index, step ->
            Row(verticalAlignment = Alignment.Top) {
                Text(
                    "${index + 1}.",
                    fontSize = 12.sp,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.primary,
                )
                Spacer(Modifier.width(6.dp))
                Text(step, style = MaterialTheme.typography.bodySmall)
            }
        }
        if (!variant.example.isNullOrBlank()) {
            Column(
                Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .background(MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.45f))
                    .padding(8.dp),
            ) {
                Text(
                    "Пример",
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                )
                Text(variant.example, style = MaterialTheme.typography.bodySmall)
            }
        }
        if (!variant.tip.isNullOrBlank()) {
            Text(
                "💡 ${variant.tip}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
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
                Text("Подробное объяснение с ИИ", fontWeight = FontWeight.SemiBold)
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
    serverBaseUrl: String,
    onSelect: (String) -> Unit,
    onWatch: (String) -> Unit,
) {
    val selected = videos.firstOrNull { it.videoId == selectedId } ?: videos.firstOrNull()
    val context = LocalContext.current
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
                // В списке показываем превью, а сам плеер открываем на весь
                // экран: WebView с видео внутри прокручиваемого списка на
                // части устройств отдаёт только звук, оставляя чёрный кадр.
                Box(
                    Modifier
                        .fillMaxWidth()
                        .aspectRatio(16f / 9f)
                        .clip(RoundedCornerShape(12.dp))
                        .background(Color.Black),
                ) {
                    AsyncImage(
                        model = "https://i.ytimg.com/vi/${selected.videoId}/hqdefault.jpg",
                        contentDescription = selected.title,
                        contentScale = ContentScale.Crop,
                        modifier = Modifier.fillMaxSize(),
                    )
                    Box(Modifier.fillMaxSize().background(Color(0x44000000)))
                    Button(
                        onClick = { onWatch(selected.videoId) },
                        modifier = Modifier.align(Alignment.Center),
                    ) {
                        Text("▶ Смотреть")
                    }
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
                Text(
                    "Нет изображения? Открыть в браузере",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.clickable {
                        openInBrowser(
                            context,
                            "https://www.youtube.com/watch?v=${selected.videoId}",
                        )
                    },
                )
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

/** Скрипт, который выполняется до загрузки плеера YouTube.
 *
 * На Android 15 у части устройств (особенно MediaTek Dimensity) ломается
 * аппаратное декодирование HEVC/AV1: звук идёт, а кадр остаётся чёрным.
 * Сообщаем плееру, что этих кодеков нет, — YouTube отдаёт H.264, который
 * декодируется везде с Android 5.
 */
private val youtubeCodecScript = """
    (function () {
      try {
        var blocked = /(hvc1|hev1|av01|vp09|vp9|vp08|vp8)/i;
        var isVideo = function (type) { return /^video\//i.test(type); };
        if (window.MediaSource && window.MediaSource.isTypeSupported) {
          var original = window.MediaSource.isTypeSupported.bind(window.MediaSource);
          window.MediaSource.isTypeSupported = function (type) {
            type = String(type || '');
            if (isVideo(type) && blocked.test(type)) { return false; }
            return original(type);
          };
        }
        var proto = window.HTMLMediaElement && window.HTMLMediaElement.prototype;
        if (proto && proto.canPlayType) {
          var canPlay = proto.canPlayType;
          proto.canPlayType = function (type) {
            type = String(type || '');
            if (isVideo(type) && blocked.test(type)) { return ''; }
            return canPlay.call(this, type);
          };
        }
      } catch (e) {}
    })();
""".trimIndent()

/** Открывает ролик во встроенном браузере (Chrome Custom Tabs).
 *
 * Запасной путь на случай, если WebView устройства не умеет показывать
 * видео: Chrome на любом Android воспроизводит ролик штатно.
 */
private fun openInBrowser(context: android.content.Context, url: String) {
    val opened = runCatching {
        CustomTabsIntent.Builder()
            .setShowTitle(true)
            .build()
            .launchUrl(context, Uri.parse(url))
        true
    }.getOrDefault(false)
    if (!opened) {
        runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }
    }
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
private fun YouTubePlayer(
    videoId: String,
    serverBaseUrl: String,
    modifier: Modifier = Modifier,
) {
    val safeId = videoId.filter { it.isLetterOrDigit() || it == '_' || it == '-' }.take(11)
    if (safeId.length != 11) return

    val context = LocalContext.current

    // Источник, от которого загружается плеер. Он же уходит в параметр origin
    // и в заголовок Referer — без согласованной пары YouTube показывает
    // «Ошибка 153» и чёрный экран.
    val origin = remember(serverBaseUrl) {
        runCatching {
            val uri = java.net.URI(serverBaseUrl.trim())
            buildString {
                append(uri.scheme ?: "https")
                append("://")
                append(uri.host ?: "virusadk.alwaysdata.net")
                if (uri.port > 0 && uri.port != 80 && uri.port != 443) {
                    append(':').append(uri.port)
                }
            }
        }.getOrDefault("https://virusadk.alwaysdata.net")
    }

    // Грузим страницу плеера напрямую, но с заголовком Referer: это
    // рекомендуемый Google способ для WebView. Раньше здесь был iframe на
    // своей странице — в WebView вложенный запрос оставался без Referer,
    // поэтому плеер не запускался.
    val embedUrl = remember(safeId, origin) {
        "https://www.youtube-nocookie.com/embed/$safeId" +
            "?autoplay=1&playsinline=1&rel=0&modestbranding=1&enablejsapi=1" +
            "&origin=" + Uri.encode(origin)
    }
    val referer = remember(origin) { "$origin/" }
    val watchUrl = remember(safeId) { "https://www.youtube.com/watch?v=$safeId" }

    var webView by remember { mutableStateOf<WebView?>(null) }
    var failed by remember(safeId) { mutableStateOf(false) }
    var loaded by remember(safeId) { mutableStateOf(false) }
    var attempt by remember(safeId) { mutableIntStateOf(0) }

    fun reload() {
        loaded = false
        failed = false
        attempt++
        webView?.loadUrl(embedUrl, mapOf("Referer" to referer))
    }

    // Страховка от бесконечного чёрного прямоугольника: если за 15 секунд
    // страница так и не загрузилась, показываем понятное сообщение и кнопки.
    LaunchedEffect(safeId, attempt) {
        delay(15_000)
        if (!loaded) failed = true
    }

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

    Box(modifier) {
        AndroidView(
            modifier = Modifier.fillMaxSize(),
            factory = { ctx ->
                // WebView живёт внутри FrameLayout: сюда же YouTube кладёт
                // «нативный» полноэкранный видеослой. Без этого вызова плеер
                // уводит видео в невидимый custom view — остаётся только звук.
                val frame = FrameLayout(ctx).apply {
                    setBackgroundColor(android.graphics.Color.BLACK)
                }
                val view = WebView(ctx).apply {
                    setBackgroundColor(android.graphics.Color.BLACK)
                    settings.javaScriptEnabled = true
                    settings.domStorageEnabled = true
                    settings.javaScriptCanOpenWindowsAutomatically = true
                    settings.mediaPlaybackRequiresUserGesture = false
                    settings.allowFileAccess = false
                    settings.allowContentAccess = false
                    settings.builtInZoomControls = false
                    settings.displayZoomControls = false
                    settings.useWideViewPort = true
                    settings.loadWithOverviewMode = true
                    settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
                    settings.cacheMode = WebSettings.LOAD_DEFAULT
                    settings.setSupportMultipleWindows(false)
                    // YouTube использует сторонние cookie для выбора потока и
                    // рекламных настроек. Без них плеер иногда отдаёт только звук.
                    CookieManager.getInstance().setAcceptThirdPartyCookies(this, true)
                    // Метка «wv» выдаёт встроенный WebView. Убираем её вместе с
                    // «Version/4.0», чтобы YouTube не включал для такого клиента
                    // ограниченный плеер.
                    settings.userAgentString = settings.userAgentString
                        .replace("; wv)", ")")
                        .replace(" Version/4.0", "")

                    // До загрузки страницы сообщаем плееру, что HEVC/AV1/VP9
                    // не поддерживаются: так YouTube выберет H.264.
                    if (WebViewFeature.isFeatureSupported(WebViewFeature.DOCUMENT_START_SCRIPT)) {
                        runCatching {
                            WebViewCompat.addDocumentStartJavaScript(
                                this,
                                youtubeCodecScript,
                                setOf(
                                    "https://www.youtube-nocookie.com",
                                    "https://www.youtube.com",
                                ),
                            )
                        }
                    }

                    webChromeClient = object : WebChromeClient() {
                        private var customView: android.view.View? = null

                        override fun onShowCustomView(
                            view: android.view.View,
                            callback: CustomViewCallback,
                        ) {
                            if (customView != null) {
                                callback.onCustomViewHidden()
                                return
                            }
                            customView = view
                            frame.addView(
                                view,
                                FrameLayout.LayoutParams(
                                    FrameLayout.LayoutParams.MATCH_PARENT,
                                    FrameLayout.LayoutParams.MATCH_PARENT,
                                ),
                            )
                            visibility = android.view.View.GONE
                        }

                        override fun onHideCustomView() {
                            val current = customView ?: return
                            frame.removeView(current)
                            customView = null
                            visibility = android.view.View.VISIBLE
                        }

                        override fun onConsoleMessage(
                            message: android.webkit.ConsoleMessage,
                        ): Boolean {
                            android.util.Log.d(
                                "YouTubePlayer",
                                "${message.messageLevel()}: ${message.message()}",
                            )
                            return true
                        }
                    }

                    webViewClient = object : WebViewClient() {
                        override fun onPageFinished(view: WebView?, url: String?) {
                            super.onPageFinished(view, url)
                            loaded = true
                        }

                        override fun onReceivedError(
                            view: WebView?,
                            request: android.webkit.WebResourceRequest?,
                            error: android.webkit.WebResourceError?,
                        ) {
                            super.onReceivedError(view, request, error)
                            if (request?.isForMainFrame == true) failed = true
                        }

                        override fun onReceivedHttpError(
                            view: WebView?,
                            request: android.webkit.WebResourceRequest?,
                            errorResponse: android.webkit.WebResourceResponse?,
                        ) {
                            super.onReceivedHttpError(view, request, errorResponse)
                            val code = errorResponse?.statusCode ?: 0
                            if (request?.isForMainFrame == true && code >= 400) failed = true
                        }
                    }

                    webView = this
                    loadUrl(embedUrl, mapOf("Referer" to referer))
                }
                frame.addView(
                    view,
                    FrameLayout.LayoutParams(
                        FrameLayout.LayoutParams.MATCH_PARENT,
                        FrameLayout.LayoutParams.MATCH_PARENT,
                    ),
                )
                frame.tag = safeId
                frame
            },
            update = { frame ->
                if (frame.tag != safeId) {
                    frame.tag = safeId
                    webView?.loadUrl(embedUrl, mapOf("Referer" to referer))
                }
            },
        )

        if (failed) {
            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .background(Color(0xE6000000))
                    .padding(12.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.Center,
            ) {
                Text(
                    "Видео не загрузилось",
                    color = Color.White,
                    fontWeight = FontWeight.SemiBold,
                    style = MaterialTheme.typography.bodyMedium,
                )
                Spacer(Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    OutlinedButton(onClick = { reload() }) {
                        Text("Повторить", color = Color.White)
                    }
                    OutlinedButton(
                        onClick = { openInBrowser(context, watchUrl) },
                    ) {
                        Text("В браузере", color = Color.White)
                    }
                }
            }
        }
    }
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
