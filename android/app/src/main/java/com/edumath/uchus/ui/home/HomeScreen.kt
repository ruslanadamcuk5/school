package com.edumath.uchus.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.ApiJson
import com.edumath.uchus.data.api.AssignmentDto
import com.edumath.uchus.data.api.SessionDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.StatPill
import com.edumath.uchus.ui.common.Tag
import com.edumath.uchus.ui.pet.PetCompanionCard
import com.edumath.uchus.ui.theme.SitePalette
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

data class HomeItem(
    val route: String,
    val emoji: String,
    val title: String,
    val subtitle: String,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    container: AppContainer,
    session: SessionDto?,
    serverUrl: String,
    availableRoutes: Set<String>,
    aiEnabled: Boolean,
    onOpen: (String) -> Unit,
    onOpenAssignment: (Int) -> Unit = {},
    onOpenNotifications: () -> Unit = {},
    onLogout: () -> Unit,
) {
    val role = session?.user?.role ?: "student"
    val theme = session?.theme ?: "playful"
    val isFamily = session?.user == null
    val isStrict = theme != "playful"
    val isStudent = role == "student" && !isFamily
    val items = homeItems(role, aiEnabled, isFamily, isStrict).filter { it.route in availableRoutes }

    var assignments by remember(session) { mutableStateOf<List<AssignmentDto>>(emptyList()) }
    var unread by remember(session) { mutableIntStateOf(0) }
    var reloadTick by remember(session) { mutableIntStateOf(0) }
    var pet by remember(session?.learner?.id) { mutableStateOf(session?.learner?.pet) }
    var petMessage by remember { mutableStateOf<String?>(null) }
    var petBusy by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    LaunchedEffect(session, reloadTick) {
        if (session == null) return@LaunchedEffect
        runCatching { apiCall { container.api.notifications(limit = 20) } }
            .onSuccess { unread = it.unread }
        if (isStudent) {
            runCatching { apiCall { container.api.studentAssignments() } }
                .onSuccess { assignments = it.assignments.filter { a -> a.result == null } }
            if (!isStrict) {
                runCatching { apiCall { container.api.pet() } }
                    .onSuccess { state -> state.pet?.let { pet = it } }
            }
        }
    }

    LaunchedEffect(petMessage) {
        if (petMessage != null) {
            delay(7000)
            petMessage = null
        }
    }

    val patPet: () -> Unit = {
        if (!petBusy) {
            petBusy = true
            scope.launch {
                runCatching { apiCall { container.api.petPat() } }
                    .onSuccess { state ->
                        state.pet?.let { pet = it }
                        petMessage = state.message
                        if (state.awarded > 0) {
                            runCatching { apiCall { container.api.me() } }.onSuccess { fresh ->
                                container.session.updateSnapshot(ApiJson.gson.toJson(fresh))
                            }
                        }
                    }
                    .onFailure { petMessage = it.message ?: "Питомец не отвечает. Попробуй ещё раз." }
                petBusy = false
            }
        }
    }

    Scaffold(
        containerColor = SitePalette.Ink950,
        topBar = {
            TopAppBar(
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = SitePalette.Ink950,
                    titleContentColor = SitePalette.Text,
                    actionIconContentColor = SitePalette.Muted,
                ),
                title = {
                    Column {
                        Text(
                            "Школьник",
                            fontWeight = FontWeight.ExtraBold,
                            style = MaterialTheme.typography.titleLarge,
                        )
                        Text(
                            "Общеобразовательная платформа",
                            style = MaterialTheme.typography.labelSmall,
                            color = SitePalette.MutedDim,
                        )
                    }
                },
                actions = {
                    if (!isFamily) {
                        IconButton(onClick = onOpenNotifications) {
                            Box {
                                Icon(Icons.Default.Notifications, contentDescription = "Уведомления")
                                val badgeAlpha by animateFloatAsState(
                                    targetValue = if (unread > 0) 1f else 0f,
                                    animationSpec = tween(220),
                                    label = "unread-badge",
                                )
                                Box(
                                    modifier = Modifier
                                        .align(Alignment.TopEnd)
                                        .size(16.dp)
                                        .alpha(badgeAlpha)
                                        .clip(CircleShape)
                                        .background(MaterialTheme.colorScheme.error),
                                    contentAlignment = Alignment.Center,
                                ) {
                                    Text(
                                        if (unread > 9) "9+" else "$unread",
                                        color = MaterialTheme.colorScheme.onError,
                                        fontSize = 9.sp,
                                        fontWeight = FontWeight.Bold,
                                    )
                                }
                            }
                        }
                    }
                    IconButton(onClick = onLogout) {
                        Icon(Icons.AutoMirrored.Filled.ExitToApp, contentDescription = "Выйти")
                    }
                },
            )
        },
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Spacer(Modifier.height(4.dp))
                Greeting(session, isStrict)
            }

            val petCard = pet
            if (isStudent && !isStrict && petCard != null) {
                item {
                    PetCompanionCard(
                        pet = petCard,
                        busy = petBusy,
                        onPat = patPet,
                        message = petMessage,
                    )
                }
            }

            val learner = session?.learner
            if (learner != null) {
                item {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        StatPill("класс", "${learner.grade}")
                        if (!isStrict) {
                            StatPill("опыт", "${learner.xp}")
                            StatPill("монеты", "${learner.coins}")
                        }
                    }
                }
            }

            if (isStudent && assignments.isNotEmpty()) {
                item {
                    SectionTitle("Задания на сегодня", "${assignments.size}")
                }
                items(assignments) { assignment ->
                    PendingAssignmentCard(assignment) { onOpenAssignment(assignment.id) }
                }
            }

            if (items.isNotEmpty()) {
                item { SectionTitle(if (isStrict) "Разделы" else "Куда пойдём?") }
            }

            items(items) { item ->
                HomeCard(item) { onOpen(item.route) }
            }

            item {
                if (items.isEmpty()) {
                    Text(
                        "Разделы появятся после подключения к серверу.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            if (!isFamily) {
                item { InfoBox("Сервер: $serverUrl") }
            }

            item { Spacer(Modifier.height(24.dp)) }
        }
    }
}

