package com.edumath.uchus.ui.psychology

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.ApiJson
import com.edumath.uchus.data.api.PsychAnswerRequest
import com.edumath.uchus.data.api.PsychChildDto
import com.edumath.uchus.data.api.PsychQuestionDto
import com.edumath.uchus.data.api.PsychRecommendationDto
import com.edumath.uchus.data.api.PsychResultDataDto
import com.edumath.uchus.data.api.PsychScaleDto
import com.edumath.uchus.data.api.PsychTestDto
import com.edumath.uchus.data.api.SessionDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.EmptyBox
import com.edumath.uchus.ui.common.ErrorBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.StatsRow
import com.edumath.uchus.ui.common.Tag
import com.edumath.uchus.ui.theme.SitePalette
import kotlinx.coroutines.launch

private val Success = Color(0xFF4ADE80)

private fun kindColor(kind: String?): Color = when (kind) {
    "attention" -> SitePalette.Rose400
    "growth" -> SitePalette.Gold400
    "interest" -> SitePalette.Cyan400
    else -> Success
}

private fun kindLabel(kind: String?): String = when (kind) {
    "attention" -> "Обратите внимание"
    "growth" -> "Зона роста"
    "interest" -> "Интерес"
    else -> "Сильная сторона"
}

private fun levelColor(scale: PsychScaleDto): Color {
    val good = scale.goodHigh
    return when (scale.level) {
        "high" -> if (good) Success else SitePalette.Rose400
        "mid" -> if (good) SitePalette.Cyan400 else SitePalette.Gold400
        else -> if (good) SitePalette.Rose400 else Success
    }
}

private fun shortDate(value: String?): String = value?.take(10) ?: ""

/* ------------------------------------------------------------------ список */
@Composable
fun PsychologyScreen(
    container: AppContainer,
    session: SessionDto?,
    parent: Boolean,
    onBack: () -> Unit,
    onOpenTest: (String) -> Unit,
    onOpenResult: (Int) -> Unit,
) {
    if (parent || session?.user?.role == "parent") {
        ParentPsychologyContent(container, onBack, onOpenResult)
    } else {
        StudentPsychologyContent(container, session, onBack, onOpenTest, onOpenResult)
    }
}

@Composable
private fun StudentPsychologyContent(
    container: AppContainer,
    session: SessionDto?,
    onBack: () -> Unit,
    onOpenTest: (String) -> Unit,
    onOpenResult: (Int) -> Unit,
) {
    ScreenScaffold(title = "Школьная психология", onBack = onBack) { padding ->
        Load(key = "psych-tests", block = { container.api.psychTests() }) { data, _ ->
            val groups = listOf("abilities", "activities", "problems", "development")
                .mapNotNull { category ->
                    val items = data.tests.filter { it.category == category }
                    if (items.isEmpty()) null else category to items
                }
            val done = data.tests.count { it.completed }
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item {
                    Text(
                        "Тесты для ${data.band?.title ?: "школы"} · ${data.grade} класс",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                    )
                    Spacer(Modifier.height(6.dp))
                    InfoBox(
                        data.disclaimer
                            ?: "Это не диагноз и не экзамен. Результат помогает понять себя."
                    )
                }
                item {
                    StatsRow(
                        "тестов" to "${data.tests.size}",
                        "пройдено" to "$done",
                        "осталось" to "${(data.tests.size - done).coerceAtLeast(0)}",
                    )
                }
                groups.forEach { (category, tests) ->
                    item(key = "title-$category") {
                        SectionTitle(
                            tests.firstOrNull()?.categoryTitle ?: category,
                            trailing = "${tests.size}",
                        )
                    }
                    items(tests, key = { it.slug ?: it.title ?: it.hashCode().toString() }) { test ->
                        StudentTestCard(test, onOpenTest, onOpenResult)
                    }
                }
                if (data.tests.isEmpty()) {
                    item { EmptyBox("Тесты для вашего класса пока не сформированы", "🧠") }
                }
                if (data.history.isNotEmpty()) {
                    item { SectionTitle("История прохождений") }
                    items(data.history, key = { "h-${it.id}" }) { item ->
                        Card(
                            Modifier
                                .fillMaxWidth()
                                .clickable { onOpenResult(item.id) }
                        ) {
                            Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
                                Text("🧠", fontSize = 20.sp)
                                Spacer(Modifier.width(10.dp))
                                Column(Modifier.weight(1f)) {
                                    Text(
                                        item.testTitle ?: "Тест",
                                        fontWeight = FontWeight.SemiBold,
                                        style = MaterialTheme.typography.bodyMedium,
                                    )
                                    Text(
                                        item.headline ?: "",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                Text(
                                    shortDate(item.createdAt),
                                    style = MaterialTheme.typography.labelSmall,
                                    color = SitePalette.MutedDim,
                                )
                            }
                        }
                    }
                }
                item {
                    Text(
                        data.source ?: "",
                        modifier = Modifier.padding(top = 6.dp, bottom = 12.dp),
                        style = MaterialTheme.typography.labelSmall,
                        color = SitePalette.MutedDim,
                    )
                }
            }
        }
    }
}

