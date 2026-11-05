package com.edumath.uchus.ui.student

import android.content.ClipData
import android.content.ClipboardManager
import android.content.Context
import android.widget.Toast
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
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.MapDto
import com.edumath.uchus.data.api.ScheduleDto
import com.edumath.uchus.data.api.SessionDto
import com.edumath.uchus.data.sound.SoundAlertService
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.KeyValue
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.StatsRow
import com.edumath.uchus.ui.common.Tag
import com.edumath.uchus.data.api.ApiJson

@Composable
fun ProfileScreen(
    container: AppContainer,
    session: SessionDto?,
    serverUrl: String,
    onBack: () -> Unit,
    onLogout: () -> Unit,
    onAbout: () -> Unit,
    onSchedule: () -> Unit,
    onShop: (() -> Unit)? = null,
    onRefreshSession: () -> Unit = {},
) {
    // Код родителя мог не попасть в старый сохранённый снимок сессии.
    // Обновляем профиль один раз при открытии, не показывая загрузку.
    LaunchedEffect(session?.user?.role, session?.user?.childCode) {
        if (
            session?.user?.role == "student" &&
            session.user?.childCode.isNullOrBlank()
        ) {
            onRefreshSession()
        }
    }

    if (session?.learner == null) {
        SimpleProfile(
            container = container,
            session = session,
            serverUrl = serverUrl,
            onBack = onBack,
            onLogout = onLogout,
            onAbout = onAbout,
            onRefreshSession = onRefreshSession,
        )
        return
    }

    ScreenScaffold(title = "Профиль", onBack = onBack) { padding ->
        val gson = remember { ApiJson.gson }
        Load(
            key = "profile:stats",
            cache = container.cache,
            gson = gson,
            cacheKey = "profile:stats",
            cacheClass = MapDto::class.java,
            block = { container.api.map(null, null) },
        ) { data, _ ->
            val playful = data.grade in 1..4
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                item {
                    Card(Modifier.fillMaxWidth()) {
                        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                            Text(session?.learner?.emoji ?: "👤", fontSize = 44.sp)
                            Spacer(Modifier.width(14.dp))
                            Column(Modifier.weight(1f)) {
                                Text(
                                    session?.learner?.displayName
                                        ?: session?.user?.displayName
                                        ?: "Профиль",
                                    style = MaterialTheme.typography.titleLarge,
                                    fontWeight = FontWeight.Bold,
                                )
                                Text(
                                    when (session?.user?.role) {
                                        "student" -> "Ученик"
                                        "teacher" -> "Учитель"
                                        "parent" -> "Родитель"
                                        "admin" -> "Администратор"
                                        else -> "Семейный профиль"
                                    },
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Tag("${data.grade} класс")
                                    Tag(themeLabel(session?.theme))
                                }
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
                                "класс" to "${data.grade}",
                                "точность" to "${stats.accuracy}%",
                                "серия" to "${stats.streakDays}",
                            )
                        }
                    }
                }

                if (session?.user?.role == "student") {
                    item {
                        EducationCard(
                            container = container,
                            role = "student",
                            onSaved = onRefreshSession,
                        )
                    }
                    item {
                        ParentCodeCard(
                            code = session?.user?.childCode,
                            onRefresh = onRefreshSession,
                        )
                    }
                    item { SoundForParentCard() }
                }

                item {
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            data.stats?.let { stats ->
                                KeyValue("Точность", "${stats.accuracy}%")
                                KeyValue("Попыток", "${stats.totalAttempts}")
                                KeyValue("Верных", "${stats.totalCorrect}")
                                if (playful) KeyValue("Звёзды", "${stats.stars}")
                            }
                            KeyValue("Сервер", serverUrl)
                            KeyValue("Аккаунт", session?.user?.login ?: "семейный профиль")
                        }
                    }
                }

                if (onShop != null && playful) {
                    item {
                        Button(onClick = onShop, modifier = Modifier.fillMaxWidth()) {
                            Text("🛍 Магазин приключений")
                        }
                    }
                }

                item {
                    OutlinedButton(onClick = onSchedule, modifier = Modifier.fillMaxWidth()) {
                        Text("Расписание уроков")
                    }
                }

                item {
                    OutlinedButton(onClick = onAbout, modifier = Modifier.fillMaxWidth()) {
                        Text("О приложении")
                    }
                }

                item {
                    Button(onClick = onLogout, modifier = Modifier.fillMaxWidth()) {
                        Text("Выйти")
                    }
                }

                item {
                    InfoBox(
                        "В семейном профиле прогресс хранится на сервере и привязан к устройству. " +
                            "Чтобы вернуться к другому профилю, выйдите и выберите его на экране входа."
                    )
                }

                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }
}