@Composable
private fun PendingAssignmentCard(item: AssignmentDto, onClick: () -> Unit) {
    val missed = item.missed
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
                Tag(
                    when {
                        missed -> "просрочено"
                        item.overdue -> "срок истёк"
                        else -> "не сдано"
                    }
                )
            }
            val author = item.authorDisplay.takeIf { it.isNotBlank() }
            if (author != null) {
                Text(
                    author,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.primary,
                )
            }
            Text(
                listOfNotNull(
                    item.kind,
                    item.questionsCount.takeIf { it > 0 }?.let { "$it заданий" },
                    item.dueDate?.takeIf { it.isNotBlank() }?.let { "до $it" },
                ).joinToString(" · "),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@Composable
private fun Greeting(session: SessionDto?, isStrict: Boolean) {
    val user = session?.user
    val learner = session?.learner
    val name = user?.displayName ?: learner?.displayName ?: "Гость"
    val emoji = learner?.emoji ?: "👤"
    val roleLabel = when (user?.role) {
        "admin" -> "Администратор"
        "teacher" -> "Учитель"
        "parent" -> "Родитель"
        "student" -> "Ученик"
        else -> "Семейный профиль"
    }

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .background(
                Brush.linearGradient(
                    listOf(
                        SitePalette.Iris500.copy(alpha = 0.24f),
                        SitePalette.Ink850,
                        SitePalette.Cyan400.copy(alpha = 0.10f),
                    ),
                ),
                RoundedCornerShape(24.dp),
            )
            .border(1.dp, SitePalette.Border, RoundedCornerShape(24.dp))
            .padding(18.dp),
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(
                modifier = Modifier
                    .size(54.dp)
                    .background(SitePalette.Ink950.copy(alpha = 0.55f), RoundedCornerShape(18.dp))
                    .border(1.dp, SitePalette.Border, RoundedCornerShape(18.dp)),
                contentAlignment = Alignment.Center,
            ) {
                Text(emoji, fontSize = if (isStrict) 26.sp else 30.sp)
            }
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(
                    "Здравствуйте, $name!",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.ExtraBold,
                    color = SitePalette.Text,
                )
                Text(
                    roleLabel.uppercase(),
                    style = MaterialTheme.typography.labelSmall,
                    color = SitePalette.Iris400,
                )
                if (!isStrict) {
                    learner?.title?.takeIf { it.isNotBlank() }?.let {
                        Text(
                            "🏅 $it",
                            style = MaterialTheme.typography.labelMedium,
                            color = SitePalette.Gold400,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun HomeCard(item: HomeItem, onClick: () -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .background(SitePalette.Ink850, RoundedCornerShape(20.dp))
            .border(1.dp, SitePalette.Border, RoundedCornerShape(20.dp))
            .clickable(onClick = onClick)
            .padding(14.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(46.dp)
                .background(SitePalette.Iris500.copy(alpha = 0.14f), RoundedCornerShape(15.dp))
                .border(1.dp, SitePalette.Iris500.copy(alpha = 0.22f), RoundedCornerShape(15.dp)),
            contentAlignment = Alignment.Center,
        ) {
            Text(item.emoji, fontSize = 22.sp)
        }
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            Text(
                item.title,
                fontWeight = FontWeight.SemiBold,
                style = MaterialTheme.typography.titleMedium,
                color = SitePalette.Text,
            )
            Text(
                item.subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = SitePalette.Muted,
            )
        }
        Text("›", style = MaterialTheme.typography.headlineMedium, color = SitePalette.MutedDim)
    }
}

private fun homeItems(
    role: String,
    aiEnabled: Boolean,
    isFamily: Boolean,
    isStrict: Boolean = false,
): List<HomeItem> = when (role) {
    "admin" -> listOf(
        HomeItem("admin/0", "📊", "Сводка", "Пользователи, классы, книги"),
        HomeItem("admin/1", "👥", "Пользователи", "Аккаунты и роли"),
        HomeItem("admin/2", "🏫", "Организации", "Города, школы, классы"),
        HomeItem("admin/3", "🗺", "Темы", "Каталог тем по классам"),
        HomeItem("admin/4", "📖", "Пособия", "PDF-учебники"),
        HomeItem("padruchnik", "🌐", "e-padruchnik", "Поиск и импорт пособий с портала"),
        HomeItem("admin/5", "🤖", "Искусственный интеллект", "Провайдер, модель, ключ"),
        HomeItem("admin/6", "▶️", "YouTube", "Видео по темам, ключ API, кэш"),
        HomeItem("admin/7", "📍", "Карты", "Карта GPS-контроля: Яндекс, OSM, свои тайлы"),
        HomeItem("admin/8", "🧾", "Журнал", "Действия администраторов"),
        HomeItem("admin/9", "🛍", "Магазин", "Подарки, каталог и события"),
        HomeItem("about", "ℹ️", "О приложении", "Версия и связь с сервером"),
    )
    "teacher" -> buildList {
        add(HomeItem("teacher_dashboard", "🏫", "Кабинет учителя", "Классы и последние работы"))
        add(HomeItem("teacher_students", "👦", "Ученики", "Классы и успеваемость"))
        add(HomeItem("assignments", "📝", "Работы", "Создать и проверить"))
        add(HomeItem("library", "📚", "Библиотека", "Книги, доступ, рекомендации"))
        add(HomeItem("padruchnik", "🌐", "Поиск пособий", "e-padruchnik: скачать и открыть классам"))
        add(HomeItem("teacher_schedule", "🗓", "Расписание", "Уроки по классам"))
        if (aiEnabled) add(HomeItem("ai", "🤖", "ИИ-помощник", "Объяснение темы и вопросы"))
        add(HomeItem("profile", "🏅", "Профиль", "Аккаунт и настройки"))
        add(HomeItem("about", "ℹ️", "О приложении", "Версия и связь с сервером"))
    }
    "parent" -> buildList {
        add(HomeItem("parent", "👨‍👩‍👧", "Дети", "Успеваемость и прогресс"))
        add(HomeItem("psychology", "🧠", "Школьная психология", "Результаты тестов и рекомендации"))
        add(HomeItem("parent_map", "🗺", "Карта детей", "Где сейчас и трек за день"))
        add(HomeItem("assignments", "📝", "Задания", "Назначить и проверить"))
        add(HomeItem("library", "📚", "Библиотека", "Книги ребёнка"))
        if (aiEnabled) add(HomeItem("ai", "🤖", "ИИ-помощник", "Объяснение темы и вопросы"))
        add(HomeItem("profile", "🏅", "Профиль", "Аккаунт и настройки"))
        add(HomeItem("about", "ℹ️", "О приложении", "Версия и связь с сервером"))
    }
    else -> buildList {
        add(HomeItem("map", "🗺", "Карта тем", "Темы, тренировки и тесты"))
        if (!isStrict) {
            add(HomeItem("shop", "🛍", "Магазин", "Опыт и монеты → усилители и питомцы"))
        }
        if (!isFamily) {
            add(HomeItem("assignments", "📝", "Работы", "Задания учителя и родителя"))
            add(HomeItem("schedule", "🗓", "Расписание", "Уроки на неделю"))
        }
        add(
            HomeItem(
                "library",
                "📚",
                "Библиотека",
                if (isFamily) "Учебники своего класса" else "Книги класса и рекомендации",
            )
        )
        add(HomeItem("location", "📍", "Геолокация", "Передача позиции родителям"))
        add(HomeItem("psychology", "🧠", "Школьная психология", "Тесты, результаты и рекомендации"))
        add(
            HomeItem(
                "profile",
                "🏅",
                "Профиль",
                if (isFamily) "Аккаунт и учёба" else "Опыт, монеты, звёзды, значки",
            )
        )
        if (aiEnabled) {
            add(HomeItem("ai", "🤖", "ИИ-помощник", "Объяснение темы и вопросы"))
        }
        add(HomeItem("about", "ℹ️", "О приложении", "Версия и связь с сервером"))
    }
}
