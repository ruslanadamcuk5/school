package com.edumath.uchus.ui.common

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
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
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.data.cache.JsonCache
import com.google.gson.Gson

/** Экран с верхней панелью и кнопкой «назад». */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ScreenScaffold(
    title: String,
    onBack: (() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {},
    content: @Composable (PaddingValues) -> Unit,
) {
    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(title, fontWeight = FontWeight.Bold) },
                navigationIcon = {
                    if (onBack != null) {
                        IconButton(onClick = onBack) {
                            Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Назад")
                        }
                    }
                },
                actions = actions,
            )
        },
    ) { padding -> content(padding) }
}

/**
 * Загрузка данных с повтором и необязательным кэшем ответа (для чтения офлайн).
 * Показывает ранее сохранённый JSON, если сеть недоступна.
 */
@Composable
fun <T : Any> Load(
    key: Any,
    cache: JsonCache? = null,
    gson: Gson? = null,
    cacheKey: String? = null,
    cacheClass: Class<T>? = null,
    block: suspend () -> T,
    content: @Composable (T, () -> Unit) -> Unit,
) {
    var data by remember(key) { mutableStateOf<T?>(null) }
    var error by remember(key) { mutableStateOf<String?>(null) }
    var loading by remember(key) { mutableStateOf(true) }
    var fromCache by remember(key) { mutableStateOf(false) }
    var tick by remember(key) { mutableIntStateOf(0) }

    LaunchedEffect(key, tick) {
        loading = true
        error = null
        runCatching { apiCall { block() } }
            .onSuccess { value ->
                data = value
                fromCache = false
                if (cache != null && gson != null && cacheKey != null) {
                    runCatching { cache.put(cacheKey, gson.toJson(value)) }
                }
            }
            .onFailure { throwable ->
                error = throwable.message ?: "Не удалось загрузить данные"
                if (
                    data == null &&
                    cache != null && gson != null &&
                    cacheKey != null && cacheClass != null
                ) {
                    val raw = cache.get(cacheKey)
                    if (raw != null) {
                        val restored = runCatching { gson.fromJson(raw, cacheClass) }.getOrNull()
                        if (restored != null) {
                            data = restored
                            fromCache = true
                        }
                    }
                }
            }
        loading = false
    }

    val current = data
    Column(Modifier.fillMaxSize()) {
        when {
            current == null && loading -> LoadingBox()
            current == null -> ErrorBox(error ?: "Нет данных") { tick++ }
            else -> {
                if (fromCache) {
                    InfoBox("Нет связи — показаны сохранённые данные.")
                }
                if (error != null) {
                    ErrorBox(error!!) { tick++ }
                }
                content(current) { tick++ }
            }
        }
    }
}

/** Заголовок раздела. */
@Composable
fun SectionTitle(text: String, trailing: String? = null) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(top = 8.dp, bottom = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            text,
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.weight(1f),
        )
        if (trailing != null) {
            Text(
                trailing,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/** Небольшая метка (класс, звёзды, статус). */
@Composable
fun Tag(text: String) {
    Surface(
        color = MaterialTheme.colorScheme.secondaryContainer,
        contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
        shape = RoundedCornerShape(8.dp),
    ) {
        Text(
            text,
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
            style = MaterialTheme.typography.labelSmall,
        )
    }
}

/** Строка «подпись — значение». */
@Composable
fun KeyValue(label: String, value: String) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.weight(1f),
        )
        Text(value, style = MaterialTheme.typography.bodySmall, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
fun VSpace(height: Int = 8) {
    Spacer(Modifier.height(height.dp))
}

@Composable
fun HSpace(width: Int = 8) {
    Spacer(Modifier.width(width.dp))
}

/** Ряд статистики. */
@Composable
fun StatsRow(vararg items: Pair<String, String>) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        items.forEach { (label, value) -> StatPill(label, value) }
    }
}