@Composable
private fun ParentCodeCard(
    code: String?,
    onRefresh: () -> Unit,
) {
    val context = LocalContext.current
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = androidx.compose.material3.CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.primaryContainer,
        ),
    ) {
        Column(
            Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                "Код для родителя",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            if (code.isNullOrBlank()) {
                Text("Загружаем код…", style = MaterialTheme.typography.bodyMedium)
                TextButton(onClick = onRefresh) { Text("Обновить") }
            } else {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    Text(
                        code,
                        style = MaterialTheme.typography.headlineSmall,
                        fontWeight = FontWeight.Bold,
                        letterSpacing = 2.sp,
                    )
                    TextButton(
                        onClick = {
                            val clipboard = context.getSystemService(
                                Context.CLIPBOARD_SERVICE
                            ) as ClipboardManager
                            clipboard.setPrimaryClip(
                                ClipData.newPlainText("Код для родителя", code)
                            )
                            Toast.makeText(
                                context,
                                "Код скопирован",
                                Toast.LENGTH_SHORT,
                            ).show()
                        },
                    ) {
                        Text("Скопировать")
                    }
                }
                Text(
                    "Родитель вводит этот код при регистрации, чтобы видеть " +
                        "вашу статистику и подключить уведомления.",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun SoundForParentCard() {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    var granted by remember { mutableStateOf(SoundAlertService.hasDndAccess(context)) }
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                granted = SoundAlertService.hasDndAccess(context)
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    Card(Modifier.fillMaxWidth()) {
        Column(
            Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                "🔊 Звук для родителя",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
            )
            KeyValue(
                "Управление звуком",
                if (granted) "разрешено" else "не разрешено",
            )
            Text(
                "Если телефон на беззвучном, родитель сможет включить звук и " +
                    "дозвониться. Android требует одно системное разрешение — " +
                    "«Не беспокоить». Это не запрос на каждый звонок.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (!granted) {
                OutlinedButton(
                    onClick = { SoundAlertService.openDndSettings(context) },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Разрешить управление звуком") }
            }
        }
    }
}

private fun themeLabel(theme: String?): String = when (theme) {
    "strict" -> "строгий"
    "adult" -> "взрослый"
    else -> "игровой"
}

@Composable
private fun SimpleProfile(
    container: AppContainer,
    session: SessionDto?,
    serverUrl: String,
    onBack: () -> Unit,
    onLogout: () -> Unit,
    onAbout: () -> Unit,
    onRefreshSession: () -> Unit = {},
) {
    ScreenScaffold(title = "Профиль", onBack = onBack) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Card(Modifier.fillMaxWidth()) {
                    Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                        Text(session?.user?.avatar ?: "👤", fontSize = 44.sp)
                        Spacer(Modifier.width(14.dp))
                        Column(Modifier.weight(1f)) {
                            Text(
                                session?.user?.displayName ?: "Профиль",
                                style = MaterialTheme.typography.titleLarge,
                                fontWeight = FontWeight.Bold,
                            )
                            Text(
                                when (session?.user?.role) {
                                    "teacher" -> "Учитель"
                                    "parent" -> "Родитель"
                                    "admin" -> "Администратор"
                                    else -> "Пользователь"
                                },
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }

            if (session?.user?.role == "teacher") {
                item {
                    EducationCard(
                        container = container,
                        role = "teacher",
                        onSaved = onRefreshSession,
                    )
                }
            }

            item {
                Card(Modifier.fillMaxWidth()) {
                    Column(Modifier.padding(14.dp)) {
                        KeyValue("Логин", session?.user?.login ?: "—")
                        KeyValue("Роль", session?.user?.role ?: "—")
                        KeyValue("Сервер", serverUrl)
                    }
                }
            }

            item {
                OutlinedButton(onClick = onAbout, modifier = Modifier.fillMaxWidth()) {
                    Text("О приложении")
                }
            }

            item {
                Button(onClick = onLogout, modifier = Modifier.fillMaxWidth()) {
                    Text("Выйти")
                }
            }

            item { Spacer(Modifier.height(16.dp)) }
        }
    }
}

@Composable
fun ScheduleScreen(
    container: AppContainer,
    onBack: () -> Unit,
) {
    ScreenScaffold(title = "Расписание", onBack = onBack) { padding ->
        val gson = remember { ApiJson.gson }
        Load(
            key = "schedule",
            cache = container.cache,
            gson = gson,
            cacheKey = "schedule",
            cacheClass = ScheduleDto::class.java,
            block = { container.api.studentSchedule() },
        ) { data, _ ->
            val rows = mutableListOf<Pair<String, com.edumath.uchus.data.api.ScheduleItemDto?>>()
            data.weekdays.forEachIndexed { index, day ->
                val lessons = data.schedule.filter { it.weekday == index }
                if (lessons.isNotEmpty()) {
                    rows += day to null
                    lessons.forEach { rows += "" to it }
                }
            }

            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (data.schedule.isEmpty()) {
                    item { InfoBox("Расписание пока не заполнено учителем.") }
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
                                        (lesson.subjectIcon ?: "") + " " +
                                            (lesson.subjectName ?: "Урок"),
                                        fontWeight = FontWeight.SemiBold,
                                    )
                                    val subtitle = listOfNotNull(
                                        lesson.timeStart?.takeIf { it.isNotBlank() }?.let { start ->
                                            start + (lesson.timeEnd?.takeIf { it.isNotBlank() }?.let { end -> "–$end" } ?: "")
                                        },
                                        lesson.topicTitle?.takeIf { it.isNotBlank() },
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
                            }
                        }
                    }
                }
                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }
}
