package com.edumath.uchus.ui.padruchnik

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
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
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.ClassDto
import com.edumath.uchus.data.api.PadruchnikImportRequest
import com.edumath.uchus.data.api.PadruchnikItemDto
import com.edumath.uchus.data.api.SubjectDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.EmptyBox
import com.edumath.uchus.ui.common.ErrorBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.LoadingBox
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import java.io.File
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Поиск пособий на национальном портале e-padruchnik.adu.by.
 *
 * Учитель сразу открывает импортированную книгу своим классам; администратор
 * может добавить пособие без классов, чтобы позже выдать его в библиотеке.
 */
@Composable
fun PadruchnikScreen(
    container: AppContainer,
    isTeacher: Boolean,
    onBack: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var query by remember { mutableStateOf("") }
    var grade by remember { mutableStateOf(0) }
    var page by remember { mutableStateOf(0) }
    var items by remember { mutableStateOf<List<PadruchnikItemDto>>(emptyList()) }
    var hasNext by remember { mutableStateOf(false) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var subjects by remember { mutableStateOf<List<SubjectDto>>(emptyList()) }
    var classes by remember { mutableStateOf<List<ClassDto>>(emptyList()) }
    var importTarget by remember { mutableStateOf<PadruchnikItemDto?>(null) }
    var notice by remember { mutableStateOf<String?>(null) }
    var uploadTarget by remember { mutableStateOf<UploadTarget?>(null) }
    var uploading by remember { mutableStateOf(false) }
    val context = LocalContext.current

    val pdfPicker = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri: Uri? ->
        val target = uploadTarget
        uploadTarget = null
        if (uri == null || target == null) return@rememberLauncherForActivityResult
        val file = copyPdfToCache(context, uri)
        if (file == null) {
            notice = "Не удалось прочитать выбранный файл"
            return@rememberLauncherForActivityResult
        }
        uploading = true
        notice = "Загружаем PDF и разбираем темы…"
        scope.launch {
            runCatching {
                apiCall {
                    container.api.padruchnikUpload(
                        MultipartBody.Part.createFormData(
                            "file",
                            file.name,
                            file.asRequestBody("application/pdf".toMediaType()),
                        ),
                        target.item.id.toString().toRequestBody(PLAIN_TEXT),
                        target.subjectId.toString().toRequestBody(PLAIN_TEXT),
                        target.grade.toString().toRequestBody(PLAIN_TEXT),
                        target.classIds.joinToString(",").toRequestBody(PLAIN_TEXT),
                    )
                }
            }.onSuccess { result ->
                notice = if (result.ok) {
                    "«${result.title ?: target.item.title}» добавлено: " +
                        "${result.pages} стр., тем — ${result.linked}."
                } else {
                    result.message ?: result.error ?: "Не удалось добавить пособие"
                }
            }.onFailure {
                notice = it.message ?: "Не удалось загрузить PDF"
            }
            uploading = false
            file.delete()
        }
    }

    LaunchedEffect(Unit) {
        runCatching { apiCall { container.api.padruchnikSubjects() } }
            .onSuccess { subjects = it.subjects }
        if (isTeacher) {
            runCatching { apiCall { container.api.teacherDashboard() } }
                .onSuccess { classes = it.classes }
        }
    }

    fun search(nextPage: Int = 0) {
        scope.launch {
            loading = true
            error = null
            runCatching {
                apiCall {
                    container.api.padruchnikSearch(
                        q = query.trim().ifBlank { null },
                        grade = grade.takeIf { it > 0 },
                        page = nextPage,
                    )
                }
            }.onSuccess { result ->
                page = nextPage
                items = if (nextPage == 0) result.items else items + result.items
                hasNext = result.hasNext
                if (!result.ok) error = result.error ?: "Портал недоступен"
            }.onFailure { error = it.message ?: "Не удалось выполнить поиск" }
            loading = false
        }
    }

    ScreenScaffold(title = "e-padruchnik", onBack = onBack) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(
                        Modifier.padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(
                            "Поиск на национальном портале e-padruchnik.adu.by",
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            "Импорт скачивает PDF и разбирает оглавление в темы. " +
                                "Занимает до минуты.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        OutlinedTextField(
                            value = query,
                            onValueChange = { query = it },
                            label = { Text("Название или автор") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }

            item {
                LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    item {
                        FilterChip(
                            selected = grade == 0,
                            onClick = { grade = 0 },
                            label = { Text("Любой класс") },
                        )
                    }
                    items((1..11).toList()) { value ->
                        FilterChip(
                            selected = grade == value,
                            onClick = { grade = if (grade == value) 0 else value },
                            label = { Text("$value") },
                        )
                    }
                }
            }

            item {
                Button(
                    onClick = { search(0) },
                    enabled = !loading,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (loading) "Ищем…" else "🔍 Найти пособия")
                }
            }

            if (uploading) {
                item { LoadingBox("Загружаем PDF и разбираем темы…") }
            }

            notice?.let { text ->
                item { InfoBox(text) }
            }

            error?.let { text ->
                item { ErrorBox(text) { search(page) } }
            }

            if (loading && items.isEmpty()) {
                item { LoadingBox("Запрашиваем портал…") }
            }

            if (!loading && items.isEmpty() && error == null) {
                item {
                    EmptyBox(
                        "Введите название и класс — платформа найдёт пособия на портале.",
                        "🌐",
                    )
                }
            }

            item {
                SectionTitle("Найдено", trailing = if (items.isEmpty()) null else "${items.size}")
            }

            items(items, key = { "${it.id}-${it.grade}-${it.year}" }) { item ->
                PadruchnikCard(item) { importTarget = item }
            }

            if (hasNext) {
                item {
                    OutlinedButton(
                        onClick = { search(page + 1) },
                        enabled = !loading,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text("Показать ещё")
                    }
                }
            }
        }
    }

    importTarget?.let { item ->
        ImportDialog(
            item = item,
            subjects = subjects,
            classes = classes,
            requireClasses = isTeacher,
            onDismiss = { importTarget = null },
            onPickFile = { subjectId, gradeValue, classIds ->
                uploadTarget = UploadTarget(item, subjectId, gradeValue, classIds)
                importTarget = null
                pdfPicker.launch("application/pdf")
            },
            onImport = { subjectId, gradeValue, classIds ->
                scope.launch {
                    runCatching {
                        apiCall {
                            container.api.padruchnikImport(
                                PadruchnikImportRequest(
                                    bookId = item.id,
                                    subjectId = subjectId,
                                    grade = gradeValue,
                                    classIds = classIds,
                                )
                            )
                        }
                    }.onSuccess { result ->
                        notice = if (result.ok) {
                            "«${result.title ?: item.title}» добавлено: " +
                                "${result.pages} стр., тем — ${result.linked}."
                        } else {
                            result.message ?: result.error ?: "Не удалось добавить пособие"
                        }
                        importTarget = null
                    }.onFailure {
                        notice = it.message ?: "Не удалось добавить пособие"
                        importTarget = null
                    }
                }
            },
        )
    }
}

