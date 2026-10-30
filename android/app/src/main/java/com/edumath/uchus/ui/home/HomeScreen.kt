package com.edumath.uchus.ui.home

import androidx.compose.foundation.background
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ExitToApp
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.AssignmentDto
import com.edumath.uchus.data.api.SessionDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.StatPill
import com.edumath.uchus.ui.common.Tag

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

    LaunchedEffect(session, reloadTick) {
        if (session == null) return@LaunchedEffect
        runCatching { apiCall { container.api.notifications(limit = 20) } }
            .onSuccess { unread = it.unread }
        if (isStudent) {
            runCatching { apiCall { container.api.studentAssignments() } }
                .onSuccess { assignments = it.assignments.filter { a -> a.result == null } }
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text("Школьник", fontWeight = FontWeight.Bold)
                        Text(
                            "Общеобразовательная платформа обучения",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
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

    Row(verticalAlignment = Alignment.CenterVertically) {
        Text(emoji, fontSize = if (isStrict) 32.sp else 40.sp)
        Spacer(Modifier.width(12.dp))
        Column {
            Text(
                "Здравствуйте, $name!",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
            )
            Text(
                roleLabel,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (!isStrict) {
                learner?.title?.takeIf { it.isNotBlank() }?.let {
                    Text(
                        "🏅 $it",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.SemiBold,
                    )
                }
                learner?.pet?.let { pet ->
                    Text(
                        "${pet.icon ?: "🐾"} ${pet.name ?: "Питомец"} · ${pet.stageName ?: "Малыш"}",
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        }
    }
}

@Composable
private fun HomeCard(item: HomeItem, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(item.emoji, fontSize = 26.sp)
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text(item.title, fontWeight = FontWeight.SemiBold)
                Text(
                    item.subtitle,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text("→", style = MaterialTheme.typography.titleMedium)
        }
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
        HomeItem("admin/6", "🧾", "Журнал", "Действия администраторов"),
        HomeItem("admin/7", "🛍", "Магазин", "Подарки, каталог и события"),
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
