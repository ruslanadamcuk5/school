package com.edumath.uchus.ui.parent

import androidx.compose.foundation.clickable
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
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.AdminTopicDto
import com.edumath.uchus.data.api.ChildDto
import com.edumath.uchus.data.api.CreateAssignmentRequest
import com.edumath.uchus.data.api.SubjectDto
import com.edumath.uchus.data.api.UpdateChildRequest
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.EmptyBox
import com.edumath.uchus.ui.common.ErrorBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.KeyValue
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.LoadingBox
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.StatsRow
import com.edumath.uchus.ui.common.Tag
import com.edumath.uchus.ui.common.rememberTopicPickerState
import com.edumath.uchus.ui.common.topicPicker
import com.edumath.uchus.ui.teacher.starsText
import kotlinx.coroutines.launch

@Composable
fun ParentScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onChild: (Int) -> Unit,
    onAssignments: () -> Unit,
    onLibrary: () -> Unit,
    onCreate: () -> Unit,
    onMap: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var tick by remember { mutableStateOf(0) }
    var code by remember { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    ScreenScaffold(title = "Кабинет родителя", onBack = onBack) { padding ->
        Load(key = "parent-dashboard:$tick", block = { container.api.parentDashboard() }) { data, refresh ->
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item {
                    StatsRow(
                        "дети" to "${data.stats.children}",
                        "звёзды" to "${data.stats.stars}",
                        "попытки" to "${data.stats.attempts}",
                    )
                }

                item {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = onAssignments, modifier = Modifier.weight(1f)) {
                            Text("Задания")
                        }
                        OutlinedButton(onClick = onLibrary, modifier = Modifier.weight(1f)) {
                            Text("Библиотека")
                        }
                    }
                }

                item {
                    OutlinedButton(onClick = onCreate, modifier = Modifier.fillMaxWidth()) {
                        Text("Создать домашнее задание")
                    }
                }

                item {
                    OutlinedButton(onClick = onMap, modifier = Modifier.fillMaxWidth()) {
                        Text("🗺 Карта детей")
                    }
                }

                item { SectionTitle("Дети", trailing = "${data.children.size}") }

                if (data.children.isEmpty()) {
                    item { EmptyBox("Привяжите аккаунт ребёнка по коду.", "👨‍👩‍👧") }
                }

                items(data.children) { child ->
                    ChildCard(child) { onChild(child.learner?.id ?: 0) }
                }

                item { SectionTitle("Привязать ребёнка") }
                item {
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text(
                                "Код ребёнка показан в профиле ученика на сайте.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            OutlinedTextField(
                                value = code,
                                onValueChange = { code = it },
                                label = { Text("Код ребёнка") },
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth(),
                            )
                            Button(
                                onClick = {
                                    if (!busy && code.isNotBlank()) {
                                        busy = true
                                        scope.launch {
                                            runCatching {
                                                apiCall {
                                                    container.api.linkChild(mapOf("code" to code.trim()))
                                                }
                                            }
                                                .onSuccess {
                                                    message = "Ребёнок привязан"
                                                    code = ""
                                                    tick++
                                                    refresh()
                                                }
                                                .onFailure { message = it.message }
                                            busy = false
                                        }
                                    }
                                },
                                enabled = !busy && code.isNotBlank(),
                                modifier = Modifier.fillMaxWidth(),
                            ) { Text(if (busy) "Привязываем…" else "Привязать") }
                        }
                    }
                }

                if (message != null) {
                    item { InfoBox(message!!) }
                }

                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }
}

@Composable
private fun ChildCard(child: ChildDto, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(child.emoji, fontSize = 34.sp)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(child.displayName, fontWeight = FontWeight.SemiBold)
                Text(
                    child.classes.firstOrNull()?.displayTitle ?: "${child.grade} класс",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                val stats = child.stats
                if (stats != null) {
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Tag("ур. ${stats.level}")
                        Tag("${stats.xp} опыта")
                        if (child.grade in 1..4) Tag("${stats.stars} ★")
                    }
                }
            }
            Text("→", style = MaterialTheme.typography.titleMedium)
        }
    }
}

