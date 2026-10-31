package com.edumath.uchus.ui.admin

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.AdminYoutubeDto
import com.edumath.uchus.data.api.SaveYoutubeRequest
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.KeyValue
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.StatsRow
import com.edumath.uchus.ui.common.Tag
import kotlinx.coroutines.launch

/**
 * Админ-раздел YouTube: те же настройки и действия, что на сайте
 * (`/admin/youtube`), но через JSON API v1 и Bearer-токен приложения.
 */
@Composable
internal fun AdminYoutubeTab(container: AppContainer) {
    val scope = rememberCoroutineScope()
    var tick by remember { mutableIntStateOf(0) }
    var message by remember { mutableStateOf<String?>(null) }
    var searchInput by remember { mutableStateOf("") }
    var search by remember { mutableStateOf("") }
    var busyAction by remember { mutableStateOf<String?>(null) }

    var loadedOnce by remember { mutableStateOf(false) }
    var enabled by remember { mutableStateOf(false) }
    var apiKey by remember { mutableStateOf("") }
    var clearKey by remember { mutableStateOf(false) }
    var regionCode by remember { mutableStateOf("BY") }
    var language by remember { mutableStateOf("ru") }
    var maxPerTopic by remember { mutableStateOf("3") }
    var cacheDays by remember { mutableStateOf("14") }
    var minDuration by remember { mutableStateOf("60") }
    var maxDuration by remember { mutableStateOf("3600") }
    var aiRanking by remember { mutableStateOf(true) }

    var testing by remember { mutableStateOf(false) }
    var testMessage by remember { mutableStateOf<String?>(null) }
    var warmLimit by remember { mutableStateOf("5") }

    var showTopicDialog by remember { mutableStateOf(false) }
    var manualTopicSlug by remember { mutableStateOf("") }
    var manualTopicTitle by remember { mutableStateOf("") }
    var manualUrl by remember { mutableStateOf("") }

    fun runAction(label: String, block: suspend () -> String?) {
        if (busyAction != null) return
        busyAction = label
        message = null
        scope.launch {
            runCatching { block() }
                .onSuccess { text ->
                    if (!text.isNullOrBlank()) message = text
                    tick++
                }
                .onFailure { message = it.message }
            busyAction = null
        }
    }

    Load(
        key = "admin-youtube:$search:$tick",
        block = { container.api.adminYoutube(search.ifBlank { null }) },
    ) { data, _ ->
        LaunchedEffect(data) {
            if (!loadedOnce) {
                enabled = data.settings.enabled
                regionCode = data.settings.regionCode
                language = data.settings.relevanceLanguage
                maxPerTopic = data.settings.maxPerTopic.toString()
                cacheDays = data.settings.cacheDays.toString()
                minDuration = data.settings.minDuration.toString()
                maxDuration = data.settings.maxDuration.toString()
                aiRanking = data.settings.aiRanking
                loadedOnce = true
            }
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                "▶ YouTube",
                                fontWeight = FontWeight.Bold,
                                modifier = Modifier.weight(1f),
                            )
                            Tag(if (data.status.enabled) "подключён" else "выключен")
                        }
                        Text(
                            "К каждой теме автоматически подбираются обучающие видео. " +
                                "Ключ хранится только на сервере и не передаётся в приложение.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("Включить видео по темам", modifier = Modifier.weight(1f))
                            Switch(checked = enabled, onCheckedChange = { enabled = it })
                        }
                    }
                }
            }

            item {
                OutlinedTextField(
                    value = apiKey,
                    onValueChange = {
                        apiKey = it
                        if (it.isNotBlank()) clearKey = false
                    },
                    label = {
                        Text(
                            if (data.settings.hasKey) {
                                "Ключ YouTube Data API v3 (сохранён — оставьте пустым)"
                            } else {
                                "Ключ YouTube Data API v3"
                            }
                        )
                    },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            if (data.settings.hasKey) {
                item {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            "Удалить сохранённый ключ",
                            modifier = Modifier.weight(1f),
                            style = MaterialTheme.typography.bodySmall,
                        )
                        Switch(checked = clearKey, onCheckedChange = { clearKey = it })
                    }
                }
            }

            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = regionCode,
                        onValueChange = { regionCode = it.uppercase().take(2) },
                        label = { Text("Регион") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = maxPerTopic,
                        onValueChange = { maxPerTopic = it.filter(Char::isDigit).take(1) },
                        label = { Text("Видео на тему") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = cacheDays,
                        onValueChange = { cacheDays = it.filter(Char::isDigit).take(2) },
                        label = { Text("Кэш, дн.") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                }
            }

            item {
                Text("Язык поиска", style = MaterialTheme.typography.labelLarge)
                LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(listOf("ru" to "Русский", "be" to "Белорусский", "en" to "Английский")) { pair ->
                        FilterChip(
                            selected = language == pair.first,
                            onClick = { language = pair.first },
                            label = { Text(pair.second) },
                        )
                    }
                }
            }

            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = minDuration,
                        onValueChange = { minDuration = it.filter(Char::isDigit).take(4) },
                        label = { Text("Мин., сек") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = maxDuration,
                        onValueChange = { maxDuration = it.filter(Char::isDigit).take(4) },
                        label = { Text("Макс., сек") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                }
            }

            item {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text("Использовать ИИ для выбора", fontWeight = FontWeight.Medium)
                        Text(
                            "ИИ ранжирует только реальные ролики из выдачи YouTube.",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Switch(checked = aiRanking, onCheckedChange = { aiRanking = it })
                }
            }

            item {
                Button(
                    onClick = {
                        runAction("save") {
                            val result = apiCall {
                                container.api.saveYoutube(
                                    SaveYoutubeRequest(
                                        enabled = enabled,
                                        apiKey = apiKey.trim().ifBlank { null },
                                        keepKey = apiKey.isBlank() && !clearKey,
                                        clearKey = clearKey,
                                        regionCode = regionCode.trim().ifBlank { "BY" },
                                        relevanceLanguage = language,
                                        maxPerTopic = maxPerTopic.toIntOrNull() ?: 3,
                                        minDuration = minDuration.toIntOrNull() ?: 60,
                                        maxDuration = maxDuration.toIntOrNull() ?: 3600,
                                        cacheDays = cacheDays.toIntOrNull() ?: 14,
                                        aiRanking = aiRanking,
                                    )
                                )
                            }
                            apiKey = ""
                            clearKey = false
                            result.message ?: "Настройки YouTube сохранены"
                        }
                    },
                    enabled = busyAction == null,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(if (busyAction == "save") "Сохранение…" else "💾 Сохранить настройки") }
            }

            item {
                OutlinedButton(
                    onClick = {
                        if (!testing) {
                            testing = true
                            testMessage = null
                            scope.launch {
                                runCatching { apiCall { container.api.adminYoutubeTest() } }
                                    .onSuccess { result ->
                                        testMessage = if (result.ok) {
                                            "YouTube API работает ✅ ${result.message ?: ""}"
                                        } else {
                                            "Не удалось подключиться: ${result.message ?: "неизвестная ошибка"}"
                                        }
                                    }
                                    .onFailure { testMessage = it.message }
                                testing = false
                            }
                        }
                    },
                    enabled = !testing,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(if (testing) "Проверка связи…" else "🔌 Проверить подключение") }
            }

            if (testMessage != null) {
                item { InfoBox(testMessage!!) }
            }
            if (message != null) {
                item { InfoBox(message!!) }
            }
            if (busyAction != null && busyAction != "save") {
                item { InfoBox("Выполняется действие «$busyAction»…") }
            }

            item { SectionTitle("Статистика") }
            item {
                StatsRow(
                    "тем с видео" to "${data.stats.withVideos}",
                    "в кэше" to "${data.stats.fresh}",
                    "авто" to "${data.stats.auto}",
                )
            }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp)) {
                        KeyValue("Всего тем", "${data.stats.topics}")
                        KeyValue("Ручных видео", "${data.stats.manual}")
                        KeyValue("Ошибок", "${data.stats.errors}")
                        data.stats.lastError?.error?.takeIf { it.isNotBlank() }?.let {
                            KeyValue("Последняя ошибка", it.take(90))
                        }
                    }
                }
            }

            item { SectionTitle("Подбор и кэш") }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(
                            "Один поиск стоит около 100 units из дневной квоты 10 000, " +
                                "поэтому за запуск обрабатывается не больше ${data.limits.warm} тем.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            OutlinedTextField(
                                value = warmLimit,
                                onValueChange = { warmLimit = it.filter(Char::isDigit).take(1) },
                                label = { Text("Тем за запуск") },
                                singleLine = true,
                                modifier = Modifier.width(140.dp),
                            )
                            Spacer(Modifier.width(10.dp))
                            Button(
                                onClick = {
                                    val limit = (warmLimit.toIntOrNull() ?: 5)
                                        .coerceIn(1, data.limits.warm)
                                    runAction("warm") {
                                        val result = apiCall {
                                            container.api.adminYoutubeWarm(mapOf("limit" to limit))
                                        }
                                        val lines = mutableListOf(result.message ?: "Готово")
                                        result.results.forEach { item ->
                                            lines += if (item.error.isNotBlank()) {
                                                "• ${item.slug}: ошибка — ${item.error}"
                                            } else {
                                                "• ${item.slug}: подобрано ${item.count}"
                                            }
                                        }
                                        if (result.stopped.isNotBlank()) {
                                            lines += "Остановлено: ${result.stopped}"
                                        }
                                        lines.joinToString("\n")
                                    }
                                },
                                enabled = busyAction == null,
                            ) { Text(if (busyAction == "warm") "Подбираем…" else "Подобрать") }
                        }
                        OutlinedButton(
                            onClick = {
                                runAction("clear") {
                                    val result = apiCall { container.api.adminYoutubeClearCache() }
                                    result.message ?: "Кэш очищен"
                                }
                            },
                            enabled = busyAction == null,
                        ) { Text("🗑 Очистить кэш видео") }
                    }
                }
            }

            item { SectionTitle("Ручные видео") }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(
                            "Ручная ссылка показывается первой и не удаляется при очистке кэша.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        OutlinedButton(
                            onClick = { showTopicDialog = true },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(
                                if (manualTopicSlug.isBlank()) {
                                    "Выбрать тему"
                                } else {
                                    "Тема: $manualTopicTitle"
                                }
                            )
                        }
                        OutlinedTextField(
                            value = manualUrl,
                            onValueChange = { manualUrl = it },
                            label = { Text("Ссылка на YouTube") },
                            placeholder = { Text("https://youtu.be/…") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Button(
                            onClick = {
                                if (manualTopicSlug.isBlank()) {
                                    message = "Сначала выберите тему"
                                } else if (manualUrl.isBlank()) {
                                    message = "Вставьте ссылку на YouTube"
                                } else {
                                    runAction("manual") {
                                        val result = apiCall {
                                            container.api.adminYoutubeAddManual(
                                                mapOf(
                                                    "slug" to manualTopicSlug,
                                                    "video_url" to manualUrl.trim(),
                                                )
                                            )
                                        }
                                        manualUrl = ""
                                        result.message ?: "Видео добавлено"
                                    }
                                }
                            },
                            enabled = busyAction == null,
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text(if (busyAction == "manual") "Добавляем…" else "＋ Добавить видео") }
                    }
                }
            }

            if (data.manual.isEmpty()) {
                item { InfoBox("Ручных видео пока нет.") }
            }
            items(data.manual, key = { "manual-${it.id}" }) { video ->
                Card(Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(
                                video.title?.takeIf { it.isNotBlank() } ?: "Видео",
                                fontWeight = FontWeight.Medium,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis,
                            )
                            Text(
                                listOfNotNull(
                                    video.topicTitle ?: video.topicSlug,
                                    video.channel?.takeIf { it.isNotBlank() },
                                ).joinToString(" · "),
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        TextButton(
                            onClick = {
                                runAction("delete-${video.id}") {
                                    val result = apiCall {
                                        container.api.adminYoutubeDeleteVideo(video.id)
                                    }
                                    result.message ?: "Ручная ссылка удалена"
                                }
                            },
                            enabled = busyAction == null,
                        ) { Text("Удалить", color = MaterialTheme.colorScheme.error) }
                    }
                }
            }

            item { SectionTitle("Темы", trailing = "Показано ${data.topics.size}") }
            item {
                Row(
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    OutlinedTextField(
                        value = searchInput,
                        onValueChange = { searchInput = it },
                        label = { Text("Поиск темы") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    Button(onClick = { search = searchInput.trim() }) { Text("Найти") }
                }
            }
            if (data.topics.isEmpty()) {
                item { InfoBox("Темы не найдены.") }
            }
            items(data.topics, key = { "topic-${it.slug}" }) { topic ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(
                                    "${topic.grade} класс · ${topic.title ?: topic.slug}",
                                    fontWeight = FontWeight.Medium,
                                )
                                Text(
                                    topic.subjectName?.takeIf { it.isNotBlank() } ?: "—",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            if (topic.fresh == 1) {
                                Tag("кэш")
                            } else if (topic.status == "error") {
                                Tag("ошибка")
                            }
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                buildString {
                                    append("Видео: ${topic.videos}")
                                    if (topic.manual > 0) append(" · ручных: ${topic.manual}")
                                    topic.checkedAt?.takeIf { it.isNotBlank() }?.let {
                                        append(" · ${it.take(16)}")
                                    }
                                },
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.weight(1f),
                            )
                            TextButton(
                                onClick = {
                                    runAction("refresh-${topic.slug}") {
                                        val result = apiCall {
                                            container.api.adminYoutubeRefreshTopic(
                                                mapOf("slug" to topic.slug)
                                            )
                                        }
                                        result.message ?: "Подобрано видео: ${result.count}"
                                    }
                                },
                                enabled = busyAction == null,
                            ) { Text(if (busyAction == "refresh-${topic.slug}") "…" else "Подобрать") }
                        }
                        topic.error?.takeIf { it.isNotBlank() }?.let {
                            Text(
                                it,
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.error,
                            )
                        }
                    }
                }
            }

            item { Spacer(Modifier.height(16.dp)) }
        }

        if (showTopicDialog) {
            TopicChoiceDialog(
                data = data,
                onDismiss = { showTopicDialog = false },
                onPick = { slug, title ->
                    manualTopicSlug = slug
                    manualTopicTitle = title
                    showTopicDialog = false
                },
            )
        }
    }
}

@Composable
private fun TopicChoiceDialog(
    data: AdminYoutubeDto,
    onDismiss: () -> Unit,
    onPick: (String, String) -> Unit,
) {
    var query by remember { mutableStateOf("") }
    val topics = data.topics.filter { topic ->
        query.isBlank() || (topic.title ?: "").contains(query, ignoreCase = true)
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Выберите тему") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    label = { Text("Поиск") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                LazyColumn(Modifier.heightIn(max = 360.dp)) {
                    items(topics, key = { "pick-${it.slug}" }) { topic ->
                        Column(
                            Modifier
                                .fillMaxWidth()
                                .clickable {
                                    onPick(topic.slug, "${topic.grade} класс · ${topic.title ?: topic.slug}")
                                }
                                .padding(vertical = 10.dp, horizontal = 4.dp),
                        ) {
                            Text(topic.title ?: topic.slug, fontWeight = FontWeight.Medium)
                            Text(
                                "${topic.grade} класс · ${topic.subjectName ?: "—"}",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                    if (topics.isEmpty()) {
                        item { InfoBox("Темы не найдены.") }
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("Отмена") }
        },
    )
}