@Composable
private fun StudentTestCard(
    test: PsychTestDto,
    onOpenTest: (String) -> Unit,
    onOpenResult: (Int) -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.Top) {
                Column(Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            test.title ?: "Тест",
                            fontWeight = FontWeight.Bold,
                            style = MaterialTheme.typography.titleSmall,
                        )
                        if (test.completed) {
                            Spacer(Modifier.width(6.dp))
                            Tag("пройден", Success)
                        }
                    }
                    Text(
                        test.subtitle ?: "",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Text(test.categoryIcon ?: "🧠", fontSize = 24.sp)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                Tag(test.duration ?: "тест", SitePalette.Cyan400)
                Tag("${test.questions} вопросов", SitePalette.Iris400)
                if (test.attempts > 1) Tag("${test.attempts} прохождения", SitePalette.Gold400)
            }
            test.latest?.let { latest ->
                Surface(
                    color = Success.copy(alpha = 0.08f),
                    shape = RoundedCornerShape(12.dp),
                    modifier = Modifier
                        .fillMaxWidth()
                        .border(1.dp, Success.copy(alpha = 0.2f), RoundedCornerShape(12.dp)),
                ) {
                    Column(Modifier.padding(10.dp)) {
                        Text(
                            "ПОСЛЕДНИЙ РЕЗУЛЬТАТ",
                            style = MaterialTheme.typography.labelSmall,
                            color = Success,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(latest.headline ?: "", style = MaterialTheme.typography.bodySmall)
                        Text(
                            shortDate(latest.createdAt),
                            style = MaterialTheme.typography.labelSmall,
                            color = SitePalette.MutedDim,
                        )
                    }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = { test.slug?.let(onOpenTest) },
                    modifier = Modifier.weight(1f),
                ) {
                    Text(if (test.completed) "Пройти снова" else "Начать тест")
                }
                test.latest?.let { latest ->
                    OutlinedButton(onClick = { onOpenResult(latest.id) }) {
                        Text("Результат")
                    }
                }
            }
        }
    }
}

