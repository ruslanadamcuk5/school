package com.edumath.uchus.ui.student

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.net.Uri
import android.provider.MediaStore
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContract
import androidx.activity.result.contract.ActivityResultContracts
import androidx.core.content.FileProvider
import androidx.exifinterface.media.ExifInterface
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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.ApiJson
import com.edumath.uchus.data.api.AssignmentDetailDto
import com.edumath.uchus.data.api.AssignmentDto
import com.edumath.uchus.data.api.QuestionDto
import com.edumath.uchus.data.api.ResultSummaryDto
import com.edumath.uchus.data.api.StepResultDto
import com.edumath.uchus.data.api.SubmitRequest
import com.edumath.uchus.data.api.SubmitResponse
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.EmptyBox
import com.edumath.uchus.ui.common.ErrorBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.Speaker
import com.edumath.uchus.ui.common.Tag
import com.edumath.uchus.ui.teacher.TeacherAssignmentsScreen
import java.io.File
import kotlinx.coroutines.launch
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody
import okhttp3.RequestBody.Companion.toRequestBody

@Composable
fun AssignmentsScreen(
    container: AppContainer,
    role: String?,
    onBack: () -> Unit,
    onOpen: (Int) -> Unit,
    onResults: (Int) -> Unit = onOpen,
    onCreate: () -> Unit = {},
) {
    when (role) {
        "teacher", "admin" -> TeacherAssignmentsScreen(container, onBack, onResults, onCreate)
        "parent" -> ParentAssignmentsScreen(container, onBack)
        else -> StudentAssignmentsScreen(container, onBack, onOpen)
    }
}

@Composable
private fun StudentAssignmentsScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onOpen: (Int) -> Unit,
) {
    ScreenScaffold(title = "Работы", onBack = onBack) { padding ->
        Load(key = "assignments", block = { container.api.studentAssignments() }) { data, _ ->
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (data.assignments.isEmpty()) {
                    item { EmptyBox("Пока нет опубликованных работ.", "📝") }
                }
                items(data.assignments) { item ->
                    AssignmentCard(item) { onOpen(item.id) }
                }
                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }
}

@Composable
private fun ParentAssignmentsScreen(
    container: AppContainer,
    onBack: () -> Unit,
) {
    ScreenScaffold(title = "Домашние задания", onBack = onBack) { padding ->
        Load(key = "parent-assignments", block = { container.api.parentAssignments() }) { data, _ ->
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item {
                    InfoBox("Родительские задания создаются на сайте или в разделе «Дети».")
                }
                if (data.assignments.isEmpty()) {
                    item { EmptyBox("Вы ещё не назначали заданий.", "📝") }
                }
                items(data.assignments) { item ->
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    item.displayTitle,
                                    fontWeight = FontWeight.SemiBold,
                                    modifier = Modifier.weight(1f),
                                )
                                Tag(item.status ?: "—")
                            }
                            Text(
                                "${item.questionsCount} заданий · ${item.kind ?: ""}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Text(
                                "Сдали: ${item.results.size}",
                                style = MaterialTheme.typography.bodySmall,
                            )
                        }
                    }
                }
                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }
}

@Composable
fun AssignmentCard(item: AssignmentDto, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    item.displayTitle,
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                val result = item.result
                if (result != null) {
                    Tag("${result.score}/${result.maxScore} · ${result.grade} б.")
                } else {
                    Tag("не сдано")
                }
            }
            // Автор задания (от учителя / от родителя)
            val authorText = item.authorDisplay.takeIf { it.isNotBlank() }
            if (authorText != null) {
                Text(
                    authorText,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            Text(
                listOfNotNull(
                    taskTypeLabel(item.taskType ?: "test"),
                    item.dueDate?.takeIf { it.isNotBlank() }?.let { "до $it" },
                ).joinToString(" · "),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (!item.description.isNullOrBlank()) {
                Text(item.description ?: "", style = MaterialTheme.typography.bodySmall)
            }
        }
    }
}

