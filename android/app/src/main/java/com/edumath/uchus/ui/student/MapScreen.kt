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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.DailyItemDto
import com.edumath.uchus.data.api.MapDto
import com.edumath.uchus.data.api.TopicCardDto
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.StatsRow
import com.edumath.uchus.data.api.ApiJson
import com.edumath.uchus.ui.common.Tag

@Composable
fun MapScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onTopic: (String) -> Unit,
    onDaily: (String) -> Unit,
) {
    var subject by remember { mutableStateOf<String?>(null) }
    val gson = remember { ApiJson.gson }

    ScreenScaffold(title = "Карта тем", onBack = onBack) { padding ->
        Load(
            key = "map:${subject ?: "default"}",
            cache = container.cache,
            gson = gson,
            cacheKey = "map:${subject ?: "default"}",
            cacheClass = MapDto::class.java,
            block = { container.api.map(null, subject) },
        ) { data, refresh ->
            val playful = data.grade in 1..4
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item {
                    data.stats?.let { stats ->
                        if (playful) {
                            StatsRow(
                                "уровень" to "${stats.level}",
                                "опыт" to "${stats.xp}",
                                "монеты" to "${stats.coins}",
                                "звёзды" to "${stats.stars}",
                            )
                        } else {
                            StatsRow(
                                "класс" to "${data.grade}",
                                "точность" to "${stats.accuracy}%",
                                "серия" to "${stats.streakDays}",
                            )
                        }
                    }
                }

                item {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(data.subjects) { item ->
                            FilterChip(
                                selected = item.slug == data.subject?.slug,
                                onClick = {
                                    if (item.slug != subject) {
                                        subject = item.slug
                                    }
                                },
                                label = { Text("${item.icon ?: "📘"} ${item.name ?: item.slug}") },
                            )
                        }
                    }
                }

                if (data.daily.isNotEmpty()) {
                    item {
                        DailyCard(
                            tasks = data.daily,
                            done = data.dailyDone,
                            onStart = {
                                val next = data.daily.firstOrNull { !it.done } ?: data.daily.first()
                                onDaily(next.generator)
                            },
                        )
                    }
                }

                item {
                    SectionTitle(
                        "Темы ${data.grade} класса",
                        trailing = "${data.topics.size}",
                    )
                }

                items(data.topics) { topic ->
                    TopicCard(topic, playful) { onTopic(topic.slug) }
                }

                if (data.topics.isEmpty()) {
                    item {
                        Text(
                            "Для этого предмета пока нет тем. Учитель может включить их в курсе класса.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }

                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }
}

@Composable
private fun DailyCard(
    tasks: List<DailyItemDto>,
    done: Boolean,
    onStart: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("🎯 Ежедневные задания", fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
                Tag(if (done) "выполнено" else "на сегодня")
            }
            tasks.forEach { task ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(if (task.done) "✅" else "▫️", fontSize = 16.sp)
                    Spacer(Modifier.width(8.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            task.topic ?: task.generator,
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Text(
                            task.label ?: task.generator,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            Button(onClick = onStart, modifier = Modifier.fillMaxWidth()) {
                Text(if (done) "Повторить задание" else "Начать")
            }
        }
    }
}

@Composable
private fun TopicCard(topic: TopicCardDto, playful: Boolean, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(topic.emoji, fontSize = 30.sp)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(topic.displayTitle, fontWeight = FontWeight.SemiBold)
                val subtitle = buildString {
                    if (topic.kind == "reading") {
                        append(if (topic.read) "прочитано" else "чтение")
                        if (topic.booksCount > 0) append(" · ${topic.booksCount} кн.")
                    } else {
                        append("точность ${topic.accuracy}%")
                        append(" · методы ${topic.methodsMastered}/${topic.methodsTotal}")
                    }
                }
                Text(
                    subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    if (playful) {
                        Text(starsText(topic.stars), color = MaterialTheme.colorScheme.tertiary)
                        if (topic.bossCleared) Tag("босс пройден")
                    }
                    if (topic.part?.isNotBlank() == true) Tag(topic.part ?: "")
                }
            }
            Text("→", style = MaterialTheme.typography.titleMedium)
        }
    }
}

fun starsText(stars: Int): String {
    val filled = "★".repeat(stars.coerceIn(0, 3))
    val empty = "☆".repeat((3 - stars).coerceIn(0, 3))
    return filled + empty
}