@Composable
private fun ParentPsychologyContent(
    container: AppContainer,
    onBack: () -> Unit,
    onOpenResult: (Int) -> Unit,
) {
    ScreenScaffold(title = "Школьная психология", onBack = onBack) { padding ->
        Load(key = "psych-parent", block = { container.api.psychParent() }) { data, _ ->
            var selected by remember(data) {
                mutableStateOf(data.children.firstOrNull()?.learner?.id ?: 0)
            }
            val active = data.children.firstOrNull { it.learner?.id == selected }
                ?: data.children.firstOrNull()

            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (data.children.isEmpty()) {
                    item {
                        EmptyBox(
                            "Когда ребёнок пройдёт тесты в своём кабинете, результаты появятся здесь.",
                            "🧠",
                        )
                    }
                    return@LazyColumn
                }

                item {
                    InfoBox(
                        data.disclaimer
                            ?: "Это мягкий скрининг, а не диагноз. При трудностях обратитесь к школьному психологу."
                    )
                }

                if (data.children.size > 1) {
                    item {
                        LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            items(data.children, key = { it.learner?.id ?: it.hashCode() }) { child ->
                                val id = child.learner?.id ?: 0
                                FilterChip(
                                    selected = id == active?.learner?.id,
                                    onClick = { selected = id },
                                    label = {
                                        Text(
                                            "${child.learner?.avatar ?: "🦊"} " +
                                                (child.learner?.name ?: "Ребёнок") +
                                                " · ${child.grade} кл."
                                        )
                                    },
                                )
                            }
                        }
                    }
                }

                active?.let { child ->
                    item {
                        StatsRow(
                            "тестов" to "${child.stats?.tests ?: 0}",
                            "сильных" to "${child.stats?.strengths ?: 0}",
                            "внимание" to "${child.stats?.attention ?: 0}",
                        )
                    }
                    if (child.recommendations.isNotEmpty()) {
                        item { SectionTitle("Рекомендации родителям") }
                        items(
                            child.recommendations,
                            key = { "${it.resultId}-${it.scale}-${it.title}-${it.kind}" },
                        ) { item ->
                            ParentRecommendationCard(item, onOpenResult)
                        }
                    }
                    item { SectionTitle("Пройденные тесты") }
                    if (child.results.isEmpty()) {
                        item {
                            EmptyBox(
                                "Ребёнок ещё не проходил тесты. Они находятся в кабинете ученика.",
                                "📝",
                            )
                        }
                    } else {
                        items(child.results, key = { "r-${it.id}" }) { item ->
                            Card(
                                Modifier
                                    .fillMaxWidth()
                                    .clickable { onOpenResult(item.id) }
                            ) {
                                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Text(
                                            item.testTitle ?: "Тест",
                                            modifier = Modifier.weight(1f),
                                            fontWeight = FontWeight.SemiBold,
                                            style = MaterialTheme.typography.bodyMedium,
                                        )
                                        Tag(item.categoryTitle ?: "тест", SitePalette.Cyan400)
                                    }
                                    Text(
                                        item.headline ?: "",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Text(
                                            shortDate(item.createdAt),
                                            style = MaterialTheme.typography.labelSmall,
                                            color = SitePalette.MutedDim,
                                        )
                                        Spacer(Modifier.weight(1f))
                                        if (item.hasAi) Tag("ИИ", SitePalette.Iris400)
                                        Text(
                                            "  Открыть →",
                                            style = MaterialTheme.typography.labelSmall,
                                            color = SitePalette.Iris400,
                                            fontWeight = FontWeight.Bold,
                                        )
                                    }
                                }
                            }
                        }
                    }
                    item {
                        InfoBox(
                            "После каждого теста приходят уведомления о результате и новых рекомендациях. " +
                                "Их можно открыть в разделе «Уведомления»."
                        )
                    }
                }

                item {
                    Text(
                        data.source ?: "",
                        modifier = Modifier.padding(top = 6.dp, bottom = 12.dp),
                        style = MaterialTheme.typography.labelSmall,
                        color = SitePalette.MutedDim,
                    )
                }
            }
        }
    }
}

@Composable
private fun ParentRecommendationCard(
    item: PsychRecommendationDto,
    onOpenResult: (Int) -> Unit,
) {
    val tone = kindColor(item.kind)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(item.title ?: "Рекомендация", modifier = Modifier.weight(1f), fontWeight = FontWeight.Bold)
                Tag(kindLabel(item.kind), tone)
            }
            Text(
                item.text ?: "",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            item.advice.take(4).forEach { advice ->
                Row(verticalAlignment = Alignment.Top) {
                    Text("✓", color = Success, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.width(6.dp))
                    Text(advice, style = MaterialTheme.typography.bodySmall)
                }
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "${item.testTitle ?: ""} · ${shortDate(item.createdAt)}",
                    style = MaterialTheme.typography.labelSmall,
                    color = SitePalette.MutedDim,
                )
                Spacer(Modifier.weight(1f))
                TextButton(onClick = { onOpenResult(item.resultId) }) {
                    Text("Весь результат")
                }
            }
        }
    }
}

