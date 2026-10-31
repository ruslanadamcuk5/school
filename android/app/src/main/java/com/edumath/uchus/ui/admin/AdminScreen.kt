package com.edumath.uchus.ui.admin

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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.horizontalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.ScrollableTabRow
import androidx.compose.material3.Tab
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
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
import com.edumath.uchus.data.api.CreateCityRequest
import com.edumath.uchus.data.api.CreateClassRequest
import com.edumath.uchus.data.api.CreateSchoolRequest
import com.edumath.uchus.data.api.CreateUserRequest
import com.edumath.uchus.data.api.CityDto
import com.edumath.uchus.data.api.MapSettingsDto
import com.edumath.uchus.data.api.MapSettingsRequest
import com.edumath.uchus.data.api.SchoolDto
import com.edumath.uchus.data.api.TeacherUserDto
import com.edumath.uchus.data.api.UserDto
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

private val adminTabs = listOf(
    "Сводка",
    "Люди",
    "Школы",
    "Темы",
    "Пособия",
    "ИИ",
    "Карты",
    "Журнал",
    "Магазин",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AdminScreen(
    container: AppContainer,
    onBack: () -> Unit,
    initialTab: Int = 0,
) {
    var tab by remember { mutableIntStateOf(initialTab.coerceIn(0, adminTabs.lastIndex)) }

    ScreenScaffold(title = "Администрирование", onBack = onBack) { padding ->
        Column(
            Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            ScrollableTabRow(
                selectedTabIndex = tab,
                edgePadding = 8.dp,
            ) {
                adminTabs.forEachIndexed { index, name ->
                    Tab(
                        selected = tab == index,
                        onClick = { tab = index },
                        text = { Text(name) },
                    )
                }
            }

            when (tab) {
                0 -> AdminOverviewTab(container)
                1 -> AdminUsersTab(container)
                2 -> AdminOrgsTab(container)
                3 -> AdminTopicsTab(container)
                4 -> AdminTextbooksTab(container)
                5 -> AdminAiTab(container)
                6 -> AdminMapsTab(container)
                7 -> AdminAuditTab(container)
                else -> AdminShopTab(container)
            }
        }
    }
}

@Composable
private fun AdminOverviewTab(container: AppContainer) {
    Load(key = "admin-stats", block = { container.api.adminStats() }) { data, _ ->
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item {
                StatsRow(
                    "люди" to "${data.stats.users}",
                    "классы" to "${data.stats.classes}",
                    "темы" to "${data.stats.topics}",
                )
            }
            item {
                StatsRow(
                    "ученики" to "${data.stats.students}",
                    "учителя" to "${data.stats.teachers}",
                    "родители" to "${data.stats.parents}",
                )
            }

            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp)) {
                        KeyValue("Города", "${data.stats.cities}")
                        KeyValue("Школы", "${data.stats.schools}")
                        KeyValue("Пособия", "${data.stats.textbooks}")
                        KeyValue("Книги в библиотеках", "${data.stats.libraryBooks}")
                        KeyValue("Работы", "${data.stats.assignments}")
                        KeyValue("Попытки", "${data.stats.attempts}")
                        KeyValue("Семейные профили", "${data.stats.learners}")
                    }
                }
            }

            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp)) {
                        Text("ИИ", fontWeight = FontWeight.SemiBold)
                        KeyValue("Запросов", "${data.ai.total}")
                        KeyValue("Успешно", "${data.ai.ok}")
                        KeyValue("Ошибок", "${data.ai.failed}")
                        data.ai.lastError?.detail?.let { KeyValue("Последняя ошибка", it.take(60)) }
                    }
                }
            }

            item { SectionTitle("Новые пользователи") }
            items(data.recentUsers) { user ->
                Card(Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(user.avatar ?: "👤", fontSize = 22.sp)
                        Spacer(Modifier.width(8.dp))
                        Column(Modifier.weight(1f)) {
                            Text(user.displayName, fontWeight = FontWeight.Medium)
                            Text(
                                "${user.login ?: ""} · ${roleLabel(user.role)}",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }

            item { SectionTitle("Последние действия") }
            items(data.recentAudit) { entry ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(
                            "${entry.action ?: "?"} ${entry.entity ?: ""} ${entry.entityId ?: ""}",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        Text(
                            "${entry.createdAt ?: ""} · ${entry.login ?: "система"}",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            item { Spacer(Modifier.height(16.dp)) }
        }
    }
}

@Composable
private fun AdminUsersTab(container: AppContainer) {
    val scope = rememberCoroutineScope()
    var tick by remember { mutableStateOf(0) }
    var role by remember { mutableStateOf<String?>(null) }
    var searchInput by remember { mutableStateOf("") }
    var search by remember { mutableStateOf("") }
    var message by remember { mutableStateOf<String?>(null) }
    var showCreate by remember { mutableStateOf(false) }
    var passwordTarget by remember { mutableStateOf<UserDto?>(null) }
    var deleteTarget by remember { mutableStateOf<UserDto?>(null) }

    Load(
        key = "admin-users:$role:$search:$tick",
        block = { container.api.adminUsers(role, search.ifBlank { null }) },
    ) { data, refresh ->
        Column(Modifier.fillMaxSize()) {
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(
                    value = searchInput,
                    onValueChange = { searchInput = it },
                    label = { Text("Поиск") },
                    singleLine = true,
                    modifier = Modifier.weight(1f),
                )
                Button(onClick = { search = searchInput.trim() }) { Text("Найти") }
            }

            LazyRow(
                contentPadding = PaddingValues(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                item {
                    FilterChip(
                        selected = role == null,
                        onClick = { role = null },
                        label = { Text("все") },
                    )
                }
                items(data.roles) { value ->
                    FilterChip(
                        selected = role == value,
                        onClick = { role = value },
                        label = { Text(roleLabel(value)) },
                    )
                }
            }

            Row(Modifier.padding(16.dp)) {
                Button(onClick = { showCreate = true }, modifier = Modifier.fillMaxWidth()) {
                    Text("Создать пользователя")
                }
            }

            if (message != null) {
                Column(Modifier.padding(horizontal = 16.dp)) { InfoBox(message!!) }
            }

            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (data.users.isEmpty()) {
                    item { EmptyBox("Пользователи не найдены.", "👥") }
                }
                items(data.users) { user ->
                    Card(Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(user.avatar ?: "👤", fontSize = 22.sp)
                            Spacer(Modifier.width(8.dp))
                            Column(Modifier.weight(1f)) {
                                Text(user.displayName, fontWeight = FontWeight.Medium)
                                Text(
                                    "${user.login ?: ""} · ${roleLabel(user.role)}",
                                    style = MaterialTheme.typography.labelSmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                            Tag(if (user.isActive) "активен" else "выключен")
                            TextButton(
                                onClick = {
                                    scope.launch {
                                        runCatching {
                                            apiCall {
                                                container.api.updateUser(
                                                    user.id,
                                                    com.edumath.uchus.data.api.UpdateUserRequest(
                                                        isActive = !user.isActive
                                                    ),
                                                )
                                            }
                                        }
                                            .onSuccess { tick++ }
                                            .onFailure { message = it.message }
                                    }
                                },
                            ) { Text(if (user.isActive) "Выкл." else "Вкл.") }
                            TextButton(onClick = { passwordTarget = user }) { Text("Пароль") }
                            TextButton(onClick = { deleteTarget = user }) {
                                Text("×", color = MaterialTheme.colorScheme.error)
                            }
                        }
                    }
                }
                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }

    if (showCreate) {
        CreateUserDialog(
            roles = listOf("student", "teacher", "parent", "admin"),
            onDismiss = { showCreate = false },
            onCreate = { request ->
                scope.launch {
                    runCatching { apiCall { container.api.createUser(request) } }
                        .onSuccess {
                            message = "Пользователь создан"
                            showCreate = false
                            tick++
                        }
                        .onFailure { message = it.message }
                }
            },
        )
    }

    val passwordUser = passwordTarget
    if (passwordUser != null) {
        var password by remember(passwordUser.id) { mutableStateOf("") }
        AlertDialog(
            onDismissRequest = { passwordTarget = null },
            title = { Text("Новый пароль") },
            text = {
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("Пароль (от 6 символов)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        val value = password
                        passwordTarget = null
                        scope.launch {
                            runCatching {
                                apiCall {
                                    container.api.setUserPassword(
                                        passwordUser.id,
                                        mapOf("password" to value),
                                    )
                                }
                            }
                                .onSuccess { message = "Пароль изменён" }
                                .onFailure { message = it.message }
                        }
                    },
                ) { Text("Сохранить") }
            },
            dismissButton = { TextButton(onClick = { passwordTarget = null }) { Text("Отмена") } },
        )
    }

    val deleting = deleteTarget
    if (deleting != null) {
        AlertDialog(
            onDismissRequest = { deleteTarget = null },
            title = { Text("Удалить пользователя?") },
            text = { Text("«${deleting.displayName}» и связанные данные будут удалены.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        deleteTarget = null
                        scope.launch {
                            runCatching { apiCall { container.api.deleteUser(deleting.id) } }
                                .onSuccess { message = "Пользователь удалён"; tick++ }
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
private fun CreateUserDialog(
    roles: List<String>,
    onDismiss: () -> Unit,
    onCreate: (CreateUserRequest) -> Unit,
) {
    var login by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var role by remember { mutableStateOf(roles.first()) }
    var firstName by remember { mutableStateOf("") }
    var lastName by remember { mutableStateOf("") }
    var email by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Новый пользователь") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = login,
                    onValueChange = { login = it },
                    label = { Text("Логин") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = password,
                    onValueChange = { password = it },
                    label = { Text("Пароль") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Text("Роль", style = MaterialTheme.typography.labelLarge)
                LazyRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    items(roles) { value ->
                        FilterChip(
                            selected = role == value,
                            onClick = { role = value },
                            label = { Text(roleLabel(value)) },
                        )
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = firstName,
                        onValueChange = { firstName = it },
                        label = { Text("Имя") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = lastName,
                        onValueChange = { lastName = it },
                        label = { Text("Фамилия") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                }
                OutlinedTextField(
                    value = email,
                    onValueChange = { email = it },
                    label = { Text("Email (необязательно)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    onCreate(
                        CreateUserRequest(
                            login = login.trim(),
                            password = password,
                            role = role,
                            firstName = firstName.trim().ifBlank { null },
                            lastName = lastName.trim().ifBlank { null },
                            email = email.trim().ifBlank { null },
                        )
                    )
                },
            ) { Text("Создать") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Отмена") } },
    )
}

@Composable
private fun AdminOrgsTab(container: AppContainer) {
    val scope = rememberCoroutineScope()
    var tick by remember { mutableStateOf(0) }
    var message by remember { mutableStateOf<String?>(null) }
    var showCity by remember { mutableStateOf(false) }
    var showSchool by remember { mutableStateOf(false) }
    var showClass by remember { mutableStateOf(false) }
    var studentsTarget by remember { mutableStateOf<ClassDto?>(null) }

    Load(key = "admin-orgs:$tick", block = { container.api.adminOrgs() }) { data, refresh ->
        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (message != null) {
                item { InfoBox(message!!) }
            }

            item { SectionTitle("Города", trailing = "${data.cities.size}") }
            items(data.cities) { city ->
                Card(Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(12.dp)) {
                        Text(city.name ?: "Город", modifier = Modifier.weight(1f))
                        Text(
                            city.region ?: "",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            item {
                OutlinedButton(onClick = { showCity = true }, modifier = Modifier.fillMaxWidth()) {
                    Text("Добавить город")
                }
            }

            item { SectionTitle("Школы", trailing = "${data.schools.size}") }
            items(data.schools) { school ->
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(12.dp)) {
                        Text(school.name ?: "Школа", fontWeight = FontWeight.Medium)
                        Text(
                            listOfNotNull(school.cityName, school.address).joinToString(" · "),
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }
            item {
                OutlinedButton(onClick = { showSchool = true }, modifier = Modifier.fillMaxWidth()) {
                    Text("Добавить школу")
                }
            }

            item { SectionTitle("Классы", trailing = "${data.classes.size}") }
            items(data.classes) { klass ->
                Card(
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { studentsTarget = klass },
                ) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text(klass.displayTitle, fontWeight = FontWeight.Medium)
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
            item {
                OutlinedButton(onClick = { showClass = true }, modifier = Modifier.fillMaxWidth()) {
                    Text("Добавить класс")
                }
            }

            item { Spacer(Modifier.height(16.dp)) }
        }
    }

    if (showCity) {
        SimpleTextDialog(
            title = "Новый город",
            fields = listOf("Название", "Регион"),
            onDismiss = { showCity = false },
            onConfirm = { values ->
                scope.launch {
                    runCatching {
                        apiCall {
                            container.api.createCity(
                                CreateCityRequest(
                                    name = values[0],
                                    region = values[1].ifBlank { null },
                                )
                            )
                        }
                    }
                        .onSuccess { message = "Город добавлен"; showCity = false; tick++ }
                        .onFailure { message = it.message }
                }
            },
        )
    }

    if (showSchool) {
        var cityId by remember { mutableStateOf<Int?>(null) }
        var cities by remember { mutableStateOf<List<CityDto>>(emptyList()) }
        var name by remember { mutableStateOf("") }
        var address by remember { mutableStateOf("") }
        LaunchedEffect(Unit) {
            runCatching { apiCall { container.api.adminOrgs() } }
                .onSuccess {
                    cities = it.cities
                    cityId = it.cities.firstOrNull()?.id
                }
        }
        AlertDialog(
            onDismissRequest = { showSchool = false },
            title = { Text("Новая школа") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Город", style = MaterialTheme.typography.labelLarge)
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        items(cities) { city ->
                            FilterChip(
                                selected = cityId == city.id,
                                onClick = { cityId = city.id },
                                label = { Text(city.name ?: "") },
                            )
                        }
                    }
                    OutlinedTextField(
                        value = name,
                        onValueChange = { name = it },
                        label = { Text("Название школы") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    OutlinedTextField(
                        value = address,
                        onValueChange = { address = it },
                        label = { Text("Адрес") },
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        val chosen = cityId
                        if (chosen != null && name.isNotBlank()) {
                            scope.launch {
                                runCatching {
                                    apiCall {
                                        container.api.createSchool(
                                            CreateSchoolRequest(
                                                cityId = chosen,
                                                name = name.trim(),
                                                address = address.trim().ifBlank { null },
                                            )
                                        )
                                    }
                                }
                                    .onSuccess { message = "Школа добавлена"; showSchool = false; tick++ }
                                    .onFailure { message = it.message }
                            }
                        }
                    },
                ) { Text("Создать") }
            },
            dismissButton = { TextButton(onClick = { showSchool = false }) { Text("Отмена") } },
        )
    }

    if (showClass) {
        var schoolId by remember { mutableStateOf<Int?>(null) }
        var grade by remember { mutableStateOf(5) }
        var letter by remember { mutableStateOf("А") }
        var teacherId by remember { mutableStateOf<Int?>(null) }
        var schools by remember { mutableStateOf<List<SchoolDto>>(emptyList()) }
        var teachers by remember { mutableStateOf<List<TeacherUserDto>>(emptyList()) }
        LaunchedEffect(Unit) {
            runCatching { apiCall { container.api.adminOrgs() } }
                .onSuccess {
                    schools = it.schools
                    teachers = it.teachers
                    schoolId = it.schools.firstOrNull()?.id
                }
        }
        AlertDialog(
            onDismissRequest = { showClass = false },
            title = { Text("Новый класс") },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Школа", style = MaterialTheme.typography.labelLarge)
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        items(schools) { school ->
                            FilterChip(
                                selected = schoolId == school.id,
                                onClick = { schoolId = school.id },
                                label = { Text(school.name ?: "") },
                            )
                        }
                    }
                    Text("Класс", style = MaterialTheme.typography.labelLarge)
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        items((1..11).toList()) { value ->
                            FilterChip(
                                selected = grade == value,
                                onClick = { grade = value },
                                label = { Text("$value") },
                            )
                        }
                    }
                    OutlinedTextField(
                        value = letter,
                        onValueChange = { letter = it },
                        label = { Text("Буква") },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                    if (teachers.isNotEmpty()) {
                        Text("Учитель", style = MaterialTheme.typography.labelLarge)
                        LazyRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            items(teachers) { teacher ->
                                FilterChip(
                                    selected = teacherId == teacher.id,
                                    onClick = { teacherId = teacher.id },
                                    label = { Text(teacher.displayName) },
                                )
                            }
                        }
                    }
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        val chosenSchool = schoolId
                        if (chosenSchool != null) {
                            scope.launch {
                                runCatching {
                                    apiCall {
                                        container.api.createClass(
                                            CreateClassRequest(
                                                schoolId = chosenSchool,
                                                grade = grade,
                                                letter = letter,
                                                teacherId = teacherId,
                                            )
                                        )
                                    }
                                }
                                    .onSuccess { message = "Класс добавлен"; showClass = false; tick++ }
                                    .onFailure { message = it.message }
                            }
                        }
                    },
                ) { Text("Создать") }
            },
            dismissButton = { TextButton(onClick = { showClass = false }) { Text("Отмена") } },
        )
    }

    val klass = studentsTarget
    if (klass != null) {
        ClassStudentsDialog(
            container = container,
            klass = klass,
            onDismiss = { studentsTarget = null },
            onChanged = { message = it; tick++ },
        )
    }
}

@Composable
private fun ClassStudentsDialog(
    container: AppContainer,
    klass: ClassDto,
    onDismiss: () -> Unit,
    onChanged: (String) -> Unit,
) {
    val scope = rememberCoroutineScope()
    var studentId by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Ученики ${klass.displayTitle}") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "Введите ID ученика из вкладки «Люди».",
                    style = MaterialTheme.typography.bodySmall,
                )
                OutlinedTextField(
                    value = studentId,
                    onValueChange = { studentId = it.filter { ch -> ch.isDigit() } },
                    label = { Text("ID ученика") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                if (error != null) {
                    Text(error!!, color = MaterialTheme.colorScheme.error)
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val id = studentId.toIntOrNull()
                    if (id != null) {
                        scope.launch {
                            runCatching {
                                apiCall {
                                    container.api.classStudents(
                                        klass.id,
                                        mapOf("student_id" to id),
                                    )
                                }
                            }
                                .onSuccess {
                                    onChanged("Ученик добавлен в класс")
                                    onDismiss()
                                }
                                .onFailure { error = it.message }
                        }
                    }
                },
            ) { Text("Добавить") }
        },
        dismissButton = {
            Row {
                TextButton(onClick = {
                    val id = studentId.toIntOrNull()
                    if (id != null) {
                        scope.launch {
                            runCatching {
                                apiCall {
                                    container.api.classStudents(
                                        klass.id,
                                        mapOf("student_id" to id, "remove" to true),
                                    )
                                }
                            }
                                .onSuccess {
                                    onChanged("Ученик убран из класса")
                                    onDismiss()
                                }
                                .onFailure { error = it.message }
                        }
                    }
                }) { Text("Убрать") }
                TextButton(onClick = onDismiss) { Text("Закрыть") }
            }
        },
    )
}

@Composable
private fun SimpleTextDialog(
    title: String,
    fields: List<String>,
    onDismiss: () -> Unit,
    onConfirm: (List<String>) -> Unit,
) {
    val values = remember { mutableStateListOf<String>().apply { fields.forEach { add("") } } }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                fields.forEachIndexed { index, label ->
                    OutlinedTextField(
                        value = values[index],
                        onValueChange = { values[index] = it },
                        label = { Text(label) },
                        singleLine = true,
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { onConfirm(values.toList()) }) { Text("Сохранить") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Отмена") } },
    )
}

@Composable
internal fun AdminMapsTab(container: AppContainer) {
    val scope = rememberCoroutineScope()
    var tick by remember { mutableIntStateOf(0) }
    var message by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    Load(key = "admin-map:$tick", block = { container.api.adminMapSettings() }) { data, _ ->
        val initial: MapSettingsDto = data.settings ?: MapSettingsDto()
        var provider by remember(initial) { mutableStateOf(initial.provider) }
        var tileUrl by remember(initial) { mutableStateOf(initial.tileUrl ?: "") }
        var attribution by remember(initial) { mutableStateOf(initial.attribution ?: "") }
        var crs by remember(initial) { mutableStateOf(initial.crs) }
        var minZoom by remember(initial) { mutableStateOf(initial.minZoom.toString()) }
        var maxZoom by remember(initial) { mutableStateOf(initial.maxZoom.toString()) }
        var zoom by remember(initial) { mutableStateOf(initial.zoom.toString()) }
        var centerLat by remember(initial) { mutableStateOf(initial.centerLat.toString()) }
        var centerLon by remember(initial) { mutableStateOf(initial.centerLon.toString()) }

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            item {
                Text(
                    "Карта для GPS-контроля",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    "Родители видят местоположение и историю детей на выбранной карте. " +
                        "Настройка общая для сайта и приложения.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(
                        Modifier.padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text("Провайдер", fontWeight = FontWeight.SemiBold)
                        LazyRow(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            items(data.presets) { preset ->
                                FilterChip(
                                    selected = provider == preset.id,
                                    onClick = {
                                        provider = preset.id
                                        val url = preset.tileUrl
                                        val attr = preset.attribution
                                        if (!url.isNullOrBlank()) tileUrl = url
                                        if (!attr.isNullOrBlank()) attribution = attr
                                        crs = preset.crs
                                        if (preset.maxZoom > 0) maxZoom = preset.maxZoom.toString()
                                    },
                                    label = { Text(preset.name.ifBlank { preset.id }) },
                                )
                            }
                        }
                        data.presets.firstOrNull { it.id == provider }?.note?.let {
                            Text(
                                it,
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }

            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(
                        Modifier.padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        OutlinedTextField(
                            value = tileUrl,
                            onValueChange = { tileUrl = it },
                            label = { Text("Адрес тайлов") },
                            supportingText = { Text("Нужны подстановки {x}, {y}, {z}") },
                            singleLine = false,
                            modifier = Modifier.fillMaxWidth(),
                        )
                        OutlinedTextField(
                            value = attribution,
                            onValueChange = { attribution = it },
                            label = { Text("Подпись источника") },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth(),
                        )
                        Text("Проекция", fontWeight = FontWeight.SemiBold)
                        Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            FilterChip(
                                selected = crs == "mercator",
                                onClick = { crs = "mercator" },
                                label = { Text("Web Mercator") },
                            )
                            FilterChip(
                                selected = crs == "yandex",
                                onClick = { crs = "yandex" },
                                label = { Text("Яндекс") },
                            )
                        }
                    }
                }
            }

            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(
                        Modifier.padding(14.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedTextField(
                                value = minZoom,
                                onValueChange = { minZoom = it },
                                label = { Text("Мин. масштаб") },
                                singleLine = true,
                                modifier = Modifier.weight(1f),
                            )
                            OutlinedTextField(
                                value = maxZoom,
                                onValueChange = { maxZoom = it },
                                label = { Text("Макс. масштаб") },
                                singleLine = true,
                                modifier = Modifier.weight(1f),
                            )
                            OutlinedTextField(
                                value = zoom,
                                onValueChange = { zoom = it },
                                label = { Text("Старт") },
                                singleLine = true,
                                modifier = Modifier.weight(1f),
                            )
                        }
                        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedTextField(
                                value = centerLat,
                                onValueChange = { centerLat = it },
                                label = { Text("Широта центра") },
                                singleLine = true,
                                modifier = Modifier.weight(1f),
                            )
                            OutlinedTextField(
                                value = centerLon,
                                onValueChange = { centerLon = it },
                                label = { Text("Долгота центра") },
                                singleLine = true,
                                modifier = Modifier.weight(1f),
                            )
                        }
                    }
                }
            }

            if (message != null) {
                item { InfoBox(message!!) }
            }

            item {
                Button(
                    onClick = {
                        if (!busy) {
                            busy = true
                            scope.launch {
                                runCatching {
                                    apiCall {
                                        container.api.saveAdminMapSettings(
                                            MapSettingsRequest(
                                                provider = provider,
                                                tileUrl = tileUrl.trim(),
                                                attribution = attribution.trim(),
                                                crs = crs,
                                                minZoom = minZoom.toIntOrNull() ?: 1,
                                                maxZoom = maxZoom.toIntOrNull() ?: 19,
                                                centerLat = centerLat.toDoubleOrNull() ?: 53.9023,
                                                centerLon = centerLon.toDoubleOrNull() ?: 27.5619,
                                                zoom = zoom.toIntOrNull() ?: 11,
                                            )
                                        )
                                    }
                                }
                                    .onSuccess {
                                        message = it.message ?: "Настройки карты сохранены"
                                        tick++
                                    }
                                    .onFailure { message = it.message }
                                busy = false
                            }
                        }
                    },
                    enabled = !busy,
                    modifier = Modifier.fillMaxWidth(),
                ) { Text(if (busy) "Сохраняем…" else "💾 Сохранить карту") }
            }

            item {
                InfoBox(
                    "Для Яндекс Карт выберите провайдера «Яндекс» — адрес тайлов и " +
                        "проекция заполнятся автоматически. Свои тайлы должны быть " +
                        "доступны по HTTPS без авторизации."
                )
            }
            item { Spacer(Modifier.height(16.dp)) }
        }
    }
}

fun roleLabel(role: String?): String = when (role) {
    "admin" -> "админ"
    "teacher" -> "учитель"
    "student" -> "ученик"
    "parent" -> "родитель"
    else -> role ?: "—"
}