@Composable
fun ChildDetailScreen(
    container: AppContainer,
    learnerId: Int,
    onBack: () -> Unit,
    onMap: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var tick by remember { mutableStateOf(0) }
    var message by remember { mutableStateOf<String?>(null) }
    var editTarget by remember { mutableStateOf(false) }
    var editName by remember { mutableStateOf("") }
    var editGrade by remember { mutableStateOf(3) }
    var resetTarget by remember { mutableStateOf(false) }

    ScreenScaffold(title = "Ребёнок", onBack = onBack) { padding ->
        Load(key = "parent-child:$learnerId:$tick", block = { container.api.parentChild(learnerId) }) { data, refresh ->
            val playful = (data.learner?.grade ?: data.classes.firstOrNull()?.grade ?: 0) in 1..4
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(data.learner?.emoji ?: "🧒", fontSize = 40.sp)
                        Spacer(Modifier.width(12.dp))
                        Column(Modifier.weight(1f)) {
                            Text(
                                data.learner?.displayName ?: data.user?.displayName ?: "Ребёнок",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Bold,
                            )
                            Text(
                                data.classes.firstOrNull()?.displayTitle
                                    ?: "${data.learner?.grade ?: 0} класс",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }

                item {
                    if (playful) {
                        StatsRow(
                            "уровень" to "${data.stats?.level ?: 1}",
                            "опыт" to "${data.stats?.xp ?: 0}",
                            "монеты" to "${data.stats?.coins ?: 0}",
                            "серия" to "${data.stats?.streakDays ?: 0}",
                        )
                    } else {
                        StatsRow(
                            "уровень" to "${data.stats?.level ?: 1}",
                            "точность" to "${data.stats?.accuracy ?: 0}%",
                            "серия" to "${data.stats?.streakDays ?: 0}",
                        )
                    }
                }

                item {
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(14.dp)) {
                            KeyValue("Точность", "${data.stats?.accuracy ?: 0}%")
                            KeyValue("Попыток", "${data.stats?.totalAttempts ?: 0}")
                            KeyValue("Верных", "${data.stats?.totalCorrect ?: 0}")
                            if (playful) KeyValue("Звёзды", "${data.stats?.stars ?: 0}")
                        }
                    }
                }

                item {
                    OutlinedButton(onClick = onMap, modifier = Modifier.fillMaxWidth()) {
                        Text("🗺 Показать на карте")
                    }
                }

                item {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedButton(
                            onClick = {
                                editName = data.learner?.name
                                    ?: data.user?.displayName
                                    ?: ""
                                editGrade = data.learner?.grade
                                    ?: data.classes.firstOrNull()?.grade
                                    ?: 3
                                editTarget = true
                            },
                            modifier = Modifier.weight(1f),
                        ) { Text("Изменить") }
                        OutlinedButton(
                            onClick = { resetTarget = true },
                            modifier = Modifier.weight(1f),
                        ) { Text("Сбросить прогресс", color = MaterialTheme.colorScheme.error) }
                    }
                }

                if (message != null) {
                    item { InfoBox(message!!) }
                }

                item { SectionTitle("Активность за неделю") }
                item {
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            if (data.weekly.isEmpty()) {
                                Text(
                                    "Пока нет занятий за неделю.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            data.weekly.forEach { day ->
                                KeyValue(day.day, "${day.correct} из ${day.attempts}")
                            }
                        }
                    }
                }

                item { SectionTitle("Темы", trailing = "${data.topics.size}") }
                if (data.topics.isEmpty()) {
                    item { InfoBox("Прогресс по темам появится после занятий.") }
                }
                items(data.topics) { topic ->
                    Card(Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(topic.slug, modifier = Modifier.weight(1f))
                            if (playful) {
                                Text(starsText(topic.stars))
                                Spacer(Modifier.width(8.dp))
                            }
                            Tag("${topic.correct}/${topic.attempts}")
                        }
                    }
                }

                item { SectionTitle("Работы", trailing = "${data.results.size}") }
                if (data.results.isEmpty()) {
                    item { InfoBox("Работ пока нет.") }
                }
                items(data.results) { result ->
                    Card(Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(result.title ?: "Работа", fontWeight = FontWeight.Medium)
                                Text(
                                    result.completedAt ?: "",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            Tag("${result.score}/${result.maxScore}")
                        }
                    }
                }

                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }

    if (editTarget) {
        EditChildDialog(
            initialName = editName,
            initialGrade = editGrade,
            onDismiss = { editTarget = false },
            onSave = { name, grade ->
                scope.launch {
                    runCatching {
                        apiCall {
                            container.api.updateChild(
                                learnerId,
                                UpdateChildRequest(
                                    name = name.takeIf { it.isNotBlank() },
                                    grade = grade,
                                ),
                            )
                        }
                    }
                        .onSuccess {
                            message = "Профиль обновлён"
                            editTarget = false
                            tick++
                        }
                        .onFailure { message = it.message }
                }
            },
        )
    }

    if (resetTarget) {
        AlertDialog(
            onDismissRequest = { resetTarget = false },
            title = { Text("Сбросить прогресс?") },
            text = { Text("Будут удалены попытки, звёзды и награды ребёнка. Это действие необратимо.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        resetTarget = false
                        scope.launch {
                            runCatching {
                                apiCall { container.api.resetChild(learnerId, mapOf("confirm" to "yes")) }
                            }
                                .onSuccess { message = "Прогресс сброшен"; tick++ }
                                .onFailure { message = it.message }
                        }
                    },
                ) { Text("Сбросить") }
            },
            dismissButton = { TextButton(onClick = { resetTarget = false }) { Text("Отмена") } },
        )
    }
}

