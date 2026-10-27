package com.edumath.uchus.ui.teacher

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
import com.edumath.uchus.data.api.AssignmentDto
import com.edumath.uchus.data.api.ClassDto
import com.edumath.uchus.data.api.CreateAssignmentRequest
import com.edumath.uchus.data.api.SubjectDto
import com.edumath.uchus.data.api.TeacherResultRowDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.EmptyBox
import com.edumath.uchus.ui.common.ErrorBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.LoadingBox
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.Tag
import com.edumath.uchus.ui.common.rememberTopicPickerState
import com.edumath.uchus.ui.common.topicPicker
import kotlinx.coroutines.launch

@Composable
fun TeacherAssignmentsScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onResults: (Int) -> Unit,
    onCreate: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var message by remember { mutableStateOf<String?>(null) }
    var deleteTarget by remember { mutableStateOf<AssignmentDto?>(null) }

    ScreenScaffold(title = "Работы", onBack = onBack) { padding ->
        Load(key = "teacher-assignments", block = { container.api.teacherAssignments() }) { data, refresh ->
            Column(
                Modifier
                    .fillMaxSize()
                    .padding(padding),
            ) {
                Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                    Button(onClick = onCreate, modifier = Modifier.fillMaxWidth()) {
                        Text("Создать работу")
                    }
                }
                if (message != null) {
                    Column(Modifier.padding(horizontal = 16.dp)) {
                        InfoBox(message!!)
                    }
                }
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                ) {
                    if (data.assignments.isEmpty()) {
                        item { EmptyBox("Работ пока нет. Создайте первую.", "📝") }
                    }
                    items(data.assignments) { item ->
                        AssignmentManageCard(
                            item = item,
                            onResults = { onResults(item.id) },
                            onPublish = {
                                scope.launch {
                                    runCatching { apiCall { container.api.publishAssignment(item.id) } }
                                        .onSuccess { message = "Работа опубликована"; refresh() }
                                        .onFailure { message = it.message }
                                }
                            },
                            onClose = {
                                scope.launch {
                                    runCatching { apiCall { container.api.closeAssignment(item.id) } }
                                        .onSuccess { message = "Работа закрыта"; refresh() }
                                        .onFailure { message = it.message }
                                }
                            },
                            onDelete = { deleteTarget = item },
                        )
                    }
                    item { Spacer(Modifier.height(16.dp)) }
                }
            }
        }
    }

    val target = deleteTarget
    if (target != null) {
        AlertDialog(
            onDismissRequest = { deleteTarget = null },
            title = { Text("Удалить работу?") },
            text = { Text("«${target.displayTitle}» будет удалена вместе с результатами.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        deleteTarget = null
                        scope.launch {
                            runCatching { apiCall { container.api.deleteAssignment(target.id) } }
                                .onSuccess { message = "Работа удалена" }
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
private fun AssignmentManageCard(
    item: AssignmentDto,
    onResults: () -> Unit,
    onPublish: () -> Unit,
    onClose: () -> Unit,
    onDelete: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    item.displayTitle,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                Tag(item.status ?: "—")
            }
            Text(
                "${item.kind ?: ""} · ${item.questionsCount} заданий" +
                    (item.dueDate?.takeIf { it.isNotBlank() }?.let { " · до $it" } ?: ""),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                OutlinedButton(onClick = onResults) { Text("Результаты") }
                if (item.status == "черновик") {
                    OutlinedButton(onClick = onPublish) { Text("Опубликовать") }
                }
                if (item.status == "опубликована") {
                    OutlinedButton(onClick = onClose) { Text("Закрыть") }
                }
                TextButton(onClick = onDelete) { Text("Удалить", color = MaterialTheme.colorScheme.error) }
            }
        }
    }
}

@Composable
fun CreateAssignmentScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onCreated: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var classes by remember { mutableStateOf<List<ClassDto>>(emptyList()) }
    var topics by remember { mutableStateOf<List<AdminTopicDto>>(emptyList()) }
    var subjects by remember { mutableStateOf<List<SubjectDto>>(emptyList()) }
    var loadingClasses by remember { mutableStateOf(true) }
    var loadingTopics by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var title by remember { mutableStateOf("") }
    var kind by remember { mutableStateOf("проверочная") }
    var questions by remember { mutableStateOf(10) }
    var selectedClass by remember { mutableStateOf<ClassDto?>(null) }
    val selectedTopics = remember { mutableStateListOf<String>() }
    var busy by remember { mutableStateOf(false) }
    val topicPickerState = rememberTopicPickerState(topics, subjects)

    LaunchedEffect(Unit) {
        runCatching { apiCall { container.api.teacherClasses() } }
            .onSuccess { classes = it.classes }
            .onFailure { error = it.message }
        loadingClasses = false
    }

    LaunchedEffect(selectedClass?.grade) {
        val grade = selectedClass?.grade ?: return@LaunchedEffect
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

    ScreenScaffold(title = "Новая работа", onBack = onBack) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item {
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("Название работы") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            item { SectionTitle("Тип") }
            item {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    items(listOf("проверочная", "домашняя", "самостоятельная")) { value ->
                        FilterChip(
                            selected = kind == value,
                            onClick = { kind = value },
                            label = { Text(value) },
                        )
                    }
                }
            }

            item { SectionTitle("Класс", trailing = if (loadingClasses) "загрузка…" else "") }
            if (loadingClasses) {
                item { LoadingBox() }
            } else if (classes.isEmpty()) {
                item { InfoBox("У вас нет классов. Обратитесь к администратору.") }
            } else {
                item {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        items(classes) { klass ->
                            FilterChip(
                                selected = selectedClass?.id == klass.id,
                                onClick = { selectedClass = klass },
                                label = { Text(klass.displayTitle) },
                            )
                        }
                    }
                }
            }

            if (selectedClass != null) {
                item { SectionTitle("Темы", trailing = "${selectedTopics.size} выбрано") }
                if (loadingTopics) {
                    item { LoadingBox() }
                } else if (topics.isEmpty()) {
                    item { InfoBox("Для этого класса нет доступных тем.") }
                } else {
                    topicPicker(
                        state = topicPickerState,
                        selected = selectedTopics.toSet(),
                        onToggle = { slug ->
                            if (slug in selectedTopics) selectedTopics.remove(slug)
                            else selectedTopics.add(slug)
                        },
                    )
                }
            }

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

            if (error != null) {
                item { ErrorBox(error!!) }
            }

            item {
                val klass = selectedClass
                Button(
                    onClick = {
                        if (klass != null && !busy) {
                            busy = true
                            scope.launch {
                                runCatching {
                                    apiCall {
                                        container.api.createTeacherAssignment(
                                            CreateAssignmentRequest(
                                                title = title.trim(),
                                                kind = kind,
                                                classId = klass.id,
                                                topicSlugs = selectedTopics.toList(),
                                                questionsCount = questions,
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
                    enabled = !busy && title.isNotBlank() && klass != null && selectedTopics.isNotEmpty(),
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(if (busy) "Создаём…" else "Создать и опубликовать") }
            }

            item { Spacer(Modifier.height(16.dp)) }
        }
    }
}

@Composable
fun TeacherResultsScreen(
    container: AppContainer,
    assignmentId: Int,
    onBack: () -> Unit,
) {
    ScreenScaffold(title = "Результаты", onBack = onBack) { padding ->
        Load(
            key = "teacher-results:$assignmentId",
            block = { container.api.assignmentResults(assignmentId) },
        ) { data, _ ->
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                item {
                    Text(
                        data.assignment?.displayTitle ?: "Работа",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                    )
                }
                if (data.results.isEmpty()) {
                    item { EmptyBox("В классе ещё нет учеников или результатов.", "👥") }
                }
                items(data.results) { row -> ResultRow(row) }
                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }
}

@Composable
private fun ResultRow(row: TeacherResultRowDto) {
    val student = row.student
    Card(Modifier.fillMaxWidth()) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("👤", fontSize = 22.sp)
            Spacer(Modifier.width(8.dp))
            Text(
                listOfNotNull(student?.firstName, student?.lastName)
                    .joinToString(" ").ifBlank { student?.login ?: "Ученик" },
                modifier = Modifier.weight(1f),
                fontWeight = FontWeight.Medium,
            )
            val result = row.result
            if (result == null) {
                Tag("не сдал")
            } else {
                Text(
                    "${result.score}/${result.maxScore} · ${row.grade} б.",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }
    }
}
