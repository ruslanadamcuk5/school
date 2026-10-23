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
import com.edumath.uchus.data.api.LibraryBookDto
import com.edumath.uchus.data.api.LibraryDto
import com.edumath.uchus.data.api.RecommendationDto
import com.edumath.uchus.data.api.UserDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.EmptyBox
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.StatsRow
import com.edumath.uchus.ui.common.Tag
import com.edumath.uchus.ui.teacher.TeacherLibraryScreen
import com.google.gson.Gson
import kotlinx.coroutines.launch

@Composable
fun LibraryScreen(
    container: AppContainer,
    role: String?,
    onBack: () -> Unit,
    onBook: (Int, Int) -> Unit,
) {
    when (role) {
        "teacher", "admin" -> TeacherLibraryScreen(container, onBack, onBook)
        "parent" -> ParentLibraryScreen(container, onBack, onBook)
        else -> StudentLibraryScreen(container, onBack, onBook)
    }
}

@Composable
private fun StudentLibraryScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onBook: (Int, Int) -> Unit,
) {
    val scope = rememberCoroutineScope()
    val gson = remember { Gson() }

    ScreenScaffold(title = "Библиотека", onBack = onBack) { padding ->
        Load(
            key = "library",
            cache = container.cache,
            gson = gson,
            cacheKey = "library",
            cacheClass = LibraryDto::class.java,
            block = { container.api.library() },
        ) { data, refresh ->
            LibraryList(
                data = data,
                padding = padding,
                onBook = onBook,
                onMarkDone = { rec ->
                    scope.launch {
                        runCatching { apiCall { container.api.recommendationDone(rec.id) } }
                            .onSuccess { refresh() }
                    }
                },
            )
        }
    }
}

@Composable
private fun ParentLibraryScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onBook: (Int, Int) -> Unit,
) {
    var childId by remember { mutableStateOf<Int?>(null) }
    val gson = remember { Gson() }

    ScreenScaffold(title = "Библиотека ребёнка", onBack = onBack) { padding ->
        Load(
            key = "parent-library:${childId ?: 0}",
            cache = container.cache,
            gson = gson,
            cacheKey = "parent-library:${childId ?: 0}",
            cacheClass = LibraryDto::class.java,
            block = { container.api.parentLibrary(childId) },
        ) { data, _ ->
            Column(
                Modifier
                    .fillMaxSize()
                    .padding(padding),
            ) {
                if (data.children.isNullOrEmpty()) {
                    EmptyBox(
                        "Нет привязанных детей. Привяжите ребёнка по коду в разделе «Дети».",
                        "👨‍👩‍👧",
                    )
                    return@Column
                }
                ChildChips(
                    children = data.children ?: emptyList(),
                    selected = childId,
                    onSelect = { childId = it },
                )
                LibraryList(
                    data = data,
                    padding = PaddingValues(0.dp),
                    onBook = onBook,
                    onMarkDone = null,
                )
            }
        }
    }
}

@Composable
private fun ChildChips(
    children: List<UserDto>,
    selected: Int?,
    onSelect: (Int?) -> Unit,
) {
    LazyRow(
        contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items(children) { child ->
            FilterChip(
                selected = selected == child.id,
                onClick = { onSelect(child.id) },
                label = { Text("${child.avatar ?: "🧒"} ${child.displayName}") },
            )
        }
    }
}

@Composable
private fun LibraryList(
    data: LibraryDto,
    padding: PaddingValues,
    onBook: (Int, Int) -> Unit,
    onMarkDone: ((RecommendationDto) -> Unit)?,
) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            StatsRow(
                "книги" to "${data.stats.books}",
                "рекомендации" to "${data.stats.active}",
                "прочитано" to "${data.stats.done}",
            )
        }

        if (data.recommendations.isNotEmpty()) {
            item { SectionTitle("Рекомендации учителя") }
            items(data.recommendations) { rec ->
                RecommendationCard(rec, onMarkDone)
            }
        }

        item { SectionTitle("Книги", trailing = "${data.books.size}") }

        if (data.books.isEmpty()) {
            item { EmptyBox("Книг пока нет. Учитель добавит их в библиотеку класса.", "📚") }
        }

        items(data.books) { book ->
            BookCard(book) { onBook(book.textbookId, 1) }
        }

        item { Spacer(Modifier.height(16.dp)) }
    }
}

@Composable
private fun RecommendationCard(rec: RecommendationDto, onMarkDone: ((RecommendationDto) -> Unit)?) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("⭐", fontSize = 20.sp)
                Spacer(Modifier.width(8.dp))
                Text(
                    rec.title ?: "Книга",
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                if (rec.done == 1) Tag("прочитано") else Tag("новая")
            }
            if (!rec.topicTitle.isNullOrBlank()) {
                Text(
                    "Тема: ${rec.topicTitle}" + (rec.page?.let { " · стр. $it" } ?: ""),
                    style = MaterialTheme.typography.bodySmall,
                )
            }
            if (!rec.note.isNullOrBlank()) {
                Text(
                    rec.note ?: "",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                "Учитель: " + listOfNotNull(rec.teacherFirst, rec.teacherLast).joinToString(" "),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (rec.done != 1 && onMarkDone != null) {
                OutlinedButton(
                    onClick = { onMarkDone(rec) },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Отметить прочитанной") }
            }
        }
    }
}

@Composable
private fun BookCard(book: LibraryBookDto, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(book.subjectIcon ?: "📕", fontSize = 30.sp)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(book.displayTitle, fontWeight = FontWeight.SemiBold)
                Text(
                    listOfNotNull(book.subjectName, book.author).joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    if (book.grade > 0) Tag("${book.grade} класс")
                    if (book.pages > 0) Tag("${book.pages} стр.")
                    if (book.topicsCount > 0) Tag("${book.topicsCount} тем")
                }
            }
            Text("→", style = MaterialTheme.typography.titleMedium)
        }
    }
}