/* ------------------------------------------------------------------ тест */
@Composable
fun PsychologyTestScreen(
    container: AppContainer,
    slug: String,
    onBack: () -> Unit,
    onResult: (Int) -> Unit,
) {
    val scope = rememberCoroutineScope()
    var index by remember { mutableIntStateOf(0) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val answers = remember { mutableStateMapOf<Int, Int>() }

    ScreenScaffold(title = "Психологический тест", onBack = onBack) { padding ->
        Load(key = "psych-test-$slug", block = { container.api.psychTest(slug) }) { data, _ ->
            val questions = data.questions
            val test = data.test
            if (questions.isEmpty()) {
                Column(Modifier.padding(padding).padding(16.dp)) {
                    EmptyBox("Вопросы не найдены", "🧠")
                }
                return@Load
            }
            val question = questions[index.coerceIn(0, questions.lastIndex)]
            val selected = answers[question.id]
            val last = index >= questions.lastIndex

            Column(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .verticalScroll(rememberScrollState())
                    .padding(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Text(
                    "${test?.categoryIcon ?: "🧠"} ${test?.title ?: "Тест"}",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    "${test?.subtitle ?: ""} · ${test?.duration ?: ""}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                LinearProgressIndicator(
                    progress = { (index + 1f) / questions.size },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(8.dp),
                )
                Text(
                    "Вопрос ${index + 1} из ${questions.size} · отвечено ${answers.size}",
                    style = MaterialTheme.typography.labelSmall,
                    color = SitePalette.MutedDim,
                )

                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text(
                            question.text ?: "",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                        )
                        question.options.forEachIndexed { optionIndex, option ->
                            val chosen = selected == optionIndex
                            Surface(
                                color = if (chosen) SitePalette.Iris500.copy(alpha = 0.22f) else SitePalette.Ink800,
                                shape = RoundedCornerShape(14.dp),
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .border(
                                        1.dp,
                                        if (chosen) SitePalette.Iris400 else SitePalette.Border,
                                        RoundedCornerShape(14.dp),
                                    )
                                    .clickable { answers[question.id] = optionIndex },
                            ) {
                                Row(
                                    Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    Text(
                                        if (chosen) "✓" else "${optionIndex + 1}",
                                        color = if (chosen) SitePalette.Iris400 else SitePalette.Muted,
                                        fontWeight = FontWeight.Bold,
                                        modifier = Modifier.width(24.dp),
                                    )
                                    Text(option, style = MaterialTheme.typography.bodyMedium)
                                }
                            }
                        }
                    }
                }

                error?.let { ErrorBox(it) }

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(
                        onClick = { index = (index - 1).coerceAtLeast(0) },
                        enabled = index > 0 && !busy,
                        modifier = Modifier.weight(1f),
                    ) {
                        Text("Назад")
                    }
                    if (last) {
                        Button(
                            onClick = {
                                if (answers.size < questions.size) {
                                    error = "Ответьте на все вопросы"
                                    return@Button
                                }
                                busy = true
                                error = null
                                scope.launch {
                                    runCatching {
                                        apiCall {
                                            container.api.psychSubmit(
                                                slug,
                                                PsychAnswerRequest(
                                                    answers.mapKeys { it.key.toString() },
                                                ),
                                            )
                                        }
                                    }.onSuccess { response ->
                                        val id = response.result?.id ?: 0
                                        if (id > 0) onResult(id) else error = "Результат не получен"
                                    }.onFailure { error = it.message ?: "Не удалось сохранить ответы" }
                                    busy = false
                                }
                            },
                            enabled = !busy,
                            modifier = Modifier.weight(1.4f),
                        ) {
                            Text(if (busy) "ИИ готовит заключение…" else "Завершить")
                        }
                    } else {
                        Button(
                            onClick = { index = (index + 1).coerceAtMost(questions.lastIndex) },
                            enabled = selected != null && !busy,
                            modifier = Modifier.weight(1.4f),
                        ) {
                            Text("Далее")
                        }
                    }
                }

                data.latestResultId?.let { latest ->
                    TextButton(
                        onClick = { onResult(latest) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Открыть предыдущий результат")
                    }
                }
                Text(
                    data.disclaimer ?: "",
                    modifier = Modifier.fillMaxWidth(),
                    textAlign = TextAlign.Center,
                    style = MaterialTheme.typography.labelSmall,
                    color = SitePalette.MutedDim,
                )
            }
        }
    }
}

/* ------------------------------------------------------------------ результат */
@Composable
fun PsychologyResultScreen(
    container: AppContainer,
    resultId: Int,
    parent: Boolean,
    onBack: () -> Unit,
    onRetake: (String) -> Unit = {},
) {
    ScreenScaffold(title = "Результат теста", onBack = onBack) { padding ->
        Load(
            key = "psych-result-$parent-$resultId",
            block = {
                if (parent) container.api.psychParentResult(resultId)
                else container.api.psychResult(resultId)
            },
        ) { data, _ ->
            val result = data.result
            if (result == null) {
                Column(Modifier.padding(padding).padding(16.dp)) {
                    EmptyBox("Результат не найден", "🧠")
                }
                return@Load
            }
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item { ResultHero(result, parent) }
                item { ResultAiCard(result) }
                item { SectionTitle("По шкалам") }
                items(result.scales, key = { it.key ?: it.label ?: it.hashCode().toString() }) { scale ->
                    ScaleCard(scale)
                }
                if (result.recommendations.isNotEmpty()) {
                    item { SectionTitle(if (parent) "Рекомендации родителям" else "Что можно сделать") }
                    items(
                        result.recommendations,
                        key = { "${it.scale}-${it.title}-${it.kind}" },
                    ) { item ->
                        ResultRecommendationCard(item)
                    }
                }
                item {
                    InfoBox(
                        result.disclaimer
                            ?: "Это не диагноз. При выраженных трудностях обратитесь к школьному психологу."
                    )
                }
                if (!parent && !result.testSlug.isNullOrBlank()) {
                    item {
                        Button(
                            onClick = { onRetake(result.testSlug!!) },
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text("Пройти снова")
                        }
                    }
                }
                item {
                    Text(
                        result.source ?: "",
                        modifier = Modifier.padding(top = 4.dp, bottom = 12.dp),
                        style = MaterialTheme.typography.labelSmall,
                        color = SitePalette.MutedDim,
                    )
                }
            }
        }
    }
}