@Composable
private fun EditChildDialog(
    initialName: String,
    initialGrade: Int,
    onDismiss: () -> Unit,
    onSave: (String, Int) -> Unit,
) {
    var name by remember { mutableStateOf(initialName) }
    var grade by remember { mutableStateOf(initialGrade) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Профиль ребёнка") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Имя") },
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
            }
        },
        confirmButton = { TextButton(onClick = { onSave(name, grade) }) { Text("Сохранить") } },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Отмена") } },
    )
}

@Composable
fun ParentCreateAssignmentScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onCreated: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var children by remember { mutableStateOf<List<ChildDto>>(emptyList()) }
    var topics by remember { mutableStateOf<List<AdminTopicDto>>(emptyList()) }
    var subjects by remember { mutableStateOf<List<SubjectDto>>(emptyList()) }
    var child by remember { mutableStateOf<ChildDto?>(null) }
    var title by remember { mutableStateOf("") }
    var questions by remember { mutableStateOf(10) }
    var kind by remember { mutableStateOf("домашняя") }
    var taskType by remember { mutableStateOf("test") }
    var description by remember { mutableStateOf("") }
    var referenceText by remember { mutableStateOf("") }
    var audioText by remember { mutableStateOf("") }
    var allowPhoto by remember { mutableStateOf(true) }
    var allowText by remember { mutableStateOf(true) }
    var busy by remember { mutableStateOf(false) }
    var loadingTopics by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val selectedTopics = remember { mutableStateListOf<String>() }
    val topicPickerState = rememberTopicPickerState(topics, subjects)

    LaunchedEffect(Unit) {
        runCatching { apiCall { container.api.parentChildren() } }
            .onSuccess {
                children = it.children
                child = it.children.firstOrNull()
            }
            .onFailure { error = it.message }
    }

    LaunchedEffect(child?.learner?.id) {
        val grade = child?.grade ?: return@LaunchedEffect
        loadingTopics = true
        selectedTopics.clear()
        topics = emptyList()
        subjects = emptyList()
        error = null
        runCatching { apiCall { container.api.topics(grade, null, null) } }
            .onSuccess {
                topics = it.topics
                subjects = it.subjects
            }
            .onFailure { error = it.message }
        loadingTopics = false
    }

    ScreenScaffold(title = "Новое задание", onBack = onBack) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (children.isEmpty()) {
                item { InfoBox("Сначала привяжите ребёнка в кабинете родителя.") }
            }

            item { SectionTitle("Ребёнок") }
            item {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(children) { item ->
                        FilterChip(
                            selected = child?.learner?.id == item.learner?.id,
                            onClick = { child = item },
                            label = { Text("${item.emoji} ${item.displayName}") },
                        )
                    }
                }
            }

            item {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("Название задания") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            item { SectionTitle("Тип") }
            item {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(listOf("домашняя", "проверочная", "самостоятельная")) { value ->
                        FilterChip(
                            selected = kind == value,
                            onClick = { kind = value },
                            label = { Text(value) },
                        )
                    }
                }
            }

            item { SectionTitle("Что должен сделать ребёнок") }
            item {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(
                        listOf(
                            "test" to "Тест",
                            "read" to "Чтение",
                            "dictation" to "Диктант",
                            "other" to "Задание",
                        )
                    ) { (value, label) ->
                        FilterChip(
                            selected = taskType == value,
                            onClick = { taskType = value },
                            label = { Text(label) },
                        )
                    }
                }
            }

            item {
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it },
                    label = {
                        Text(if (taskType == "other") "Задание для ребёнка" else "Инструкция")
                    },
                    minLines = 2,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            if (taskType == "dictation") {
                item {
                    OutlinedTextField(
                        value = referenceText,
                        onValueChange = { referenceText = it },
                        label = { Text("Текст диктанта (ребёнок не увидит)") },
                        minLines = 4,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }

            item {
                OutlinedTextField(
                    value = audioText,
                    onValueChange = { audioText = it },
                    label = { Text("Что озвучить (необязательно)") },
                    minLines = 2,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            item {
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    FilterChip(
                        selected = allowText,
                        onClick = { allowText = !allowText },
                        label = { Text("Ответ текстом") },
                    )
                    FilterChip(
                        selected = allowPhoto,
                        onClick = { allowPhoto = !allowPhoto },
                        label = { Text("Фото ответа") },
                    )
                }
            }

            if (child != null) {
                item { SectionTitle("Темы", trailing = "${selectedTopics.size} выбрано") }
                when {
                    loadingTopics -> item { LoadingBox() }
                    topics.isEmpty() -> item { InfoBox("Для класса ребёнка нет доступных тем.") }
                    else -> topicPicker(
                        state = topicPickerState,
                        selected = selectedTopics.toSet(),
                        onToggle = { slug ->
                            if (slug in selectedTopics) selectedTopics.remove(slug)
                            else selectedTopics.add(slug)
                        },
                    )
                }
            }

            if (taskType == "test") {
                item { SectionTitle("Вопросов") }
                item {
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        listOf(5, 10, 15).forEach { value ->
                            FilterChip(
                                selected = questions == value,
                                onClick = { questions = value },
                                label = { Text("$value") },
                            )
                        }
                    }
                }
            }

            if (error != null) {
                item { ErrorBox(error!!) }
            }

            item {
                val chosen = child
                val topicsRequired = taskType == "test" || taskType == "read"
                val canCreate = chosen != null &&
                    (!topicsRequired || selectedTopics.isNotEmpty()) &&
                    (taskType != "other" || description.isNotBlank()) &&
                    (taskType != "dictation" || referenceText.isNotBlank() || selectedTopics.isNotEmpty()) &&
                    (allowText || allowPhoto)
                Button(
                    onClick = {
                        val userId = chosen?.user?.id
                        if (userId != null && !busy) {
                            busy = true
                            scope.launch {
                                runCatching {
                                    apiCall {
                                        container.api.createParentAssignment(
                                            CreateAssignmentRequest(
                                                title = title.trim(),
                                                kind = kind,
                                                description = description.trim().ifBlank { null },
                                                taskType = taskType,
                                                referenceText = referenceText.trim().ifBlank { null },
                                                audioText = audioText.trim().ifBlank { null },
                                                allowPhoto = allowPhoto,
                                                allowText = allowText,
                                                topicSlugs = selectedTopics.toList(),
                                                questionsCount = questions,
                                                childIds = listOf(userId),
                                                status = "опубликована",
                                            )
                                        )
                                    }
                                }
                                    .onSuccess { onCreated() }
                                    .onFailure { error = it.message }
                                busy = false
                            }
                        }
                    },
                    enabled = !busy && canCreate,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(if (busy) "Создаём…" else "Создать задание") }
            }

            item { Spacer(Modifier.height(16.dp)) }
        }
    }
}

@Composable
fun ParentHomeworkScreen(
    container: AppContainer,
    onBack: () -> Unit,
) {
    ScreenScaffold(title = "Задания родителя", onBack = onBack) { padding ->
        Load(key = "parent-homework", block = { container.api.parentAssignments() }) { data, _ ->
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (data.assignments.isEmpty()) {
                    item { EmptyBox("Заданий пока нет. Создайте первое в кабинете.", "📝") }
                }
                items(data.assignments) { item ->
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    item.displayTitle,
                                    fontWeight = FontWeight.SemiBold,
                                    modifier = Modifier.weight(1f),
                                )
                                Tag(item.status ?: "—")
                            }
                            Text(
                                "${item.kind ?: ""} · ${item.questionsCount} заданий",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Text(
                                "Выполнили: ${item.results.size}",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }
}
