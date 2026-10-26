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
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.TopicTextDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.EmptyBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.data.api.ApiJson
import kotlinx.coroutines.launch

@Composable
fun ReadScreen(
    container: AppContainer,
    slug: String,
    onBack: () -> Unit,
    onBook: (Int, Int) -> Unit,
    onQuiz: (String) -> Unit,
) {
    val scope = rememberCoroutineScope()
    val gson = remember { ApiJson.gson }
    var message by remember { mutableStateOf<String?>(null) }

    ScreenScaffold(title = "Чтение", onBack = onBack) { padding ->
        Load(
            key = "text:$slug",
            cache = container.cache,
            gson = gson,
            cacheKey = "text:$slug",
            cacheClass = TopicTextDto::class.java,
            block = { container.api.topicText(slug) },
        ) { data, refresh ->
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item {
                    Text(
                        data.topic?.displayTitle ?: "Текст темы",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        "Страницы учебника. Текст сохраняется для чтения без сети.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }

                if (message != null) {
                    item { InfoBox(message!!) }
                }

                item {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(
                            onClick = {
                                scope.launch {
                                    runCatching { apiCall { container.api.markRead(slug) } }
                                        .onSuccess {
                                            message = "Отмечено как прочитанное."
                                            refresh()
                                        }
                                        .onFailure { message = it.message }
                                }
                            },
                            modifier = Modifier.weight(1f),
                        ) { Text("Прочитано") }
                        OutlinedButton(
                            onClick = { onQuiz(slug) },
                            modifier = Modifier.weight(1f),
                        ) { Text("Тест") }
                    }
                }

                data.topic?.books?.let { books ->
                    if (books.isNotEmpty()) {
                        item {
                            OutlinedButton(
                                onClick = {
                                    val book = books.first()
                                    onBook(book.id, book.page ?: 1)
                                },
                                modifier = Modifier.fillMaxWidth(),
                            ) { Text("Открыть страницы учебника") }
                        }
                    }
                }

                if (data.pages.isEmpty()) {
                    item { EmptyBox("Для этой темы нет текста пособия.", "📄") }
                }

                items(data.pages) { page ->
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(
                                "Страница ${page.page}",
                                style = MaterialTheme.typography.labelMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Text(
                                page.text.ifBlank { "…" },
                                style = MaterialTheme.typography.bodyLarge,
                            )
                        }
                    }
                }

                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }
}
