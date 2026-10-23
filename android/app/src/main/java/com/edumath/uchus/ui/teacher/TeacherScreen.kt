package com.edumath.uchus.ui.teacher

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
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.AlertDialog
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
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
import com.edumath.uchus.data.api.ClassDto
import com.edumath.uchus.data.api.ScheduleDto
import com.edumath.uchus.data.api.ScheduleItemDto
import com.edumath.uchus.data.api.StudentCardDto
import com.edumath.uchus.data.api.SubjectDto
import com.edumath.uchus.data.api.TeacherDashboardDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.EmptyBox
import com.edumath.uchus.ui.common.ErrorBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.KeyValue
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.LoadingBox
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.StatsRow
import com.edumath.uchus.ui.common.Tag
import kotlinx.coroutines.launch

@Composable
fun TeacherDashboardScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onClass: (Int) -> Unit,
    onStudent: (Int) -> Unit,
    onAssignments: () -> Unit,
) {
    ScreenScaffold(title = "Кабинет учителя", onBack = onBack) { padding ->
        Load(key = "teacher-dashboard", block = { container.api.teacherDashboard() }) { data, _ ->
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item { DashboardStats(data) }

                item {
                    Button(onClick = onAssignments, modifier = Modifier.fillMaxWidth()) {
                        Text("Работы и задания")
                    }
                }

                item { SectionTitle("Мои классы", trailing = "${data.classes.size}") }
                if (data.classes.isEmpty()) {
                    item { InfoBox("Классы не назначены. Администратор может назначить вас классным руководителем.") }
                }
                items(data.classes) { klass ->
                    ClassRow(klass) { onClass(klass.id) }
                }

                item { SectionTitle("Ученики", trailing = "${data.stats.students}") }
                items(data.students) { student ->
                    StudentRow(student) { onStudent(student.id) }
                }

                item { SectionTitle("Последние работы", trailing = "${data.stats.assignments}") }
                if (data.recentAssignments.isEmpty()) {
                    item { EmptyBox("Работ пока нет.", "📝") }
                }
                items(data.recentAssignments) { item ->
                    Card(Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                item.displayTitle,
                                modifier = Modifier.weight(1f),
                                fontWeight = FontWeight.Medium,
                            )
                            Tag(item.status ?: "—")
                        }
                    }
                }

                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }
}

@Composable
private fun DashboardStats(data: TeacherDashboardDto) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        StatsRow(
            "классы" to "${data.stats.classes}",
            "ученики" to "${data.stats.students}",
        )
        StatsRow(
            "работы" to "${data.stats.assignments}",
            "открыто" to "${data.stats.openAssignments}",
        )
    }
}

@Composable
private fun ClassRow(klass: ClassDto, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("🏫", fontSize = 24.sp)
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(klass.displayTitle, fontWeight = FontWeight.SemiBold)
                Text(
                    listOfNotNull(klass.schoolName, klass.cityName).joinToString(" · "),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Tag("${klass.studentsCount} чел.")
        }
    }
}

@Composable
fun StudentRow(student: StudentCardDto, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(student.learner?.emoji ?: "👤", fontSize = 24.sp)
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(student.displayName, fontWeight = FontWeight.Medium)
                val stats = student.stats
                Text(
                    if (stats != null) {
                        "ур. ${stats.level} · ${stats.xp} опыта · ${stats.accuracy}% точность"
                    } else {
                        "нет профиля ученика"
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text("→", style = MaterialTheme.typography.titleMedium)
        }
    }
}

