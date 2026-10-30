package com.edumath.uchus.ui.parent

import android.annotation.SuppressLint
import android.graphics.Color
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.ApiJson
import com.edumath.uchus.data.api.LocationTrackDto
import com.edumath.uchus.data.api.ParentLocationsDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.EmptyBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.LoadingBox
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.StatsRow
import java.text.SimpleDateFormat
import java.util.Calendar
import java.util.Date
import java.util.Locale
import java.util.TimeZone
import kotlinx.coroutines.launch

/**
 * Карта детей для родителя: последние точки всех детей и трек за выбранный день.
 * Карта — локальный Leaflet в WebView, тайлы OpenStreetMap (без API-ключа).
 */
@Composable
fun ParentMapScreen(
    container: AppContainer,
    learnerId: Int,
    onBack: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    val tzMinutes = remember {
        TimeZone.getDefault().getOffset(System.currentTimeMillis()) / 60000
    }
    var overview by remember { mutableStateOf<ParentLocationsDto?>(null) }
    var overviewError by remember { mutableStateOf<String?>(null) }
    var track by remember { mutableStateOf<LocationTrackDto?>(null) }
    var trackError by remember { mutableStateOf<String?>(null) }
    var trackLoading by remember { mutableStateOf(false) }
    var selectedId by remember { mutableIntStateOf(learnerId) }
    var date by remember { mutableStateOf(todayIso()) }
    var tick by remember { mutableIntStateOf(0) }
    var message by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }

    LaunchedEffect(tick) {
        overviewError = null
        runCatching { apiCall { container.api.parentLocations(tzMinutes) } }
            .onSuccess { data ->
                overview = data
                if (selectedId == 0 || data.children.none { it.learner?.id == selectedId }) {
                    selectedId = data.children.firstOrNull()?.learner?.id ?: 0
                }
            }
            .onFailure { overviewError = it.message }
    }

    LaunchedEffect(selectedId, date, tick) {
        if (selectedId == 0) return@LaunchedEffect
        trackLoading = true
        trackError = null
        runCatching { apiCall { container.api.parentChildLocation(selectedId, date, tzMinutes) } }
            .onSuccess { track = it }
            .onFailure { trackError = it.message }
        trackLoading = false
    }

    ScreenScaffold(title = "Карта детей", onBack = onBack) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (overviewError != null) {
                item { InfoBox(overviewError!!) }
            }
            val children = overview?.children.orEmpty()
            if (overview == null) {
                item { LoadingBox() }
            } else if (children.isEmpty()) {
                item { EmptyBox("Привяжите ребёнка, чтобы видеть его на карте.", "🗺") }
            } else {
                item {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(children) { child ->
                            val info = child.learner
                            FilterChip(
                                selected = selectedId == info?.id,
                                onClick = { selectedId = info?.id ?: 0 },
                                label = {
                                    Text(
                                        listOfNotNull(info?.avatar, info?.name)
                                            .joinToString(" ")
                                            .ifBlank { "Ребёнок" }
                                    )
                                },
                            )
                        }
                    }
                }
                item {
                    DateRow(
                        date = date,
                        minDate = shiftDate(todayIso(), -13),
                        maxDate = todayIso(),
                        onChange = { date = it },
                    )
                }
                item {
                    Card(Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(6.dp)) {
                            MapWebView(
                                track = track,
                                overview = overview,
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .height(360.dp),
                            )
                        }
                    }
                }

                item {
                    val info = children.firstOrNull { it.learner?.id == selectedId }
                    val sharing = info?.sharing
                    val last = info?.lastPoint
                    Card(Modifier.fillMaxWidth()) {
                        Column(
                            Modifier.padding(14.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            Text(
                                info?.learner?.name ?: "Ребёнок",
                                fontWeight = FontWeight.Bold,
                                style = MaterialTheme.typography.titleMedium,
                            )
                            Text(
                                when {
                                    sharing?.enabled != true -> "Передача геолокации выключена"
                                    last == null -> "Точек пока нет"
                                    else -> "Последняя точка: ${formatLocal(last.recordedAt)}"
                                },
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            if (sharing?.enabled != true) {
                                Spacer(Modifier.height(6.dp))
                                OutlinedButton(
                                    onClick = {
                                        if (busy) return@OutlinedButton
                                        busy = true
                                        scope.launch {
                                            runCatching {
                                                apiCall { container.api.requestChildLocation(selectedId) }
                                            }.onSuccess {
                                                message = it.message ?: "Просьба отправлена"
                                            }.onFailure { message = it.message }
                                            busy = false
                                        }
                                    },
                                    enabled = !busy,
                                ) { Text("🔔 Попросить включить геолокацию") }
                            }
                        }
                    }
                }

                if (message != null) {
                    item { InfoBox(message!!) }
                }

                item {
                    val summary = track?.summary
                    if (trackLoading && track == null) {
                        LoadingBox("Загружаем трек…")
                    } else if (trackError != null) {
                        InfoBox(trackError!!)
                    } else if (summary != null) {
                        StatsRow(
                            "точек" to "${summary.points}",
                            "путь" to formatDistance(summary.distanceM),
                            "время" to formatDuration(summary.durationMin),
                        )
                    }
                }

                item {
                    if (track != null && track!!.points.isEmpty()) {
                        val sharing = track!!.sharing
                        InfoBox(
                            if (sharing?.enabled != true) {
                                "Ребёнок выключил передачу геолокации."
                            } else {
                                "За ${prettyDate(date)} точек нет."
                            }
                        )
                    }
                }

                val points = track?.points.orEmpty()
                if (points.isNotEmpty()) {
                    item { SectionTitle("Метки времени", trailing = "${points.size}") }
                    itemsIndexed(points.asReversed().take(300)) { _, point ->
                        Card(Modifier.fillMaxWidth()) {
                            Row(
                                Modifier.padding(horizontal = 12.dp, vertical = 9.dp),
                                verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
                            ) {
                                Text(
                                    point.time ?: formatTime(point.recordedAt),
                                    fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.primary,
                                )
                                Spacer(Modifier.weight(1f))
                                Column(horizontalAlignment = androidx.compose.ui.Alignment.End) {
                                    Text(
                                        "%.5f, %.5f".format(Locale.US, point.lat, point.lon),
                                        style = MaterialTheme.typography.bodySmall,
                                    )
                                    val bits = mutableListOf<String>()
                                    point.accuracy?.let { bits.add("±${it.toInt()} м") }
                                    point.battery?.let { bits.add("🔋$it%") }
                                    point.speed?.let { bits.add("%.1f км/ч".format(it * 3.6)) }
                                    if (bits.isNotEmpty()) {
                                        Text(
                                            bits.joinToString(" · "),
                                            style = MaterialTheme.typography.labelSmall,
                                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        )
                                    }
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

@Composable
private fun MapWebView(
    track: LocationTrackDto?,
    overview: ParentLocationsDto?,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    var ready by remember { mutableStateOf(false) }
    val trackJson = remember(track) {
        if (track == null) "null" else ApiJson.gson.toJson(track)
    }
    val overviewJson = remember(overview) {
        if (overview == null) "null" else ApiJson.gson.toJson(overview)
    }
    val webView = remember {
        @SuppressLint("SetJavaScriptEnabled")
        WebView(context).apply {
            setBackgroundColor(Color.parseColor("#eef4ff"))
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = true
            settings.loadsImagesAutomatically = true
            settings.setSupportZoom(false)
            settings.builtInZoomControls = false
            settings.displayZoomControls = false
            webViewClient = object : WebViewClient() {
                override fun onPageFinished(view: WebView?, url: String?) {
                    ready = true
                }
            }
            loadUrl("file:///android_asset/parent_map.html")
        }
    }

    LaunchedEffect(ready, trackJson, overviewJson) {
        if (!ready) return@LaunchedEffect
        webView.evaluateJavascript("window.showOverview($overviewJson);", null)
        webView.evaluateJavascript("window.showTrack($trackJson);", null)
    }

    DisposableEffect(Unit) {
        onDispose {
            runCatching {
                webView.stopLoading()
                webView.destroy()
            }
        }
    }

    AndroidView(
        factory = { webView },
        modifier = modifier,
    )
}

@Composable
private fun DateRow(
    date: String,
    minDate: String,
    maxDate: String,
    onChange: (String) -> Unit,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = androidx.compose.ui.Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        OutlinedButton(
            onClick = { onChange(shiftDate(date, -1)) },
            enabled = date > minDate,
            contentPadding = PaddingValues(horizontal = 10.dp),
        ) { Text("‹") }
        Text(
            prettyDate(date),
            modifier = Modifier.weight(1f),
            fontWeight = FontWeight.SemiBold,
        )
        if (date != maxDate) {
            TextButton(onClick = { onChange(maxDate) }) { Text("Сегодня") }
        }
        OutlinedButton(
            onClick = { onChange(shiftDate(date, 1)) },
            enabled = date < maxDate,
            contentPadding = PaddingValues(horizontal = 10.dp),
        ) { Text("›") }
    }
}

private fun todayIso(): String =
    SimpleDateFormat("yyyy-MM-dd", Locale.US).format(Date())

private fun shiftDate(value: String, days: Int): String {
    return runCatching {
        val parser = SimpleDateFormat("yyyy-MM-dd", Locale.US)
        val calendar = Calendar.getInstance().apply { time = parser.parse(value) ?: Date() }
        calendar.add(Calendar.DAY_OF_YEAR, days)
        parser.format(calendar.time)
    }.getOrDefault(value)
}

private fun prettyDate(value: String): String {
    return runCatching {
        val parser = SimpleDateFormat("yyyy-MM-dd", Locale.US)
        val date = parser.parse(value) ?: return value
        SimpleDateFormat("dd.MM.yyyy", Locale("ru")).format(date)
    }.getOrDefault(value)
}

private fun formatLocal(value: String?): String {
    if (value.isNullOrBlank()) return "—"
    return runCatching {
        val parser = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        val date = parser.parse(value.take(19)) ?: return value
        SimpleDateFormat("dd.MM, HH:mm", Locale("ru")).format(date)
    }.getOrDefault(value)
}

private fun formatTime(value: String?): String {
    if (value.isNullOrBlank()) return "—"
    return runCatching {
        val parser = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        val date = parser.parse(value.take(19)) ?: return value
        SimpleDateFormat("HH:mm", Locale("ru")).format(date)
    }.getOrDefault(value)
}

private fun formatDistance(meters: Double): String {
    if (meters <= 0) return "0 м"
    if (meters < 1000) return "${meters.toInt()} м"
    return String.format(Locale.US, "%.1f км", meters / 1000)
}

private fun formatDuration(minutes: Int): String {
    if (minutes <= 0) return "0 мин"
    if (minutes < 60) return "$minutes мин"
    return "${minutes / 60} ч ${minutes % 60} мин"
}