@Composable
fun AssignmentDetailScreen(
    container: AppContainer,
    assignmentId: Int,
    onBack: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var submitted by remember { mutableStateOf<SubmitResponse?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    ScreenScaffold(title = "Работа", onBack = onBack) { padding ->
        val response = submitted
        if (response != null) {
            ResultScreen(
                title = "Работа сдана",
                result = response.result,
                details = response.details,
                padding = padding,
                onBack = onBack,
            )
            return@ScreenScaffold
        }

        Load(
            key = "assignment:$assignmentId",
            block = { container.api.assignment(assignmentId) },
        ) { data, _ ->
            if (data.submitted) {
                ResultScreen(
                    title = data.assignment?.displayTitle ?: "Результат",
                    result = data.result,
                    details = data.details,
                    padding = padding,
                    onBack = onBack,
                )
            } else {
                AssignmentForm(
                    data = data,
                    padding = padding,
                    busy = busy,
                    error = error,
                    onSubmit = { answers, photos ->
                        if (!busy) {
                            busy = true
                            scope.launch {
                                runCatching {
                                    apiCall {
                                        if (photos.isEmpty()) {
                                            container.api.submitAssignment(
                                                assignmentId,
                                                SubmitRequest(answers),
                                            )
                                        } else {
                                            val parts = photos.map { file ->
                                                val mime = if (file.extension.equals("png", true)) {
                                                    "image/png"
                                                } else {
                                                    "image/jpeg"
                                                }
                                                MultipartBody.Part.createFormData(
                                                    "photos",
                                                    file.name,
                                                    file.asRequestBody(mime.toMediaType()),
                                                )
                                            }
                                            container.api.submitAssignmentPhoto(
                                                assignmentId,
                                                ApiJson.gson.toJson(answers)
                                                    .toRequestBody("application/json".toMediaType()),
                                                parts,
                                                "0".toRequestBody("text/plain".toMediaType()),
                                            )
                                        }
                                    }
                                }
                                    .onSuccess { submitted = it; error = null }
                                    .onFailure { error = it.message }
                                busy = false
                            }
                        }
                    },
                )
            }
        }
    }
}

@Composable
private fun AssignmentForm(
    data: AssignmentDetailDto,
    padding: PaddingValues,
    busy: Boolean,
    error: String?,
    onSubmit: (List<String>, List<File>) -> Unit,
) {
    val context = LocalContext.current
    val speaker = remember { Speaker(context) }
    DisposableEffect(Unit) {
        onDispose { speaker.shutdown() }
    }

    val questions = data.questions
    val answers = remember(data) {
        mutableStateListOf<String>().apply { repeat(questions.size) { add("") } }
    }
    val photos = remember(data) { mutableStateListOf<File>() }
    val taskType = data.assignment?.taskType
        ?: questions.firstOrNull()?.taskType
        ?: "test"
    val allowText = data.assignment?.allowText ?: true
    val allowPhoto = data.assignment?.allowPhoto ?: true

    var pendingCameraFile by remember { mutableStateOf<File?>(null) }
    val camera = rememberLauncherForActivityResult(
        TakeAnswerPhoto()
    ) { success ->
        val file = pendingCameraFile
        pendingCameraFile = null
        if (success && file != null) {
            normalizePhoto(file)?.let { photos.add(it) }
        }
    }
    val gallery = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent()
    ) { uri ->
        if (uri != null) {
            copyToCache(context, uri)?.let { normalizePhoto(it) }?.let { photos.add(it) }
        }
    }

    val answered = answers.count { it.isNotBlank() }
    val textReady = when {
        !allowText -> false
        taskType == "test" -> answers.all { it.isNotBlank() }
        taskType == "read" -> true
        else -> answers.any { it.isNotBlank() }
    }
    val canSubmit = taskType == "read" || photos.isNotEmpty() || textReady

    fun speakAll() {
        val parts = mutableListOf<String>()
        data.assignment?.description
            ?.takeIf { it.isNotBlank() }
            ?.let { parts.add(it) }
        data.questions.forEach { question ->
            val text = if (question.taskType == "dictation") {
                question.audioText.orEmpty()
            } else {
                question.question
            }
            if (text.isNotBlank()) parts.add(text)
        }
        speaker.speak(parts.joinToString(". "))
    }

    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .padding(padding),
        contentPadding = PaddingValues(16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        item {
            Text(
                data.assignment?.displayTitle ?: "Работа",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            Text(
                taskTypeLabel(taskType),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
            )
            if (!data.assignment?.description.isNullOrBlank()) {
                Text(
                    data.assignment?.description ?: "",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { speakAll() }) {
                    Text("🔊 Озвучить задание")
                }
                if (speaker.speaking) {
                    TextButton(onClick = { speaker.stop() }) { Text("Остановить") }
                }
            }
            if (speaker.error != null) {
                Text(
                    speaker.error ?: "",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }

        if (error != null) {
            item { ErrorBox(error) }
        }

        items(questions) { question ->
            val index = question.index
            QuestionCard(
                question = question,
                value = answers.getOrNull(index) ?: "",
                allowText = allowText,
                onChange = { value -> if (index in answers.indices) answers[index] = value },
                onSpeak = {
                    val text = question.audioText?.takeIf { it.isNotBlank() }
                        ?: question.contentText?.takeIf { it.isNotBlank() }
                        ?: question.question
                    speaker.speak(text)
                },
            )
        }

        if (allowPhoto) {
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(
                        Modifier.padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text("📷 Фото письменного ответа", fontWeight = FontWeight.SemiBold)
                        Text(
                            "Сфотографируйте листок с решением. ИИ прочитает фото и укажет на ошибки. До 6 фото.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedButton(
                                onClick = {
                                    val file = File(
                                        context.cacheDir,
                                        "answer_${System.currentTimeMillis()}.jpg",
                                    )
                                    pendingCameraFile = file
                                    val uri = FileProvider.getUriForFile(
                                        context,
                                        "${context.packageName}.fileprovider",
                                        file,
                                    )
                                    camera.launch(uri)
                                },
                            ) {
                                Text("Сфотографировать")
                            }
                            OutlinedButton(onClick = { gallery.launch("image/*") }) {
                                Text("Из галереи")
                            }
                        }
                        photos.forEachIndexed { photoIndex, file ->
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    file.name,
                                    style = MaterialTheme.typography.bodySmall,
                                    modifier = Modifier.weight(1f),
                                )
                                TextButton(onClick = { photos.removeAt(photoIndex) }) {
                                    Text("Удалить")
                                }
                            }
                        }
                    }
                }
            }
        }

        item {
            Text(
                if (taskType == "read") {
                    "Отмечено как прочитано: можно отправлять"
                } else {
                    "Отвечено: $answered из ${questions.size}" +
                        if (photos.isNotEmpty()) " · фото: ${photos.size}" else ""
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }

        item {
            Button(
                onClick = { onSubmit(answers.toList(), photos.toList()) },
                enabled = !busy && canSubmit,
                modifier = Modifier.fillMaxWidth(),
            ) { Text(if (busy) "Отправляем…" else "Сдать работу") }
        }

        item { Spacer(Modifier.height(16.dp)) }
    }
}