@Composable
private fun ResultHero(result: PsychResultDataDto, parent: Boolean) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Tag("${result.categoryIcon ?: "🧠"} ${result.categoryTitle ?: "Тест"}", SitePalette.Iris400)
                Spacer(Modifier.weight(1f))
                Text(
                    shortDate(result.createdAt),
                    style = MaterialTheme.typography.labelSmall,
                    color = SitePalette.MutedDim,
                )
            }
            Text(
                result.testTitle ?: "Результат",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (parent) {
                val child = result.learner?.name ?: result.learnerName
                if (!child.isNullOrBlank()) {
                    Text(
                        "$child · ${result.grade} класс",
                        style = MaterialTheme.typography.bodySmall,
                        color = SitePalette.Muted,
                    )
                }
            }
            Text(
                result.headline ?: "",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            Text(
                result.summary ?: "",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun ResultAiCard(result: PsychResultDataDto) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("✨ Заключение ИИ", fontWeight = FontWeight.Bold)
                Spacer(Modifier.weight(1f))
                Tag("персонально", SitePalette.Iris400)
            }
            val text = result.ai?.text
            if (text.isNullOrBlank()) {
                Text(
                    "ИИ сейчас недоступен, поэтому показано заключение по профессиональным шкалам. " +
                        "Оно уже содержит главное: сильные стороны, зоны поддержки и конкретные шаги.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            } else {
                text.split("\n").forEach { raw ->
                    val line = raw.replace("**", "").trim()
                    if (line.isNotEmpty()) {
                        if (line.startsWith("## ")) {
                            Text(
                                line.removePrefix("## "),
                                fontWeight = FontWeight.Bold,
                                style = MaterialTheme.typography.titleSmall,
                                modifier = Modifier.padding(top = 4.dp),
                            )
                        } else {
                            Text(
                                if (line.startsWith("- ")) "• ${line.removePrefix("- ")}" else line,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
                Text(
                    "Сгенерировано ИИ по результатам теста и проверенным психологическим шкалам. Не является диагнозом.",
                    style = MaterialTheme.typography.labelSmall,
                    color = SitePalette.MutedDim,
                )
            }
        }
    }
}

@Composable
private fun ScaleCard(scale: PsychScaleDto) {
    val tone = levelColor(scale)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "${scale.icon ?: ""} ${scale.label ?: ""}".trim(),
                    modifier = Modifier.weight(1f),
                    fontWeight = FontWeight.SemiBold,
                )
                Tag(scale.levelLabel ?: "", tone)
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                LinearProgressIndicator(
                    progress = { (scale.percent.coerceIn(0, 100)) / 100f },
                    color = tone,
                    modifier = Modifier
                        .weight(1f)
                        .height(8.dp),
                )
                Spacer(Modifier.width(8.dp))
                Text("${scale.percent}%", style = MaterialTheme.typography.labelSmall, color = SitePalette.Muted)
            }
            Text(
                scale.text ?: "",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            scale.advice.take(3).forEach { advice ->
                Row(verticalAlignment = Alignment.Top) {
                    Text("•", color = tone)
                    Spacer(Modifier.width(6.dp))
                    Text(
                        advice,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun ResultRecommendationCard(item: PsychRecommendationDto) {
    val tone = kindColor(item.kind)
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(item.title ?: "Рекомендация", modifier = Modifier.weight(1f), fontWeight = FontWeight.Bold)
                Tag(kindLabel(item.kind), tone)
            }
            Text(
                item.text ?: "",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            item.advice.forEach { advice ->
                Row(verticalAlignment = Alignment.Top) {
                    Text("✓", color = Success, fontWeight = FontWeight.Bold)
                    Spacer(Modifier.width(6.dp))
                    Text(advice, style = MaterialTheme.typography.bodySmall)
                }
            }
        }
    }
}
