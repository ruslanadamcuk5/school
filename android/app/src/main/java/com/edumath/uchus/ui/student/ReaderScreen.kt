package com.edumath.uchus.ui.student

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import coil.compose.AsyncImage
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

    ScreenScaffold(title = "Учебник", onBack = onBack) { padding ->
        Load(
            key = "book:$textbookId",
            block = { container.api.book(textbookId) },
        ) { info, _ ->
            val book = info.book
            val pages = book?.pages ?: 0
            val base = container.session.baseUrl.trimEnd('/')
            val url = "$base/api/v1/books/$textbookId/page/$page.png"

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
                        AsyncImage(
                            model = url,
                            imageLoader = container.imageLoader,
                            contentDescription = "Страница $page",
                            modifier = Modifier.fillMaxSize(),
                            contentScale = ContentScale.Fit,
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
