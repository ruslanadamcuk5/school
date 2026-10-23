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
import com.edumath.uchus.data.api.BookLinkDto
import com.edumath.uchus.data.api.MethodDto
import com.edumath.uchus.data.api.TopicDetailDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.Tag
import kotlinx.coroutines.launch

@Composable
fun TopicScreen(
    container: AppContainer,
    slug: String,
    onBack: () -> Unit,
    onPlay: (String, String) -> Unit,
    onQuiz: (String) -> Unit,
    onRead: (String) -> Unit,
    onBook: (Int, Int) -> Unit,
    onTopic: (String) -> Unit,
) {
    val scope = rememberCoroutineScope()
    var message by remember { mutableStateOf<String?>(null) }

    ScreenScaffold(title = "Тема", onBack = onBack) { padding ->
        Load(
            key = "topic:$slug",
            block = { container.api.topic(slug) },
        ) { data, refresh ->
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