@Composable
fun TeacherClassScreen(
    container: AppContainer,
    classId: Int,
    onBack: () -> Unit,
    onStudent: (Int) -> Unit,
) {
    ScreenScaffold(title = "Класс", onBack = onBack) { padding ->
        Load(key = "teacher-class:$classId", block = { container.api.teacherClass(classId) }) { data, _ ->
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item {
                    Text(
                        data.klass?.displayTitle ?: "Класс",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        listOfNotNull(data.klass?.schoolName, data.klass?.cityName)
                            .joinToString(" · "),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }

                item { SectionTitle("Ученики", trailing = "${data.students.size}") }
                if (data.students.isEmpty()) {
                    item { InfoBox("В классе пока нет учеников.") }
                }
                items(data.students) { student ->
                    StudentRow(student) { onStudent(student.id) }
                }

                item { SectionTitle("Работы", trailing = "${data.assignments.size}") }
                if (data.assignments.isEmpty()) {
                    item { InfoBox("Работ для этого класса нет.") }
                }
                items(data.assignments) { item ->
                    Card(Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(item.displayTitle, modifier = Modifier.weight(1f))
                            Tag(item.status ?: "—")
                        }
                    }
                }

                item { SectionTitle("Расписание") }
                if (data.schedule.isEmpty()) {
                    item { InfoBox("Расписание не заполнено.") }
                }
                items(data.schedule) { lesson ->
                    Card(Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(12.dp)) {
                            Tag("${weekdayName(lesson.weekday)}, ${lesson.lessonNo}")
                            Spacer(Modifier.width(8.dp))
                            Text(
                                (lesson.subjectIcon ?: "") + " " + (lesson.subjectName ?: "Урок"),
                                modifier = Modifier.weight(1f),
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
fun TeacherStudentsScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onStudent: (Int) -> Unit,
) {
    var query by remember { mutableStateOf("") }

    ScreenScaffold(title = "Ученики", onBack = onBack) { padding ->
        Load(key = "teacher-students", block = { container.api.teacherStudents() }) { data, _ ->
            val visible = data.students.filter {
                query.isBlank() ||
                    it.displayName.contains(query, ignoreCase = true) ||
                    (it.login ?: "").contains(query, ignoreCase = true)
            }
            Column(
                Modifier
                    .fillMaxSize()
                    .padding(padding),
            ) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    label = { Text("Поиск по имени или логину") },
                    singleLine = true,
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(16.dp),
                )
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    if (visible.isEmpty()) {
                        item { EmptyBox("Ученики не найдены.", "🔎") }
                    }
                    items(visible) { student ->
                        StudentRow(student) { onStudent(student.id) }
                    }
                    item { Spacer(Modifier.height(16.dp)) }
                }
            }
        }
    }
}

@Composable
fun TeacherStudentScreen(
    container: AppContainer,
    studentId: Int,
    onBack: () -> Unit,
) {
    ScreenScaffold(title = "Ученик", onBack = onBack) { padding ->
        Load(key = "teacher-student:$studentId", block = { container.api.teacherStudent(studentId) }) { data, _ ->
            val playful = (data.learner?.grade ?: 0) in 1..4
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                item {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(data.learner?.emoji ?: "👤", fontSize = 36.sp)
                        Spacer(Modifier.width(12.dp))
                        Column {
                            Text(
                                data.student?.displayName ?: "Ученик",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Bold,
                            )
                            Text(
                                "логин: ${data.student?.login ?: "—"}",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            data.classes.firstOrNull()?.let { klass ->
                                Tag(klass.displayTitle)
                            }
                        }
                    }
                }

                item {
                    data.stats?.let { stats ->
                        if (playful) {
                            StatsRow(
                                "уровень" to "${stats.level}",
                                "опыт" to "${stats.xp}",
                                "монеты" to "${stats.coins}",
                                "серия" to "${stats.streakDays}",
                            )
                        } else {
                            StatsRow(
                                "точность" to "${stats.accuracy}%",
                                "попыток" to "${stats.totalAttempts}",
                                "серия" to "${stats.streakDays}",
                            )
                        }
                    }
                }

                item {
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(14.dp)) {
                            data.stats?.let { stats ->
                                KeyValue("Точность", "${stats.accuracy}%")
                                KeyValue("Попыток", "${stats.totalAttempts}")
                                KeyValue("Верных", "${stats.totalCorrect}")
                            }
                            data.learner?.let { learner ->
                                KeyValue("Класс профиля", "${learner.grade}")
                            }
                        }
                    }
                }

                item { SectionTitle("Активность за неделю") }
                item {
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            if (data.weekly.isEmpty()) {
                                Text(
                                    "Нет попыток за неделю.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            data.weekly.forEach { day ->
                                KeyValue(day.day, "${day.correct} из ${day.attempts}")
                            }
                        }
                    }
                }

                item { SectionTitle("Темы", trailing = "${data.topics.size}") }
                items(data.topics) { topic ->
                    Card(Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(topic.slug, modifier = Modifier.weight(1f))
                            if (playful) {
                                Text(starsText(topic.stars))
                                Spacer(Modifier.width(8.dp))
                            }
                            Tag("${topic.correct}/${topic.attempts}")
                        }
                    }
                }

                item { SectionTitle("Результаты работ", trailing = "${data.results.size}") }
                items(data.results) { result ->
                    Card(Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(result.title ?: "Работа", modifier = Modifier.weight(1f))
                            Tag("${result.score}/${result.maxScore}")
                        }
                    }
                }

                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }
}

