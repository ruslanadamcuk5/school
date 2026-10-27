package com.edumath.uchus.ui.student

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import coil.compose.SubcomposeAsyncImage
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.ui.common.EmptyBox
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.Tag

@Composable
fun ReaderScreen(
    container: AppContainer,
    textbookId: Int,
    startPage: Int,
    onBack: () -> Unit,
) {
    var page by remember { mutableIntStateOf(startPage.coerceAtLeast(1)) }
    var attempt by remember(page) { mutableIntStateOf(0) }

    ScreenScaffold(title = "Учебник", onBack = onBack) { padding ->
        Load(
            key = "book:$textbookId",
            block = { container.api.book(textbookId) },
        ) { info, _ ->
            val book = info.book
            val pages = book?.pages ?: 0
            val base = container.session.baseUrl.trimEnd('/')
            val url = buildString {
                append(base)
                append("/api/v1/books/")
                append(textbookId)
                append("/page/")
                append(page)
                append(".png")
                // После ошибки меняем URL, чтобы Coil не взял закэшированный сбой.
                if (attempt > 0) {
                    append("?attempt=")
                    append(attempt)
                }
            }

            LaunchedEffect(pages) {
                if (pages > 0 && page > pages) page = pages
            }

            Column(
                Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(horizontal = 12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        book?.displayTitle ?: "Учебник",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.weight(1f),
                    )
                    Tag(if (pages > 0) "стр. $page из $pages" else "стр. $page")
                }

                if (info.topics.isNotEmpty()) {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        items(info.topics) { link ->
                            FilterChip(
                                selected = link.page == page,
                                onClick = { link.page?.let { page = it } },
                                label = { Text("стр. ${link.page ?: "?"}") },
                            )
                        }
                    }
                }

                Card(Modifier.fillMaxWidth().weight(1f)) {
                    if (pages == 0) {
                        EmptyBox("В этом пособии нет страниц для показа.", "📄")
                    } else {
                        SubcomposeAsyncImage(
                            model = url,
                            imageLoader = container.imageLoader,
                            contentDescription = "Страница $page",
                            modifier = Modifier.fillMaxSize(),
                            contentScale = ContentScale.Fit,
                            loading = {
                                Box(
                                    modifier = Modifier.fillMaxSize(),
                                    contentAlignment = Alignment.Center,
                                ) {
                                    CircularProgressIndicator()
                                }
                            },
                            error = {
                                PageLoadError(
                                    page = page,
                                    onRetry = { attempt += 1 },
                                )
                            },
                        )
                    }
                }

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedButton(
                        onClick = { if (page > 1) page -= 1 },
                        enabled = page > 1,
                        modifier = Modifier.weight(1f),
                    ) { Text("← Назад") }
                    Button(
                        onClick = { page += 1 },
                        enabled = pages == 0 || page < pages,
                        modifier = Modifier.weight(1f),
                    ) { Text("Вперёд →") }
                }
            }
        }
    }
}

@Composable
private fun PageLoadError(page: Int, onRetry: () -> Unit) {
    Column(
        modifier = Modifier
            .fillMaxSize()
            .padding(24.dp),
        verticalArrangement = Arrangement.Center,
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Text("📄", fontSize = 42.sp)
        Spacer(Modifier.height(10.dp))
        Text(
            text = "Не удалось загрузить страницу $page",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
        )
        Spacer(Modifier.height(6.dp))
        Text(
            text = "Проверьте подключение к интернету и попробуйте ещё раз.",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(12.dp))
        OutlinedButton(onClick = onRetry) { Text("Повторить") }
    }
}
