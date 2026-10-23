package com.edumath.uchus.ui.student

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
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.QuizResultDto
import com.edumath.uchus.data.api.QuizStartDto
import com.edumath.uchus.data.api.QuizSubmitRequest
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.ErrorBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.Tag
import kotlinx.coroutines.launch

@Composable
fun QuizScreen(
    container: AppContainer,
    slug: String,
    onBack: () -> Unit,
    playful: Boolean = true,
) {
    val scope = rememberCoroutineScope()
    var result by remember { mutableStateOf<QuizResultDto?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    ScreenScaffold(title = "Тест по теме", onBack = onBack) { padding ->
        val quizResult = result
        if (quizResult != null) {
            QuizResultView(quizResult, playful, Modifier.padding(padding), onDone = onBack)
            return@ScreenScaffold
        }

        Load(
            key = "quiz:$slug",
            block = { container.api.quiz(slug) },
        ) { quiz, _ ->
            QuizForm(
                quiz = quiz,
                padding = padding,
                busy = busy,
                error = error,
                onSubmit = { answers ->
                    if (!busy) {
                        busy = true
                        scope.launch {
                            runCatching {
                                apiCall {
                                    container.api.quizSubmit(
                                        slug,
                                        QuizSubmitRequest(quiz.quizId, answers),
                                    )
                                }
                            }
                                .onSuccess { result = it; error = null }
                                .onFailure { error = it.message }
                            busy = false
                        }
                    }
                },
            )
        }
    }
}

@Composable
private fun QuizForm(
    quiz: QuizStartDto,
    padding: androidx.compose.foundation.layout.PaddingValues,
    busy: Boolean,
    error: String?,
    onSubmit: (List<String>) -> Unit,
) {
    val answers = remember(quiz) {
        mutableStateListOf<String>().apply {
            repeat(quiz.questions.size) { add("") }
        }
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
                quiz.topic?.displayTitle ?: "Тест",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            Text(
                "Выберите один вариант ответа в каждом вопросе.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        if (error != null) {
            item { ErrorBox(error) }
        }

        items(quiz.questions) { question ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "${question.index + 1}. ${question.question}",
                        fontWeight = FontWeight.SemiBold,
                    )
                    question.choices.forEach { choice ->
                        val selected = answers.getOrNull(question.index) == choice
                        if (selected) {
                            Button(
                                onClick = { answers[question.index] = choice },
                                modifier = Modifier.fillMaxWidth(),
                            ) { Text(choice) }
                        } else {
                            OutlinedButton(
                                onClick = { answers[question.index] = choice },
                                modifier = Modifier.fillMaxWidth(),
                            ) { Text(choice) }
                        }
                    }
                }
            }
        }

        item {
            val filled = answers.count { it.isNotBlank() }
            Text(
                "Отвечено: $filled из ${quiz.questions.size}",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        item {
            Button(
                onClick = { onSubmit(answers.toList()) },
                enabled = !busy && answers.all { it.isNotBlank() },
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (busy) "Проверяем…" else "Завершить тест")
            }
        }

        item { Spacer(Modifier.height(16.dp)) }
    }
}

@Composable
private fun QuizResultView(
    result: QuizResultDto,
    playful: Boolean,
    modifier: Modifier = Modifier,
    onDone: () -> Unit,
) {
    LazyColumn(
        modifier = modifier.fillMaxSize(),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Card(Modifier.fillMaxWidth()) {
                Column(
                    Modifier
                        .fillMaxWidth()
                        .padding(20.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        "Тест завершён",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                    )
                    if (playful) {
                        Text(starsText(result.stars), fontSize = 36.sp, color = MaterialTheme.colorScheme.tertiary)
                    }
                    Text("Верно ${result.correct} из ${result.total}")
                    if (playful && result.badges.isNotEmpty()) {
                        Text("Значки: " + result.badges.joinToString(" ") { it.icon ?: "🏅" })
                    }
                }
            }
        }

        item { SectionTitle("Разбор ответов") }
        items(result.results) { item ->
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
                        Text(
                            item.solution ?: "",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
        }

        item {
            Button(onClick = onDone, modifier = Modifier.fillMaxWidth()) { Text("К теме") }
        }
        item { InfoBox("Звёзды за тест учитываются в прогрессе темы.") }
        item { Spacer(Modifier.height(16.dp)) }
    }
}
