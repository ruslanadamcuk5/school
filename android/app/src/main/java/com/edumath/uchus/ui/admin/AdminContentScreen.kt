package com.edumath.uchus.ui.admin

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
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
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.AdminTopicDto
import com.edumath.uchus.data.api.SaveAiRequest
import com.edumath.uchus.data.api.TextbookDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.EmptyBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.KeyValue
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.Tag
import kotlinx.coroutines.launch

@Composable
fun AdminTopicsTab(container: AppContainer) {
    val scope = rememberCoroutineScope()
    var tick by remember { mutableStateOf(0) }
    var subjectId by remember { mutableStateOf<Int?>(null) }
    var grade by remember { mutableStateOf<Int?>(null) }
    var searchInput by remember { mutableStateOf("") }
    var search by remember { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }
    var showCreate by remember { mutableStateOf(false) }
    var editTarget by remember { mutableStateOf<AdminTopicDto?>(null) }
    var deleteTarget by remember { mutableStateOf<AdminTopicDto?>(null) }

    Load(
        key = "admin-topics:$subjectId:$grade:$search:$tick",
        block = { container.api.adminTopics(subjectId, grade, search.ifBlank { null }) },
    ) { data, _ ->
        Column(Modifier.fillMaxSize()) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
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

            LazyRow(
                contentPadding = PaddingValues(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                item {
                    FilterChip(
                        selected = subjectId == null,
                        onClick = { subjectId = null },
                        label = { Text("все предметы") },
                    )
                }
                items(data.subjects) { subject ->
                    FilterChip(
                        selected = subjectId == subject.id,
                        onClick = { subjectId = subject.id },
                        label = { Text("${subject.icon ?: ""} ${subject.name ?: ""}") },
                    )
                }
            }

            LazyRow(
                contentPadding = PaddingValues(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                item {
                    FilterChip(
                        selected = grade == null,
                        onClick = { grade = null },
                        label = { Text("все классы") },
                    )
                }
                items((1..11).toList()) { value ->
                    FilterChip(
                        selected = grade == value,
                        onClick = { grade = value },
                        label = { Text("$value") },
                    )
                }
            }

            Row(Modifier.padding(16.dp)) {
                Button(onClick = { showCreate = true }, modifier = Modifier.fillMaxWidth()) {
                    Text("Добавить тему")
                }
            }

            if (message != null) {
                Column(Modifier.padding(horizontal = 16.dp)) { InfoBox(message!!) }
            }

            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (data.topics.isEmpty()) {
                    item { EmptyBox("Темы не найдены.", "📚") }
                }
                items(data.topics) { topic ->
                    Card(Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(topic.icon ?: "⭐", modifier = Modifier.width(28.dp))
                            Column(Modifier.weight(1f)) {
                                Text(topic.title ?: topic.slug, fontWeight = FontWeight.Medium)
                                Text(
                                    "${topic.slug} · ${topic.grade} кл. · ${topic.subjectName ?: ""}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            TextButton(onClick = { editTarget = topic }) { Text("Изм.") }
                            TextButton(onClick = { deleteTarget = topic }) {
                                Text("×", color = MaterialTheme.colorScheme.error)
                            }
                        }
                    }
                }
                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }

    if (showCreate) {
        val subjects = remember { mutableListOf<com.edumath.uchus.data.api.SubjectDto>() }
        var subject by remember { mutableStateOf<com.edumath.uchus.data.api.SubjectDto?>(null) }
        var title by remember { mutableStateOf("") }
        var grade by remember { mutableStateOf(5) }
        var icon by remember { mutableStateOf("📘") }
        var description by remember { mutableStateOf("") }
        LaunchedEffect(Unit) {
            runCatching { apiCall { container.api.meta() } }
                .onSuccess { meta ->
                    subjects.clear()
                    subjects.addAll(meta.subjects)
                    subject = meta.subjects.firstOrNull()
                }
        }
        AlertDialog(
            onDismissRequest = { showCreate = false },
            title = { Text("Новая тема") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Предмет", style = MaterialTheme.typography.labelLarge)
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        items(subjects) { item ->
                            FilterChip(
                                selected = subject?.id == item.id,
                                onClick = { subject = item },
                                label = { Text(item.name ?: "") },
                            )
                        }
                    }
                    OutlinedTextField(
                        value = title,
                        onValueChange = { title = it },
                        label = { Text("Название") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = icon,
                        onValueChange = { icon = it },
                        label = { Text("Значок") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    Text("Класс", style = MaterialTheme.typography.labelLarge)
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        items((1..11).toList()) { value ->
                            FilterChip(
                                selected = grade == value,
                                onClick = { grade = value },
                                label = { Text("$value") },
                            )
                        }
                    }
                    OutlinedTextField(
                        value = description,
                        onValueChange = { description = it },
                        label = { Text("Описание") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        val chosen = subject
                        if (chosen != null && title.isNotBlank()) {
                            scope.launch {
                                runCatching {
                                    apiCall {
                                        container.api.createTopic(
                                            mapOf(
                                                "subject_id" to chosen.id,
                                                "grade" to grade,
                                                "title" to title.trim(),
                                                "icon" to icon,
                                                "description" to description,
                                            )
                                        )
                                    }
                                }
                                    .onSuccess {
                                        message = "Тема создана"
                                        showCreate = false
                                        tick++
                                    }
                                    .onFailure { message = it.message }
                            }
                        }
                    },
                ) { Text("Создать") }
            },
            dismissButton = { TextButton(onClick = { showCreate = false }) { Text("Отмена") } },
        )
    }

    val editing = editTarget
    if (editing != null) {
        var title by remember(editing.slug) { mutableStateOf(editing.title ?: "") }
        var icon by remember(editing.slug) { mutableStateOf(editing.icon ?: "") }
        var description by remember(editing.slug) { mutableStateOf(editing.description ?: "") }
        AlertDialog(
            onDismissRequest = { editTarget = null },
            title = { Text("Тема ${editing.slug}") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = title,
                        onValueChange = { title = it },
                        label = { Text("Название") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = icon,
                        onValueChange = { icon = it },
                        label = { Text("Значок") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = description,
                        onValueChange = { description = it },
                        label = { Text("Описание") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        editTarget = null
                        scope.launch {
                            runCatching {
                                apiCall {
                                    container.api.updateTopic(
                                        editing.slug,
                                        mapOf(
                                            "title" to title,
                                            "icon" to icon,
                                            "description" to description,
                                        ),
                                    )
                                }
                            }
                                .onSuccess { message = "Тема обновлена"; tick++ }
                                .onFailure { message = it.message }
                        }
                    },
                ) { Text("Сохранить") }
            },
            dismissButton = { TextButton(onClick = { editTarget = null }) { Text("Отмена") } },
        )
    }

    val deleting = deleteTarget
    if (deleting != null) {
        AlertDialog(
            onDismissRequest = { deleteTarget = null },
            title = { Text("Удалить тему?") },
            text = { Text("Тема «${deleting.title ?: deleting.slug}» будет удалена.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        deleteTarget = null
                        scope.launch {
                            runCatching { apiCall { container.api.deleteTopic(deleting.slug) } }
                                .onSuccess { message = "Тема удалена"; tick++ }
                                .onFailure { message = it.message }
                        }
                    },
                ) { Text("Удалить") }
            },
            dismissButton = { TextButton(onClick = { deleteTarget = null }) { Text("Отмена") } },
        )
    }
}

@Composable
fun AdminTextbooksTab(container: AppContainer) {
    val scope = rememberCoroutineScope()
    var tick by remember { mutableStateOf(0) }
    var searchInput by remember { mutableStateOf("") }
    var search by remember { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }
    var deleteTarget by remember { mutableStateOf<TextbookDto?>(null) }

    Load(
        key = "admin-textbooks:$search:$tick",
        block = { container.api.adminTextbooks(null, null, search.ifBlank { null }) },
    ) { data, _ ->
        Column(Modifier.fillMaxSize()) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(
                    value = searchInput,
                    onValueChange = { searchInput = it },
                    label = { Text("Поиск пособия") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                Button(onClick = { search = searchInput.trim() }) { Text("Найти") }
            }

            if (message != null) {
                Column(Modifier.padding(horizontal = 16.dp)) { InfoBox(message!!) }
            }

            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (data.textbooks.isEmpty()) {
                    item { EmptyBox("Пособий нет.", "📄") }
                }
                items(data.textbooks) { textbook ->
                    Card(Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(
                                    textbook.title ?: "Пособие",
                                    fontWeight = FontWeight.Medium,
                                )
                                Text(
                                    listOfNotNull(
                                        textbook.author,
                                        "${textbook.grade} класс",
                                        "${textbook.pages} стр.",
                                    ).joinToString(" · "),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            TextButton(onClick = { deleteTarget = textbook }) {
                                Text("×", color = MaterialTheme.colorScheme.error)
                            }
                        }
                    }
                }
                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }

    val deleting = deleteTarget
    if (deleting != null) {
        AlertDialog(
            onDismissRequest = { deleteTarget = null },
            title = { Text("Удалить пособие?") },
            text = {
                Text(
                    "«${deleting.title ?: "Пособие"}» и связанные темы будут удалены. " +
                        "Книги в библиотеках могут стать недоступны."
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        deleteTarget = null
                        scope.launch {
                            runCatching { apiCall { container.api.deleteTextbook(deleting.id) } }
                                .onSuccess { message = "Пособие удалено"; tick++ }
                                .onFailure { message = it.message }
                        }
                    },
                ) { Text("Удалить") }
            },
            dismissButton = { TextButton(onClick = { deleteTarget = null }) { Text("Отмена") } },
        )
    }
}

@Composable
fun AdminAiTab(container: AppContainer) {
    val scope = rememberCoroutineScope()
    var tick by remember { mutableStateOf(0) }
    var message by remember { mutableStateOf<String?>(null) }
    var enabled by remember { mutableStateOf(false) }
    var provider by remember { mutableStateOf("openrouter") }
    var baseUrl by remember { mutableStateOf("") }
    var model by remember { mutableStateOf("") }
    var apiKey by remember { mutableStateOf("") }
    var systemNote by remember { mutableStateOf("") }
    var loadedOnce by remember { mutableStateOf(false) }
    var testing by remember { mutableStateOf(false) }
    var testMessage by remember { mutableStateOf<String?>(null) }

    Load(key = "admin-ai:$tick", block = { container.api.adminAi() }) { data, _ ->
        LaunchedEffect(data) {
            if (!loadedOnce) {
                enabled = data.settings.enabled
                provider = data.settings.provider ?: "openrouter"
                baseUrl = data.settings.baseUrl ?: ""
                model = data.settings.model ?: ""
                systemNote = data.settings.systemNote ?: ""
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
                                "ИИ включён",
                                modifier = Modifier.weight(1f),
                                fontWeight = FontWeight.SemiBold,
                            )
                            Switch(checked = enabled, onCheckedChange = { enabled = it })
                        }
                        Text(
                            "Пока ИИ не настроен и не включён, разделы ИИ скрыты в приложении и на сайте.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            item {
                Text("Провайдер", style = MaterialTheme.typography.labelLarge)
                LazyRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    items(data.providers) { item ->
                        FilterChip(
                            selected = provider == item.id,
                            onClick = {
                                provider = item.id
                                if (baseUrl.isBlank() || data.settings.provider != item.id) {
                                    baseUrl = item.baseUrl ?: ""
                                }
                                if (model.isBlank() && item.models.isNotEmpty()) {
                                    model = item.models.first()
                                }
                            },
                            label = { Text(item.name ?: item.id) },
                        )
                    }
                }
            }

            item {
                OutlinedTextField(
                    value = baseUrl,
                    onValueChange = { baseUrl = it },
                    label = { Text("Адрес API (base URL)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            item {
                OutlinedTextField(
                    value = model,
                    onValueChange = { model = it },
                    label = { Text("Модель") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            item {
                OutlinedTextField(
                    value = apiKey,
                    onValueChange = { apiKey = it },
                    label = {
                        Text(
                            if (data.settings.hasKey) {
                                "Ключ API (сохранён — оставьте пустым, чтобы не менять)"
                            } else {
                                "Ключ API"
                            }
                        )
                    },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            item {
                OutlinedTextField(
                    value = systemNote,
                    onValueChange = { systemNote = it },
                    label = { Text("Системная заметка (для стиля ответов)") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            item {
                Button(
                    onClick = {
                        scope.launch {
                            runCatching {
                                apiCall {
                                    container.api.saveAi(
                                        SaveAiRequest(
                                            enabled = enabled,
                                            provider = provider,
                                            baseUrl = baseUrl.trim().ifBlank { null },
                                            apiKey = apiKey.trim().ifBlank { null },
                                            keepKey = apiKey.isBlank(),
                                            model = model.trim().ifBlank { null },
                                            temperature = data.settings.temperature,
                                            maxTokens = data.settings.maxTokens,
                                            systemNote = systemNote.trim().ifBlank { null },
                                        )
                                    )
                                }
                            }
                                .onSuccess {
                                    message = "Настройки ИИ сохранены"
                                    apiKey = ""
                                    tick++
                                }
                                .onFailure { message = it.message }
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Сохранить") }
            }

            item {
                OutlinedButton(
                    onClick = {
                        if (!testing) {
                            testing = true
                            testMessage = null
                            scope.launch {
                                runCatching { apiCall { container.api.adminAiTest() } }
                                    .onSuccess { result ->
                                        testMessage = if (result.ok) {
                                            "Связь с моделью работает ✅ ${result.message ?: ""}"
                                        } else {
                                            "Не удалось связаться: ${result.message ?: "неизвестная ошибка"}"
                                        }
                                    }
                                    .onFailure { testMessage = it.message }
                                testing = false
                            }
                        }
                    },
                    enabled = !testing,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(if (testing) "Проверка связи…" else "Проверить связь с моделью") }
            }

            if (testMessage != null) {
                item { InfoBox(testMessage!!) }
            }

            if (message != null) {
                item { InfoBox(message!!) }
            }

            item { SectionTitle("Статистика") }
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp)) {
                        KeyValue("Всего запросов", "${data.stats.total}")
                        KeyValue("Успешно", "${data.stats.ok}")
                        KeyValue("Ошибок", "${data.stats.failed}")
                        KeyValue("Объяснений", "${data.stats.explanations}")
                        data.stats.lastError?.detail?.let { KeyValue("Последняя ошибка", it.take(80)) }
                    }
                }
            }

            item { SectionTitle("Последние запросы") }
            if (data.stats.recent.isEmpty()) {
                item { InfoBox("Запросов к ИИ ещё не было.") }
            }
            items(data.stats.recent) { entry ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text("${entry.kind ?: "запрос"} · ${if (entry.ok == 1) "ок" else "ошибка"}")
                        Text(
                            entry.detail ?: entry.createdAt ?: "",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            item { Spacer(Modifier.height(16.dp)) }
        }
    }
}

@Composable
fun AdminAuditTab(container: AppContainer) {
    Load(key = "admin-audit", block = { container.api.adminAudit(200) }) { data, _ ->
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (data.entries.isEmpty()) {
                item { EmptyBox("Журнал пуст.", "🗂") }
            }
            items(data.entries) { entry ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                "${entry.action ?: "?"} ${entry.entity ?: ""} ${entry.entityId ?: ""}",
                                modifier = Modifier.weight(1f),
                                fontWeight = FontWeight.Medium,
                            )
                            Tag(entry.createdAt?.take(10) ?: "—")
                        }
                        Text(
                            listOfNotNull(
                                entry.login,
                                listOfNotNull(entry.firstName, entry.lastName)
                                    .joinToString(" ").ifBlank { null },
                            ).joinToString(" · "),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        if (!entry.details.isNullOrBlank()) {
                            Text(
                                entry.details ?: "",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
            }
            item { Spacer(Modifier.height(16.dp)) }
        }
    }
}