private fun taskTypeLabel(type: String): String = when (type) {
    "read" -> "Чтение темы"
    "dictation" -> "Диктант"
    "other" -> "Задание"
    else -> "Тест"
}

@Composable
private fun QuestionCard(
    question: QuestionDto,
    value: String,
    allowText: Boolean,
    onChange: (String) -> Unit,
    onSpeak: () -> Unit,
) {
    val taskType = question.taskType ?: "test"
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "${question.index + 1}. ${question.question}",
                    fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.weight(1f),
                )
                TextButton(onClick = onSpeak) { Text("🔊") }
            }

            if (taskType == "read") {
                if (!question.contentText.isNullOrBlank()) {
                    Text(
                        question.contentText ?: "",
                        style = MaterialTheme.typography.bodyMedium,
                    )
                } else {
                    Text(
                        "Откройте тему в учебнике и прочитайте её.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            if (taskType == "dictation") {
                Text(
                    "🎧 Диктант читает устройство. Нажмите «🔊», запишите текст в тетрадь или введите ниже. Текст диктанта не показывается до проверки.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            if (allowText) {
                when (taskType) {
                    "read" -> {
                        OutlinedTextField(
                            value = value,
                            onValueChange = onChange,
                            label = { Text("Что запомнил(а)? (необязательно)") },
                            minLines = 2,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                    "dictation", "other" -> {
                        OutlinedTextField(
                            value = value,
                            onValueChange = onChange,
                            label = { Text("Ответ") },
                            minLines = 6,
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                    else -> {
                        if (question.choices.isNotEmpty()) {
                            question.choices.forEach { choice ->
                                if (choice == value) {
                                    Button(
                                        onClick = { onChange(choice) },
                                        modifier = Modifier.fillMaxWidth(),
                                    ) { Text(choice) }
                                } else {
                                    OutlinedButton(
                                        onClick = { onChange(choice) },
                                        modifier = Modifier.fillMaxWidth(),
                                    ) { Text(choice) }
                                }
                            }
                        } else {
                            OutlinedTextField(
                                value = value,
                                onValueChange = onChange,
                                label = { Text("Ответ") },
                                singleLine = true,
                                keyboardOptions = KeyboardOptions(
                                    keyboardType = KeyboardType.Number
                                ),
                                modifier = Modifier.fillMaxWidth(),
                            )
                        }
                    }
                }
            } else if (taskType == "test" && question.choices.isNotEmpty()) {
                Text(
                    "Ответьте на листке и прикрепите фото.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

private const val MAX_PHOTO_BYTES = 8 * 1024 * 1024

/** Камера с записью в FileProvider-URI: контракту нужен явный grant. */
private class TakeAnswerPhoto : ActivityResultContract<Uri, Boolean>() {
    override fun createIntent(context: Context, input: Uri): Intent =
        Intent(MediaStore.ACTION_IMAGE_CAPTURE)
            .putExtra(MediaStore.EXTRA_OUTPUT, input)
            .addFlags(
                Intent.FLAG_GRANT_READ_URI_PERMISSION or
                    Intent.FLAG_GRANT_WRITE_URI_PERMISSION
            )

    override fun parseResult(resultCode: Int, intent: Intent?): Boolean =
        resultCode == Activity.RESULT_OK
}

private fun normalizePhoto(file: File): File? {
    if (file.length() <= 0L) return null
    return runCatching {
        val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
        BitmapFactory.decodeFile(file.absolutePath, bounds)
        var sample = 1
        while (
            bounds.outWidth / sample > 2400 ||
            bounds.outHeight / sample > 2400
        ) {
            sample *= 2
        }
        val options = BitmapFactory.Options().apply { inSampleSize = sample }
        val bitmap = BitmapFactory.decodeFile(file.absolutePath, options)
            ?: return@runCatching null
        val exif = runCatching { ExifInterface(file.absolutePath) }.getOrNull()
        val angle = when (exif?.getAttributeInt(
            ExifInterface.TAG_ORIENTATION,
            ExifInterface.ORIENTATION_NORMAL,
        )) {
            ExifInterface.ORIENTATION_ROTATE_90 -> 90f
            ExifInterface.ORIENTATION_ROTATE_180 -> 180f
            ExifInterface.ORIENTATION_ROTATE_270 -> 270f
            else -> 0f
        }
        val oriented = if (angle != 0f) {
            Bitmap.createBitmap(
                bitmap,
                0,
                0,
                bitmap.width,
                bitmap.height,
                Matrix().apply { postRotate(angle) },
                true,
            ).also { if (it !== bitmap) bitmap.recycle() }
        } else {
            bitmap
        }
        val output = File(file.parentFile, "norm_${file.name}")
        output.outputStream().use { stream ->
            oriented.compress(Bitmap.CompressFormat.JPEG, 84, stream)
        }
        oriented.recycle()
        file.delete()
        output.takeIf { it.length() in 1..MAX_PHOTO_BYTES }
    }.getOrNull()
}

private fun copyToCache(context: Context, uri: Uri): File? = runCatching {
    val mime = context.contentResolver.getType(uri) ?: "image/jpeg"
    val extension = when {
        mime.contains("png") -> "png"
        mime.contains("webp") -> "webp"
        else -> "jpg"
    }
    val file = File(context.cacheDir, "answer_${System.currentTimeMillis()}.$extension")
    context.contentResolver.openInputStream(uri)?.use { input ->
        file.outputStream().use { output -> input.copyTo(output) }
    }
    file.takeIf { it.length() > 0 }
}.getOrNull()

@Composable
fun ResultScreen(
    title: String,
    result: ResultSummaryDto?,
    details: List<StepResultDto>,
    padding: PaddingValues,
    onBack: () -> Unit,
) {
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
                    Modifier
                        .fillMaxWidth()
                        .padding(20.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                    if (result != null) {
                        Text(
                            "${result.score} из ${result.maxScore}",
                            style = MaterialTheme.typography.headlineMedium,
                        )
                        Text(
                            "${result.percent}% · оценка ${result.grade}",
                            style = MaterialTheme.typography.titleMedium,
                        )
                        if (!result.completedAt.isNullOrBlank()) {
                            Text(
                                result.completedAt ?: "",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        }

        if (!result?.aiFeedback.isNullOrBlank()) {
            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text("🤖 Проверка ИИ", fontWeight = FontWeight.SemiBold)
                            result?.aiScore?.let { score ->
                                Spacer(Modifier.width(8.dp))
                                Tag("$score%")
                            }
                        }
                        Text(
                            result?.aiFeedback ?: "",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        if (!result?.aiModel.isNullOrBlank()) {
                            Text(
                                "Модель: ${result?.aiModel}",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        } else if (result?.aiStatus == "failed") {
            item {
                InfoBox("ИИ не смог проверить работу. Учитель увидит ответ и проверит его.")
            }
        }

        if (details.isNotEmpty()) {
            item { SectionTitle("Разбор") }
            items(details) { item ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(if (item.correct) "✅" else "❌")
                            Spacer(Modifier.width(6.dp))
                            Text(item.question, style = MaterialTheme.typography.bodyMedium)
                        }
                        if (item.taskType == "read") {
                            Text(
                                "Тема отмечена как прочитанная.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        } else {
                            Text(
                                "ваш ответ: ${item.given.ifBlank { "—" }}" +
                                    (item.answer ?: item.expected)
                                        .takeIf { it.isNotBlank() }
                                        ?.let { " · верный: $it" }
                                        .orEmpty(),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        if (!item.solution.isNullOrBlank()) {
                            Text(item.solution ?: "", style = MaterialTheme.typography.labelSmall)
                        }
                        if (!item.aiComment.isNullOrBlank()) {
                            Text(
                                "🤖 ${item.aiComment}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.primary,
                            )
                        }
                    }
                }
            }
        }

        item {
            Button(onClick = onBack, modifier = Modifier.fillMaxWidth()) { Text("Назад") }
        }
        item { Spacer(Modifier.height(16.dp)) }
    }
}