@Composable
fun TeacherScheduleScreen(
    container: AppContainer,
    onBack: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var classes by remember { mutableStateOf<List<ClassDto>>(emptyList()) }
    var subjects by remember { mutableStateOf<List<SubjectDto>>(emptyList()) }
    var selected by remember { mutableStateOf<ClassDto?>(null) }
    var schedule by remember { mutableStateOf<ScheduleDto?>(null) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var showDialog by remember { mutableStateOf(false) }
    var message by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        runCatching {
            val loadedClasses = apiCall { container.api.teacherClasses() }.classes
            val meta = apiCall { container.api.meta() }
            classes = loadedClasses
            subjects = meta.subjects
            selected = loadedClasses.firstOrNull()
        }.onFailure { error = it.message }
        loading = false
    }

    LaunchedEffect(selected?.id) {
        val classId = selected?.id ?: return@LaunchedEffect
        runCatching { apiCall { container.api.teacherSchedule(classId) } }
            .onSuccess { schedule = it }
            .onFailure { error = it.message }
    }

    ScreenScaffold(title = "Расписание", onBack = onBack) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            if (loading) {
                LoadingBox()
                return@Column
            }
            if (classes.isEmpty()) {
                InfoBox("У вас нет классов для расписания.")
                return@Column
            }

            LazyRow(
                contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(classes) { klass ->
                    FilterChip(
                        selected = selected?.id == klass.id,
                        onClick = { selected = klass; message = null },
                        label = { Text(klass.displayTitle) },
                    )
                }
            }

            if (message != null) {
                Column(Modifier.padding(horizontal = 16.dp)) { InfoBox(message!!) }
            }
            if (error != null) {
                Column(Modifier.padding(horizontal = 16.dp)) { ErrorBox(error!!) }
            }

            Row(Modifier.padding(horizontal = 16.dp, vertical = 8.dp)) {
                Button(onClick = { showDialog = true }, modifier = Modifier.fillMaxWidth()) {
                    Text("Добавить урок")
                }
            }

            val rows = buildScheduleRows(schedule)
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (rows.isEmpty()) {
                    item { EmptyBox("В расписании пока нет уроков.", "🗓") }
                }
                items(rows) { row ->
                    val (day, lesson) = row
                    if (lesson == null) {
                        SectionTitle(day)
                    } else {
                        Card(Modifier.fillMaxWidth()) {
                            Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                                Text("${lesson.lessonNo}", fontWeight = FontWeight.Bold)
                                Spacer(Modifier.width(10.dp))
                                Column(Modifier.weight(1f)) {
                                    Text(
                                        (lesson.subjectIcon ?: "") + " " + (lesson.subjectName ?: "Урок"),
                                        fontWeight = FontWeight.SemiBold,
                                    )
                                    val times = listOfNotNull(
                                        lesson.timeStart?.takeIf { it.isNotBlank() },
                                        lesson.timeEnd?.takeIf { it.isNotBlank() },
                                    ).joinToString("–")
                                    val subtitle = listOfNotNull(
                                        times.takeIf { it.isNotBlank() },
                                        lesson.note?.takeIf { it.isNotBlank() },
                                    ).joinToString(" · ")
                                    if (subtitle.isNotBlank()) {
                                        Text(
                                            subtitle,
                                            style = MaterialTheme.typography.bodySmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
                                }
                                TextButton(
                                    onClick = {
                                        val classId = selected?.id ?: return@TextButton
                                        scope.launch {
                                            runCatching { apiCall { container.api.deleteSchedule(lesson.id) } }
                                                .onSuccess {
                                                    message = "Урок удалён"
                                                    schedule = apiCall { container.api.teacherSchedule(classId) }
                                                }
                                                .onFailure { message = it.message }
                                        }
                                    },
                                ) { Text("Удалить", color = MaterialTheme.colorScheme.error) }
                            }
                        }
                    }
                }
                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }

    val klass = selected
    if (showDialog && klass != null) {
        ScheduleDialog(
            subjects = subjects,
            weekdays = schedule?.weekdays ?: defaultWeekdays,
            onDismiss = { showDialog = false },
            onSave = { weekday, lessonNo, subjectId, start, end, note ->
                scope.launch {
                    runCatching {
                        apiCall {
                            container.api.saveSchedule(
                                mapOf(
                                    "class_id" to klass.id,
                                    "weekday" to weekday,
                                    "lesson_no" to lessonNo,
                                    "subject_id" to subjectId,
                                    "time_start" to start,
                                    "time_end" to end,
                                    "note" to note,
                                ),
                            )
                        }
                    }
                        .onSuccess {
                            schedule = it
                            message = "Расписание сохранено"
                            showDialog = false
                        }
                        .onFailure { message = it.message }
                }
            },
        )
    }
}

