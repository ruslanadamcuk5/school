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
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.AnswerDto
import com.edumath.uchus.data.api.AnswerRequest
import com.edumath.uchus.data.api.DailyStartRequest
import com.edumath.uchus.data.api.PlayResultDto
import com.edumath.uchus.data.api.PlayStartRequest
import com.edumath.uchus.data.api.RoundStateDto
import com.edumath.uchus.data.api.TaskDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.ErrorBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.LoadingBox
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.Tag
import kotlinx.coroutines.launch

@Composable
fun PlayScreen(
    container: AppContainer,
    topicSlug: String?,
    generator: String?,
    mode: String,
    onBack: () -> Unit,
    playful: Boolean = true,
) {
    val scope = rememberCoroutineScope()
    var roundId by remember { mutableStateOf<Int?>(null) }
    var task by remember { mutableStateOf<TaskDto?>(null) }
    var state by remember { mutableStateOf<RoundStateDto?>(null) }
    var done by remember { mutableStateOf(false) }
    var feedback by remember { mutableStateOf<AnswerDto?>(null) }
    var result by remember { mutableStateOf<PlayResultDto?>(null) }
    var hintText by remember { mutableStateOf<String?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var answerText by remember { mutableStateOf("") }
    var startTick by remember { mutableIntStateOf(0) }

    LaunchedEffect(startTick) {
        roundId = null
        task = null
        state = null
        done = false
        feedback = null
        result = null
        hintText = null
        error = null
        answerText = ""
        runCatching {
            apiCall {
                if (generator != null) {
                    container.api.dailyStart(DailyStartRequest(generator))
                } else {
                    container.api.playStart(PlayStartRequest(topicSlug ?: "", mode, null))
                }
            }
        }
            .onSuccess {
                roundId = it.roundId
                task = it.task
                state = it.state
                done = it.done
            }
            .onFailure { error = it.message }
    }

    LaunchedEffect(done) {
        val id = roundId
        if (done && id != null && result == null) {
            runCatching { apiCall { container.api.playResult(id) } }
                .onSuccess { result = it }
                .onFailure { error = it.message }
        }
    }

    fun submit(value: String) {
        val id = roundId ?: return
        if (busy || done || value.isBlank()) return
        busy = true
        scope.launch {
            runCatching { apiCall { container.api.playAnswer(id, AnswerRequest(value)) } }
                .onSuccess { response ->
                    feedback = response
                    state = response.state
                    if (!response.hint.isNullOrBlank()) hintText = response.hint
                    if (response.done) done = true
                    error = null
                }
                .onFailure { error = it.message }
            busy = false
        }
    }

    fun next() {
        val id = roundId ?: return
        if (busy) return
        busy = true
        scope.launch {
            feedback = null
            hintText = null
            answerText = ""
            runCatching { apiCall { container.api.playRound(id) } }
                .onSuccess {
                    if (it.done) {
                        done = true
                    } else {
                        task = it.task
                        state = it.state
                    }
                    error = null
                }
                .onFailure { error = it.message }
            busy = false
        }
    }

    ScreenScaffold(title = if (generator != null) "Задание дня" else "Тренировка", onBack = onBack) { padding ->
        when {
            error != null && task == null -> Column(Modifier.padding(padding)) {
                ErrorBox(error!!) { startTick++ }
            }

            roundId == null -> Column(Modifier.padding(padding)) { LoadingBox() }

            done -> Column(
                Modifier
                    .fillMaxSize()
                    .padding(padding),
            ) {
                if (result == null) {
                    LoadingBox("Считаем результат…")
                } else {
                    ResultView(
                        result = result!!,
                        playful = playful,
                        onAgain = { startTick++ },
                        onFinish = onBack,
                    )
                }
            }

            else -> {
                val current = task
                if (current == null) {
                    Column(Modifier.padding(padding)) {
                        ErrorBox("Задание не загрузилось") { next() }
                    }
                } else {
                    LazyColumn(
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(padding),
                        contentPadding = PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        item { ProgressHeader(current, state, playful) }

                        item {
                            Card(Modifier.fillMaxWidth()) {
                                Text(
                                    current.question,
                                    modifier = Modifier.padding(18.dp),
                                    style = MaterialTheme.typography.headlineSmall,
                                    fontWeight = FontWeight.SemiBold,
                                )
                            }
                        }

                        if (message != null) {
                            item { InfoBox(message!!) }
                        }

                        item {
                            if (current.choices.isNotEmpty()) {
                                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    current.choices.forEach { choice ->
                                        OutlinedButton(
                                            onClick = { submit(choice) },
                                            enabled = !busy,
                                            modifier = Modifier.fillMaxWidth(),
                                        ) { Text(choice, fontSize = 18.sp) }
                                    }
                                }
                            } else {
                                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                                    OutlinedTextField(
                                        value = answerText,
                                        onValueChange = { answerText = it },
                                        label = { Text("Ответ") },
                                        singleLine = true,
                                        enabled = !busy,
                                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                                        modifier = Modifier.fillMaxWidth(),
                                    )
                                    Button(
                                        onClick = { submit(answerText.trim()) },
                                        enabled = !busy && answerText.isNotBlank(),
                                        modifier = Modifier.fillMaxWidth(),
                                    ) { Text("Ответить") }
                                }
                            }
                        }

                        item {
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                OutlinedButton(
                                    onClick = {
                                        val id = roundId ?: return@OutlinedButton
                                        busy = true
                                        scope.launch {
                                            runCatching { apiCall { container.api.playHint(id) } }
                                                .onSuccess {
                                                    hintText = it.hint
                                                    message = "Подсказок осталось: ${it.left}"
                                                }
                                                .onFailure { message = it.message }
                                            busy = false
                                        }
                                    },
                                    enabled = !busy && feedback == null,
                                    modifier = Modifier.weight(1f),
                                ) { Text("Подсказка") }
                                if (current.canSwitchMethod) {
                                    OutlinedButton(
                                        onClick = {
                                            val id = roundId ?: return@OutlinedButton
                                            busy = true
                                            scope.launch {
                                                runCatching { apiCall { container.api.playSwitch(id) } }
                                                    .onSuccess {
                                                        message = "Новый способ: ${it.name ?: it.method}. ${it.explanation ?: ""}"
                                                    }
                                                    .onFailure { message = it.message }
                                                busy = false
                                            }
                                        },
                                        enabled = !busy,
                                        modifier = Modifier.weight(1f),
                                    ) { Text("Другой способ") }
                                }
                            }
                        }

                        if (hintText != null) {
                            item { InfoBox("💡 $hintText") }
                        }

                        val fb = feedback
                        if (fb != null) {
                            item {
                                FeedbackCard(fb, playful) {
                                    if (fb.retry) {
                                        feedback = null
                                    } else {
                                        next()
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ProgressHeader(task: TaskDto, state: RoundStateDto?, playful: Boolean) {
    val total = state?.total ?: task.total
    val index = (state?.index ?: task.index) + 1
    val fraction = if (total > 0) (index.toFloat() / total).coerceIn(0f, 1f) else 0f
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(
                "Вопрос $index из $total",
                style = MaterialTheme.typography.labelLarge,
                modifier = Modifier.weight(1f),
            )
            if (playful && (state?.combo ?: 0) > 1) {
                Tag("серия ×${state?.combo}")
            }
            if (task.method?.name?.isNotBlank() == true) {
                Spacer(Modifier.width(6.dp))
                Tag(task.method?.name ?: "")
            }
        }
        LinearProgressIndicator(
            progress = { fraction },
            modifier = Modifier
                .fillMaxWidth()
                .height(8.dp),
        )
    }
}

@Composable
private fun FeedbackCard(feedback: AnswerDto, playful: Boolean, onContinue: () -> Unit) {
    val good = feedback.correct
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Text(
                if (good) "✅ Верно!" else if (feedback.retry) "Пока неверно" else "❌ Неверно",
                fontWeight = FontWeight.Bold,
                color = if (good) Color(0xFF15803D) else MaterialTheme.colorScheme.error,
            )
            if (!good && !feedback.correctAnswer.isNullOrBlank()) {
                Text("Правильный ответ: ${feedback.correctAnswer}")
            }
            if (!feedback.solution.isNullOrBlank()) {
                Text(
                    feedback.solution ?: "",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (playful && good && (feedback.xp > 0 || feedback.coins > 0)) {
                Text(
                    "+${feedback.xp} опыта, +${feedback.coins} монет",
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            if (feedback.methodSwitched) {
                Text("Способ решения изменён — попробуйте новый.", style = MaterialTheme.typography.bodySmall)
            }
            if (playful && feedback.badges.isNotEmpty()) {
                Text(
                    "Новые значки: " + feedback.badges.joinToString { it.icon ?: "🏅" },
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            Button(onClick = onContinue, modifier = Modifier.fillMaxWidth()) {
                Text(if (feedback.retry) "Попробовать снова" else "Дальше")
            }
        }
    }
}

@Composable
private fun ResultView(
    result: PlayResultDto,
    playful: Boolean,
    onAgain: () -> Unit,
    onFinish: () -> Unit,
) {
    LazyColumn(
        modifier = Modifier.fillMaxSize(),
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
                        if (playful) {
                            if (result.stars >= 3) "🏆 Отлично!"
                            else if (result.stars >= 2) "🎉 Хорошо!"
                            else "💪 Есть над чем поработать"
                        } else {
                            "Тренировка завершена"
                        },
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                    )
                    if (playful && result.mode != "daily") {
                        Text(starsText(result.stars), fontSize = 36.sp, color = MaterialTheme.colorScheme.tertiary)
                    }
                    Text(
                        "Верно ${result.correct} из ${result.total}",
                        style = MaterialTheme.typography.titleMedium,
                    )
                    if (playful) {
                        Text(
                            "+${result.xp} опыта · +${result.coins} монет · серия ${result.maxCombo}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    if (playful && result.badges.isNotEmpty()) {
                        Text(
                            "Значки: " + result.badges.joinToString(" ") { it.icon ?: "🏅" },
                            style = MaterialTheme.typography.bodyMedium,
                        )
                    }
                }
            }
        }

        item {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onAgain, modifier = Modifier.weight(1f)) {
                    Text("Ещё раз")
                }
                Button(onClick = onFinish, modifier = Modifier.weight(1f)) {
                    Text("Готово")
                }
            }
        }

        item { SectionTitle("Разбор заданий") }
        items(result.items) { item ->
            Card(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(item.question, style = MaterialTheme.typography.bodyMedium)
                    Text(
                        (if (item.correct) "✅ " else "❌ ") +
                            "ваш ответ: ${item.given?.ifBlank { "—" } ?: "—"} · верный: ${item.answer ?: "—"}",
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
        item { Spacer(Modifier.height(12.dp)) }
    }
}
