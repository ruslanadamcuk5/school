package com.edumath.uchus.ui.home

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.edumath.uchus.data.api.SessionDto
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.StatPill

data class HomeItem(
    val route: String,
    val emoji: String,
    val title: String,
    val subtitle: String,
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    session: SessionDto?,
    serverUrl: String,
    availableRoutes: Set<String>,
    aiEnabled: Boolean,
    onOpen: (String) -> Unit,
    onLogout: () -> Unit,
) {
    val role = session?.user?.role ?: "student"
    val theme = session?.theme ?: "playful"
    val isFamily = session?.user == null
    val items = homeItems(role, aiEnabled, isFamily, theme)
        .filter { it.route in availableRoutes }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Учусь", fontWeight = FontWeight.Bold) },
                actions = {
                    IconButton(onClick = onLogout) {
                        Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = "Выйти")
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
                Greeting(session)
            }

            val learner = session?.learner
            if (learner != null) {
                item {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        if (theme == "playful") {
                            StatPill("опыт", "${learner.xp}")
                            StatPill("монеты", "${learner.coins}")
                        }
                        StatPill("класс", "${learner.grade}")
                    }
                }
            }

            item {
                InfoBox("Сервер: $serverUrl")
            }

            items(items) { item ->
                HomeCard(item) { onOpen(item.route) }
            }

            if (items.isEmpty()) {
                item {
                    Text(
                        "Разделы появятся после подключения к серверу.",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            item { Spacer(Modifier.height(24.dp)) }
        }
    }
}

@Composable
private fun Greeting(session: SessionDto?) {
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
        Text(emoji, fontSize = 40.sp)
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
            Text(item.emoji, fontSize = 28.sp)
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
    theme: String,
): List<HomeItem> = when (role) {
    "admin" -> listOf(
        HomeItem("admin/0", "📊", "Сводка", "Пользователи, классы, книги"),
        HomeItem("admin/1", "👥", "Пользователи", "Аккаунты и роли"),
        HomeItem("admin/2", "🏫", "Организации", "Города, школы, классы"),
        HomeItem("admin/3", "🗺", "Темы", "Каталог тем по классам"),
        HomeItem("admin/4", "📖", "Пособия", "PDF-учебники"),
        HomeItem("admin/5", "🤖", "Искусственный интеллект", "Провайдер, модель, ключ"),
        HomeItem("admin/6", "🧾", "Журнал", "Действия администраторов"),
        HomeItem("about", "ℹ️", "О приложении", "Версия и связь с сервером"),
    )
    "teacher" -> buildList {
        add(HomeItem("teacher_dashboard", "🏫", "Кабинет учителя", "Классы и последние работы"))
        add(HomeItem("teacher_students", "👦", "Ученики", "Классы и успеваемость"))
        add(HomeItem("assignments", "📝", "Работы", "Создать и проверить"))
        add(HomeItem("library", "📚", "Библиотека", "Книги, доступ, рекомендации"))
        add(HomeItem("teacher_schedule", "🗓", "Расписание", "Уроки по классам"))
        if (aiEnabled) add(HomeItem("ai", "🤖", "ИИ-помощник", "Объяснение темы и вопросы"))
        add(HomeItem("profile", "🏅", "Профиль", "Аккаунт и настройки"))
        add(HomeItem("about", "ℹ️", "О приложении", "Версия и связь с сервером"))
    }
    "parent" -> buildList {
        add(HomeItem("parent", "👨‍👩‍👧", "Дети", "Успеваемость и прогресс"))
        add(HomeItem("assignments", "📝", "Задания", "Назначить и проверить"))
        add(HomeItem("library", "📚", "Библиотека", "Книги ребёнка"))
        if (aiEnabled) add(HomeItem("ai", "🤖", "ИИ-помощник", "Объяснение темы и вопросы"))
        add(HomeItem("profile", "🏅", "Профиль", "Аккаунт и настройки"))
        add(HomeItem("about", "ℹ️", "О приложении", "Версия и связь с сервером"))
    }
    else -> buildList {
        add(HomeItem("map", "🗺", "Карта тем", "Темы, тренировки и тесты"))
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
        add(
            HomeItem(
                "profile",
                "🏅",
                "Профиль",
                if (theme == "playful") "Опыт, монеты, звёзды, значки" else "Аккаунт и учёба",
            )
        )
        if (aiEnabled) {
            add(HomeItem("ai", "🤖", "ИИ-помощник", "Объяснение темы и вопросы"))
        }
        add(HomeItem("about", "ℹ️", "О приложении", "Версия и связь с сервером"))
    }
}
