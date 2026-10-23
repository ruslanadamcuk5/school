package com.edumath.uchus.ui.teacher

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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import com.edumath.uchus.data.api.ClassDto
import com.edumath.uchus.data.api.LibraryBookDto
import com.edumath.uchus.data.api.RecommendRequest
import com.edumath.uchus.data.api.SubjectDto
import com.edumath.uchus.data.api.TeacherLibraryDto
import com.edumath.uchus.data.api.TextbookDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.EmptyBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.Tag
import kotlinx.coroutines.launch

@Composable
fun TeacherLibraryScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onBook: (Int, Int) -> Unit,
) {
    var tab by remember { mutableStateOf(0) }

    ScreenScaffold(title = "Библиотека", onBack = onBack) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                FilterChip(
                    selected = tab == 0,
                    onClick = { tab = 0 },
                    label = { Text("Мои книги") },
                )
                FilterChip(
                    selected = tab == 1,
                    onClick = { tab = 1 },
                    label = { Text("Пособия") },
                )
            }

            if (tab == 0) {
                TeacherBooksTab(container, onBook)
            } else {
                TeacherTextbooksTab(container)
            }
        }
    }
}

@Composable
private fun TeacherBooksTab(container: AppContainer, onBook: (Int, Int) -> Unit) {
    val scope = rememberCoroutineScope()
    var searchInput by remember { mutableStateOf("") }
    var search by remember { mutableStateOf("") }
    var grade by remember { mutableStateOf<Int?>(null) }
    var subjectId by remember { mutableStateOf<Int?>(null) }
    var tick by remember { mutableStateOf(0) }
    var message by remember { mutableStateOf<String?>(null) }
    var recommendTarget by remember { mutableStateOf<LibraryBookDto?>(null) }
    var deleteTarget by remember { mutableStateOf<LibraryBookDto?>(null) }

    Load(
        key = "teacher-library:$search:$grade:$subjectId:$tick",
        block = { container.api.teacherLibrary(search.ifBlank { null }, grade, subjectId) },
    ) { data, refresh ->
        Column(Modifier.fillMaxSize()) {
            OutlinedTextField(
                value = searchInput,
                onValueChange = { searchInput = it },
                label = { Text("Поиск книги") },
                singleLine = true,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
            )
            Row(
                Modifier.padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Button(
                    onClick = { search = searchInput.trim() },
                    modifier = Modifier.weight(1f),
                ) { Text("Найти") }
                OutlinedButton(
                    onClick = {
                        searchInput = ""
                        search = ""
                        grade = null
                        subjectId = null
                    },
                    modifier = Modifier.weight(1f),
                ) { Text("Сбросить") }
            }

            LazyRow(
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 6.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                item {
                    FilterChip(
                        selected = grade == null,
                        onClick = { grade = null },
                        label = { Text("все классы") },
                    )
                }
                items((1..11).toList()) { value ->
                    FilterChip(
                        selected = grade == value,
                        onClick = { grade = value },
                        label = { Text("$value") },
                    )
                }
            }

            LazyRow(
                contentPadding = PaddingValues(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                item {
                    FilterChip(
                        selected = subjectId == null,
                        onClick = { subjectId = null },
                        label = { Text("все предметы") },
                    )
                }
                items(data.subjects) { subject ->
                    FilterChip(
                        selected = subjectId == subject.id,
                        onClick = { subjectId = subject.id },
                        label = { Text("${subject.icon ?: ""} ${subject.name ?: ""}") },
                    )
                }
            }

            if (message != null) {
                Column(Modifier.padding(horizontal = 16.dp, vertical = 4.dp)) {
                    InfoBox(message!!)
                }
            }

            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item {
                    Text(
                        "Книг: ${data.books.size} · рекомендаций: ${data.stats.recommendations}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }

                if (data.books.isEmpty()) {
                    item { EmptyBox("Книг нет. Добавьте пособие во вкладке «Пособия».", "📚") }
                }

                items(data.books) { book ->
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(book.subjectIcon ?: "📕", fontSize = 26.sp)
                                Spacer(Modifier.width(10.dp))
                                Column(Modifier.weight(1f)) {
                                    Text(book.displayTitle, fontWeight = FontWeight.SemiBold)
                                    Text(
                                        listOfNotNull(book.author, book.subjectName)
                                            .joinToString(" · "),
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                                Tag("${book.grade} кл.")
                            }
                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Tag("${book.pages} стр.")
                                Tag("${book.topicsCount} тем")
                                Tag("${book.classesCount} кл.")
                            }
                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                if (book.textbookId > 0) {
                                    OutlinedButton(onClick = { onBook(book.textbookId, 1) }) {
                                        Text("Открыть")
                                    }
                                }
                                OutlinedButton(onClick = { recommendTarget = book }) {
                                    Text("Рекомендовать")
                                }
                                TextButton(onClick = { deleteTarget = book }) {
                                    Text("Удалить", color = MaterialTheme.colorScheme.error)
                                }
                            }
                        }
                    }
                }
                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }

    val target = recommendTarget
    if (target != null) {
        ClassPickerDialog(
            title = "Рекомендовать «${target.displayTitle}»",
            classes = emptyList(),
            loadClasses = { apiCall { container.api.teacherLibrary(null, null, null) }.classes },
            onDismiss = { recommendTarget = null },
            onConfirm = { classIds, note ->
                scope.launch {
                    runCatching {
                        apiCall {
                            container.api.recommendBook(
                                target.id,
                                RecommendRequest(
                                    topicSlug = null,
                                    classIds = classIds,
                                    studentIds = emptyList(),
                                    note = note,
                                ),
                            )
                        }
                    }
                        .onSuccess {
                            message = "Рекомендация отправлена"
                            recommendTarget = null
                            tick++
                        }
                        .onFailure { message = it.message }
                }
            },
        )
    }

    val deleting = deleteTarget
    if (deleting != null) {
        AlertDialog(
            onDismissRequest = { deleteTarget = null },
            title = { Text("Удалить книгу?") },
            text = { Text("«${deleting.displayTitle}» будет убрана из вашей библиотеки.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        deleteTarget = null
                        scope.launch {
                            runCatching { apiCall { container.api.deleteTeacherBook(deleting.id) } }
                                .onSuccess { message = "Книга удалена"; tick++ }
                                .onFailure { message = it.message }
                        }
                    },
                ) { Text("Удалить") }
            },
            dismissButton = { TextButton(onClick = { deleteTarget = null }) { Text("Отмена") } },
        )
    }
}

