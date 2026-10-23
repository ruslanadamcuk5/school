package com.edumath.uchus.ui.student

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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.AssignmentDetailDto
import com.edumath.uchus.data.api.AssignmentDto
import com.edumath.uchus.data.api.QuestionDto
import com.edumath.uchus.data.api.ResultSummaryDto
import com.edumath.uchus.data.api.StepResultDto
import com.edumath.uchus.data.api.SubmitRequest
import com.edumath.uchus.data.api.SubmitResponse
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.EmptyBox
import com.edumath.uchus.ui.common.ErrorBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.Tag
import com.edumath.uchus.ui.teacher.TeacherAssignmentsScreen
import kotlinx.coroutines.launch

@Composable
fun AssignmentsScreen(
    container: AppContainer,
    role: String?,
    onBack: () -> Unit,
    onOpen: (Int) -> Unit,
    onResults: (Int) -> Unit = onOpen,
    onCreate: () -> Unit = {},
) {
    when (role) {
        "teacher", "admin" -> TeacherAssignmentsScreen(container, onBack, onResults, onCreate)
        "parent" -> ParentAssignmentsScreen(container, onBack)
        else -> StudentAssignmentsScreen(container, onBack, onOpen)
    }
}

@Composable
private fun StudentAssignmentsScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onOpen: (Int) -> Unit,
) {
    ScreenScaffold(title = "Работы", onBack = onBack) { padding ->
        Load(key = "assignments", block = { container.api.studentAssignments() }) { data, _ ->
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (data.assignments.isEmpty()) {
                    item { EmptyBox("Пока нет опубликованных работ.", "📝") }
                }
                items(data.assignments) { item ->
                    AssignmentCard(item) { onOpen(item.id) }
                }
                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }
}

@Composable
private fun ParentAssignmentsScreen(
    container: AppContainer,
    onBack: () -> Unit,
) {
    ScreenScaffold(title = "Домашние задания", onBack = onBack) { padding ->
        Load(key = "parent-assignments", block = { container.api.parentAssignments() }) { data, _ ->
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item {
                    InfoBox("Родительские задания создаются на сайте или в разделе «Дети».")
                }
                if (data.assignments.isEmpty()) {
                    item { EmptyBox("Вы ещё не назначали заданий.", "📝") }
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
                                "${item.questionsCount} заданий · ${item.kind ?: ""}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Text(
                                "Сдали: ${item.results.size}",
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

@Composable
fun AssignmentCard(item: AssignmentDto, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    item.displayTitle,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                val result = item.result
                if (result != null) {
                    Tag("${result.score}/${result.maxScore} · ${result.grade} б.")
                } else {
                    Tag("не сдано")
                }
            }
            Text(
                listOfNotNull(item.kind, item.dueDate?.takeIf { it.isNotBlank() }?.let { "до $it" })
                    .joinToString(" · "),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (!item.description.isNullOrBlank()) {
                Text(item.description ?: "", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
fun AssignmentDetailScreen(
    container: AppContainer,
    assignmentId: Int,
    onBack: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var submitted by remember { mutableStateOf<SubmitResponse?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    ScreenScaffold(title = "Работа", onBack = onBack) { padding ->
        val response = submitted
        if (response != null) {
            ResultScreen(
                title = "Работа сдана",
                result = response.result,
                details = response.details,
                padding = padding,
                onBack = onBack,
            )
            return@ScreenScaffold
        }

        Load(
            key = "assignment:$assignmentId",
            block = { container.api.assignment(assignmentId) },
        ) { data, _ ->
            if (data.submitted) {
                ResultScreen(
                    title = data.assignment?.displayTitle ?: "Результат",
                    result = data.result,
                    details = data.details,
                    padding = padding,
                    onBack = onBack,
                )
            } else {
                AssignmentForm(
                    data = data,
                    padding = padding,
                    busy = busy,
                    error = error,
                    onSubmit = { answers ->
                        if (!busy) {
                            busy = true
                            scope.launch {
                                runCatching {
                                    apiCall {
                                        container.api.submitAssignment(
                                            assignmentId,
                                            SubmitRequest(answers),
                                        )
                                    }
                                }
                                    .onSuccess { submitted = it; error = null }
                                    .onFailure { error = it.message }
                                busy = false
                            }
                        }
                    },
                )
            }
        }
    }
}

@Composable
private fun AssignmentForm(
    data: AssignmentDetailDto,
    padding: PaddingValues,
    busy: Boolean,
    error: String?,
    onSubmit: (List<String>) -> Unit,
) {
    val questions = data.questions
    val answers = remember(data) {
        mutableStateListOf<String>().apply { repeat(questions.size) { add("") } }
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text(
                data.assignment?.displayTitle ?: "Работа",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            if (!data.assignment?.description.isNullOrBlank()) {
                Text(
                    data.assignment?.description ?: "",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }

        if (error != null) {
            item { ErrorBox(error) }
        }

        items(questions) { question ->
            QuestionCard(
                question = question,
                value = answers.getOrNull(question.index) ?: "",
                onChange = { value -> answers[question.index] = value },
            )
        }

        item {
            Text(
                "Отвечено: ${answers.count { it.isNotBlank() }} из ${questions.size}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        item {
            Button(
                onClick = { onSubmit(answers.toList()) },
                enabled = !busy && answers.all { it.isNotBlank() },
                modifier = Modifier.fillMaxWidth(),
            ) { Text(if (busy) "Отправляем…" else "Сдать работу") }
        }

        item { Spacer(Modifier.height(16.dp)) }
    }
}

@Composable
private fun QuestionCard(question: QuestionDto, value: String, onChange: (String) -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                "${question.index + 1}. ${question.question}",
                fontWeight = FontWeight.SemiBold,
            )
            if (question.choices.isNotEmpty()) {
                question.choices.forEach { choice ->
                    if (choice == value) {
                        Button(onClick = { onChange(choice) }, modifier = Modifier.fillMaxWidth()) {
                            Text(choice)
                        }
                    } else {
                        OutlinedButton(
                            onClick = { onChange(choice) },
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text(choice) }
                    }
                }
            } else {
                OutlinedTextField(
                    value = value,
                    onValueChange = onChange,
                    label = { Text("Ответ") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
    }
}

@Composable
fun ResultScreen(
    title: String,
    result: ResultSummaryDto?,
    details: List<StepResultDto>,
    padding: PaddingValues,
    onBack: () -> Unit,
) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        item {
            Card(Modifier.fillMaxWidth()) {
                Column(
                    Modifier
                        .fillMaxWidth()
                        .padding(20.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    if (result != null) {
                        Text(
                            "${result.score} из ${result.maxScore}",
                            style = MaterialTheme.typography.headlineMedium,
                        )
                        Text(
                            "${result.percent}% · оценка ${result.grade}",
                            style = MaterialTheme.typography.titleMedium,
                        )
                        if (!result.completedAt.isNullOrBlank()) {
                            Text(
                                result.completedAt ?: "",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        }

        if (details.isNotEmpty()) {
            item { SectionTitle("Разбор") }
            items(details) { item ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(if (item.correct) "✅" else "❌")
                            Spacer(Modifier.width(6.dp))
                            Text(item.question, style = MaterialTheme.typography.bodyMedium)
                        }
                        Text(
                            "ваш ответ: ${item.given.ifBlank { "—" }} · верный: ${item.expected}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        if (!item.solution.isNullOrBlank()) {
                            Text(item.solution ?: "", style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
        }

        item {
            Button(onClick = onBack, modifier = Modifier.fillMaxWidth()) { Text("Назад") }
        }
        item { Spacer(Modifier.height(16.dp)) }
    }
}
