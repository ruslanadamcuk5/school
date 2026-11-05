package com.edumath.uchus.ui.student

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
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
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.EducationProfileDto
import com.edumath.uchus.data.api.EducationRequest
import com.edumath.uchus.data.api.OrgCatalogDto
import com.edumath.uchus.data.api.SubjectDto
import com.edumath.uchus.data.api.apiCall
import kotlinx.coroutines.launch

/**
 * Карточка «Учебное заведение» в профиле.
 *
 * Ученик выбирает одну связку город → школа → класс, учитель — несколько
 * классов одной школы и предметы для каждого класса.
 */
@Composable
fun EducationCard(
    container: AppContainer,
    role: String,
    onSaved: () -> Unit = {},
) {
    val isStudent = role == "student"
    val scope = rememberCoroutineScope()
    var profile by remember { mutableStateOf<EducationProfileDto?>(null) }
    var catalog by remember { mutableStateOf<OrgCatalogDto?>(null) }
    var cityId by remember { mutableStateOf<Int?>(null) }
    var schoolId by remember { mutableStateOf<Int?>(null) }
    var studentClassId by remember { mutableStateOf<Int?>(null) }
    var classIds by remember { mutableStateOf<Set<Int>>(emptySet()) }
    var subjectsByClass by remember { mutableStateOf<Map<Int, Set<Int>>>(emptyMap()) }
    var loading by remember { mutableStateOf(true) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var dialog by remember { mutableStateOf<String?>(null) }

    fun applyProfile(data: EducationProfileDto) {
        profile = data
        cityId = data.cityId
        schoolId = data.schoolId
        if (isStudent) {
            studentClassId = data.classId
        } else {
            classIds = data.classes.map { it.id }.toSet()
            subjectsByClass = data.classes.associate { klass ->
                klass.id to klass.subjects.map { it.id }.toSet()
            }
        }
    }

    LaunchedEffect(Unit) {
        runCatching { apiCall { container.api.educationProfile() } }
            .onSuccess { applyProfile(it) }
            .onFailure { error = it.message ?: "Не удалось загрузить учебное заведение" }
        loading = false
    }

    LaunchedEffect(cityId, schoolId) {
        runCatching { apiCall { container.api.orgCatalog(cityId, schoolId) } }
            .onSuccess { catalog = it }
    }

    fun chooseCity(id: Int) {
        cityId = id
        schoolId = null
        studentClassId = null
        classIds = emptySet()
        subjectsByClass = emptyMap()
        message = null
        error = null
    }

    fun chooseSchool(id: Int) {
        schoolId = id
        studentClassId = null
        classIds = emptySet()
        subjectsByClass = emptyMap()
        message = null
        error = null
    }

    fun toggleClass(id: Int) {
        classIds = if (classIds.contains(id)) classIds - id else classIds + id
        if (subjectsByClass[id] == null) {
            subjectsByClass = subjectsByClass + (id to emptySet())
        }
    }

    fun toggleSubject(classId: Int, subjectId: Int) {
        val current = subjectsByClass[classId] ?: emptySet()
        subjectsByClass = subjectsByClass + (
            classId to if (current.contains(subjectId)) current - subjectId else current + subjectId
            )
    }

    fun save() {
        val city = cityId
        val school = schoolId
        if (city == null || school == null) {
            error = "Выберите город и школу"
            return
        }
        if (isStudent && studentClassId == null) {
            error = "Выберите класс"
            return
        }
        scope.launch {
            busy = true
            error = null
            message = null
            try {
                val body = if (isStudent) {
                    EducationRequest(cityId = city, schoolId = school, classId = studentClassId)
                } else {
                    EducationRequest(
                        cityId = city,
                        schoolId = school,
                        classIds = classIds.toList(),
                        subjectsByClass = classIds.associate { id ->
                            id.toString() to (subjectsByClass[id] ?: emptySet()).toList()
                        },
                    )
                }
                val updated = apiCall { container.api.saveEducation(body) }
                applyProfile(updated)
                onSaved()
                message = "Сохранено"
            } catch (err: Exception) {
                error = err.message ?: "Не удалось сохранить учебное заведение"
            } finally {
                busy = false
            }
        }
    }

    val cities = catalog?.cities ?: emptyList()
    val schools = catalog?.schools ?: emptyList()
    val catalogClasses = (catalog?.classes ?: emptyList()).map {
        ClassOption(it.id, it.displayTitle)
    }
    val extraSelected = (profile?.classes ?: emptyList())
        .filter { klass ->
            catalogClasses.none { it.id == klass.id } &&
                (if (isStudent) klass.id == studentClassId else classIds.contains(klass.id))
        }
        .map { ClassOption(it.id, it.displayTitle) }
    val classes = catalogClasses + extraSelected
    val subjects = catalog?.subjects?.takeIf { it.isNotEmpty() }
        ?: profile?.subjects
        ?: emptyList()

    val cityName = cities.find { it.id == cityId }?.name ?: profile?.cityName
    val schoolName = schools.find { it.id == schoolId }?.name ?: profile?.schoolName
    val selectedStudentClass = classes.find { it.id == studentClassId }?.title
        ?: profile?.klass?.takeIf { it.id == studentClassId }?.displayTitle

    Card(Modifier.fillMaxWidth()) {
        Column(
            Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text("🏫 Учебное заведение", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
            Text(
                if (isStudent) {
                    "Выберите город, школу и класс — по ним учитель находит вас в своём классе."
                } else {
                    "Выберите город и школу, затем классы, которые вы ведёте, и предметы для каждого класса."
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )

            if (loading && profile == null) {
                Text("Загружаем данные об обучении…", style = MaterialTheme.typography.bodySmall)
            } else {
                SelectorRow("Город", cityName ?: "Выбрать город") { dialog = "city" }
                SelectorRow(
                    label = "Школа",
                    value = schoolName ?: if (cityId == null) "Сначала выберите город" else "Выбрать школу",
                    enabled = cityId != null,
                ) { dialog = "school" }

                if (isStudent) {
                    SelectorRow(
                        label = "Класс",
                        value = selectedStudentClass
                            ?: if (schoolId == null) "Сначала выберите школу" else "Выбрать класс",
                        enabled = schoolId != null,
                    ) { dialog = "class" }
                } else {
                    Text("Классы", style = MaterialTheme.typography.labelLarge)
                    if (classes.isEmpty()) {
                        Text(
                            if (schoolId == null) "Сначала выберите школу" else "В школе пока нет классов",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    } else {
                        LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            items(classes) { klass ->
                                FilterChip(
                                    selected = classIds.contains(klass.id),
                                    onClick = { toggleClass(klass.id) },
                                    label = { Text(klass.title) },
                                )
                            }
                        }
                    }

                    if (classIds.isNotEmpty()) {
                        Text(
                            "Предметы по классам",
                            style = MaterialTheme.typography.labelLarge,
                        )
                        classIds.sorted().forEach { id ->
                            val klass = classes.find { it.id == id }
                            Card(Modifier.fillMaxWidth()) {
                                Column(
                                    Modifier.padding(10.dp),
                                    verticalArrangement = Arrangement.spacedBy(6.dp),
                                ) {
                                    Text(
                                        klass?.title ?: "Класс №$id",
                                        style = MaterialTheme.typography.bodyMedium,
                                        fontWeight = FontWeight.SemiBold,
                                    )
                                    SubjectChips(
                                        subjects = subjects,
                                        selected = subjectsByClass[id] ?: emptySet(),
                                        onToggle = { subjectId -> toggleSubject(id, subjectId) },
                                    )
                                }
                            }
                        }
                    }
                }

                if (error != null) {
                    Text(
                        error!!,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                }
                if (message != null) {
                    Text(
                        message!!,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }

                Button(
                    onClick = { save() },
                    enabled = !busy && cityId != null && schoolId != null &&
                        (!isStudent || studentClassId != null),
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Text(if (busy) "Сохраняем…" else "Сохранить")
                }
            }
        }
    }

    if (dialog == "city") {
        ChoiceDialog(
            title = "Город",
            options = cities.map { it.id to (it.name ?: "") },
            onPick = { chooseCity(it); dialog = null },
            onDismiss = { dialog = null },
        )
    }
    if (dialog == "school") {
        ChoiceDialog(
            title = "Школа",
            options = schools.map { it.id to (it.name ?: "") },
            onPick = { chooseSchool(it); dialog = null },
            onDismiss = { dialog = null },
        )
    }
    if (dialog == "class") {
        ChoiceDialog(
            title = "Класс",
            options = classes.map { it.id to it.title },
            onPick = {
                studentClassId = it
                dialog = null
            },
            onDismiss = { dialog = null },
        )
    }
}

private data class ClassOption(val id: Int, val title: String)

@Composable
private fun SubjectChips(
    subjects: List<SubjectDto>,
    selected: Set<Int>,
    onToggle: (Int) -> Unit,
) {
    if (subjects.isEmpty()) {
        Text(
            "Предметы не загрузились",
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        return
    }
    LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        items(subjects) { subject ->
            FilterChip(
                selected = selected.contains(subject.id),
                onClick = { onToggle(subject.id) },
                label = { Text("${subject.icon ?: "📘"} ${subject.name ?: ""}") },
            )
        }
    }
}

@Composable
private fun SelectorRow(
    label: String,
    value: String,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(
            Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(Modifier.weight(1f)) {
                Text(
                    label,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Text(value, style = MaterialTheme.typography.bodyMedium)
            }
            Text("▾")
        }
    }
}

@Composable
private fun ChoiceDialog(
    title: String,
    options: List<Pair<Int, String>>,
    onPick: (Int) -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            if (options.isEmpty()) {
                Text("Список пуст")
            } else {
                LazyColumn(Modifier.heightIn(max = 360.dp)) {
                    items(options) { (id, name) ->
                        Text(
                            name,
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable { onPick(id) }
                                .padding(horizontal = 4.dp, vertical = 12.dp),
                            style = MaterialTheme.typography.bodyLarge,
                        )
                    }
                }
            }
        },
        confirmButton = {
            TextButton(onClick = onDismiss) { Text("Отмена") }
        },
    )
}