@Composable
private fun TeacherTextbooksTab(container: AppContainer) {
    val scope = rememberCoroutineScope()
    var searchInput by remember { mutableStateOf("") }
    var search by remember { mutableStateOf("") }
    var tick by remember { mutableStateOf(0) }
    var message by remember { mutableStateOf<String?>(null) }
    var addTarget by remember { mutableStateOf<TextbookDto?>(null) }

    Load(
        key = "teacher-textbooks:$search:$tick",
        block = { container.api.teacherTextbooks(null, null, search.ifBlank { null }) },
    ) { data, refresh ->
        Column(Modifier.fillMaxSize()) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(
                    value = searchInput,
                    onValueChange = { searchInput = it },
                    label = { Text("Поиск пособия") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                Button(onClick = { search = searchInput.trim() }) { Text("Найти") }
            }

            if (message != null) {
                Column(Modifier.padding(horizontal = 16.dp)) { InfoBox(message!!) }
            }

            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (data.textbooks.isEmpty()) {
                    item { EmptyBox("Пособий нет. Загрузите PDF на сайте или через администратора.", "📄") }
                }
                items(data.textbooks) { textbook ->
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                            Text(textbook.title ?: "Пособие", fontWeight = FontWeight.SemiBold)
                            Text(
                                listOfNotNull(
                                    textbook.author,
                                    if (textbook.grade > 0) "${textbook.grade} класс" else null,
                                    if (textbook.pages > 0) "${textbook.pages} стр." else null,
                                ).joinToString(" · "),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                OutlinedButton(onClick = { addTarget = textbook }) {
                                    Text("В библиотеку")
                                }
                                if (textbook.pages > 0) {
                                    Text(
                                        "${textbook.topicsCount} тем",
                                        style = MaterialTheme.typography.bodySmall,
                                        modifier = Modifier.align(Alignment.CenterVertically),
                                    )
                                }
                            }
                        }
                    }
                }
                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }

    val target = addTarget
    if (target != null) {
        ClassPickerDialog(
            title = "Добавить «${target.title ?: "пособие"}»",
            classes = emptyList(),
            loadClasses = { apiCall { container.api.teacherLibrary(null, null, null) }.classes },
            onDismiss = { addTarget = null },
            onConfirm = { classIds, _ ->
                scope.launch {
                    runCatching {
                        apiCall {
                            container.api.createTeacherBook(
                                mapOf(
                                    "textbook_id" to target.id,
                                    "class_ids" to classIds,
                                ),
                            )
                        }
                    }
                        .onSuccess {
                            message = "Книга добавлена в библиотеку"
                            addTarget = null
                            tick++
                        }
                        .onFailure { message = it.message }
                }
            },
        )
    }
}

@Composable
private fun ClassPickerDialog(
    title: String,
    classes: List<ClassDto>,
    loadClasses: suspend () -> List<ClassDto>,
    onDismiss: () -> Unit,
    onConfirm: (List<Int>, String) -> Unit,
) {
    var loaded by remember { mutableStateOf(classes) }
    var error by remember { mutableStateOf<String?>(null) }
    val selected = remember { mutableStateListOf<Int>() }
    var note by remember { mutableStateOf("") }

    if (loaded.isEmpty() && error == null) {
        androidx.compose.runtime.LaunchedEffect(Unit) {
            runCatching { loadClasses() }
                .onSuccess { loaded = it }
                .onFailure { error = it.message }
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Кому", style = MaterialTheme.typography.labelLarge)
                if (error != null) {
                    Text(error!!, color = MaterialTheme.colorScheme.error)
                }
                if (loaded.isEmpty()) {
                    Text(
                        "Нет доступных классов. Рекомендацию можно отправить ученику на сайте.",
                        style = MaterialTheme.typography.bodySmall,
                    )
                } else {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        items(loaded) { klass ->
                            FilterChip(
                                selected = klass.id in selected,
                                onClick = {
                                    if (klass.id in selected) selected.remove(klass.id)
                                    else selected.add(klass.id)
                                },
                                label = { Text(klass.displayTitle) },
                            )
                        }
                    }
                }
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("Заметка (необязательно)") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(selected.toList(), note) }) { Text("Отправить") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Отмена") } },
    )
}