private val defaultWeekdays = listOf("Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс")

private fun weekdayName(index: Int): String =
    defaultWeekdays.getOrNull(index) ?: "?"

private fun buildScheduleRows(
    schedule: ScheduleDto?,
): List<Pair<String, ScheduleItemDto?>> {
    if (schedule == null) return emptyList()
    val rows = mutableListOf<Pair<String, ScheduleItemDto?>>()
    schedule.weekdays.forEachIndexed { index, day ->
        val lessons = schedule.schedule.filter { it.weekday == index }.sortedBy { it.lessonNo }
        if (lessons.isNotEmpty()) {
            rows += day to null
            lessons.forEach { rows += "" to it }
        }
    }
    return rows
}

@Composable
private fun ScheduleDialog(
    subjects: List<SubjectDto>,
    weekdays: List<String>,
    onDismiss: () -> Unit,
    onSave: (Int, Int, Int?, String, String, String) -> Unit,
) {
    var weekday by remember { mutableStateOf(0) }
    var lessonNo by remember { mutableStateOf(1) }
    var subject by remember { mutableStateOf<SubjectDto?>(null) }
    var start by remember { mutableStateOf("") }
    var end by remember { mutableStateOf("") }
    var note by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Новый урок") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("День", style = MaterialTheme.typography.labelLarge)
                LazyRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    items(weekdays.indices.toList()) { index ->
                        FilterChip(
                            selected = weekday == index,
                            onClick = { weekday = index },
                            label = { Text(weekdays[index]) },
                        )
                    }
                }
                Text("Урок", style = MaterialTheme.typography.labelLarge)
                LazyRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    items((1..7).toList()) { number ->
                        FilterChip(
                            selected = lessonNo == number,
                            onClick = { lessonNo = number },
                            label = { Text("$number") },
                        )
                    }
                }
                if (subjects.isNotEmpty()) {
                    Text("Предмет", style = MaterialTheme.typography.labelLarge)
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        items(subjects) { item ->
                            FilterChip(
                                selected = subject?.id == item.id,
                                onClick = { subject = item },
                                label = { Text("${item.icon ?: ""} ${item.name ?: ""}") },
                            )
                        }
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = start,
                        onValueChange = { start = it },
                        label = { Text("Начало") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = end,
                        onValueChange = { end = it },
                        label = { Text("Конец") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                }
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("Тема или заметка") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(onClick = { onSave(weekday, lessonNo, subject?.id, start, end, note) }) {
                Text("Сохранить")
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Отмена") } },
    )
}

fun starsText(stars: Int): String {
    val filled = "★".repeat(stars.coerceIn(0, 3))
    val empty = "☆".repeat((3 - stars).coerceIn(0, 3))
    return filled + empty
}