@Composable
private fun PadruchnikCard(item: PadruchnikItemDto, onImport: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(
            Modifier.padding(14.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                item.title ?: "Без названия",
                fontWeight = FontWeight.SemiBold,
            )
            if (!item.author.isNullOrBlank()) {
                Text(
                    item.author!!,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                listOfNotNull(
                    item.grade.takeIf { it > 0 }?.let { "$it класс" },
                    item.year?.takeIf { it.isNotBlank() },
                    item.language?.takeIf { it.isNotBlank() },
                    item.level?.takeIf { it.isNotBlank() },
                ).joinToString(" · "),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Button(
                onClick = onImport,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 6.dp),
            ) {
                Text("📥 Добавить в пособия")
            }
        }
    }
}

@Composable
private fun ImportDialog(
    item: PadruchnikItemDto,
    subjects: List<SubjectDto>,
    classes: List<ClassDto>,
    requireClasses: Boolean,
    onDismiss: () -> Unit,
    onPickFile: (subjectId: Int, grade: Int, classIds: List<Int>) -> Unit,
    onImport: (subjectId: Int, grade: Int, classIds: List<Int>) -> Unit,
) {
    var subjectId by remember(item.id) { mutableStateOf(subjects.firstOrNull()?.id ?: 0) }
    var grade by remember(item.id) {
        mutableStateOf(item.grade.takeIf { it > 0 } ?: 3)
    }
    val chosen = remember(item.id) { mutableStateListOf<Int>() }
    var validation by remember(item.id) { mutableStateOf<String?>(null) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(item.title ?: "Добавить пособие") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Предмет", style = MaterialTheme.typography.labelLarge)
                if (subjects.isEmpty()) {
                    Text(
                        "Предметы не загрузились. Проверьте связь и откройте экран заново.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                } else {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        items(subjects) { subject ->
                            FilterChip(
                                selected = subjectId == subject.id,
                                onClick = { subjectId = subject.id },
                                label = { Text("${subject.icon ?: ""} ${subject.name ?: ""}".trim()) },
                            )
                        }
                    }
                }

                OutlinedTextField(
                    value = grade.toString(),
                    onValueChange = { value ->
                        grade = value.filter { it.isDigit() }.take(2).toIntOrNull() ?: 0
                    },
                    label = { Text("Класс пособия") },
                    singleLine = true,
                )

                if (classes.isNotEmpty()) {
                    Text(
                        if (requireClasses) "Открыть классам (обязательно)" else "Открыть классам",
                        style = MaterialTheme.typography.labelLarge,
                    )
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        items(classes) { klass ->
                            val selected = klass.id in chosen
                            FilterChip(
                                selected = selected,
                                onClick = {
                                    if (selected) chosen.remove(klass.id) else chosen.add(klass.id)
                                },
                                label = { Text(klass.displayTitle) },
                            )
                        }
                    }
                }

                validation?.let { text ->
                    Text(
                        text,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }

                OutlinedButton(
                    onClick = {
                        when {
                            subjectId == 0 -> validation = "Выберите предмет"
                            requireClasses && chosen.isEmpty() ->
                                validation = "Выберите хотя бы один класс"
                            else -> onPickFile(subjectId, grade, chosen.toList())
                        }
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("📎 PDF не скачивается? Выбрать файл") }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    if (subjectId == 0) {
                        validation = "Выберите предмет"
                        return@TextButton
                    }
                    if (requireClasses && chosen.isEmpty()) {
                        validation = "Выберите хотя бы один класс"
                        return@TextButton
                    }
                    onImport(subjectId, grade, chosen.toList())
                },
            ) { Text("Добавить") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Отмена") }
        },
    )
}


private val PLAIN_TEXT = "text/plain".toMediaType()

private data class UploadTarget(
    val item: PadruchnikItemDto,
    val subjectId: Int,
    val grade: Int,
    val classIds: List<Int>,
)

/** Скопировать выбранный PDF во временный файл, чтобы отправить его на сервер. */
private fun copyPdfToCache(context: android.content.Context, uri: Uri): File? = runCatching {
    val file = File(context.cacheDir, "padruchnik_${System.currentTimeMillis()}.pdf")
    context.contentResolver.openInputStream(uri)?.use { input ->
        file.outputStream().use { output -> input.copyTo(output) }
    }
    file.takeIf { it.length() > 0 }
}.getOrNull()
