package com.edumath.uchus.ui.location

import android.Manifest
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
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
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.LocationSharingRequest
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.data.location.LocationTrackingService
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.KeyValue
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone
import kotlinx.coroutines.launch

/**
 * Согласие ребёнка на передачу геолокации.
 *
 * По умолчанию передача выключена. Включение — только осознанным нажатием,
 * после системного разрешения на доступ к местоположению.
 */
@Composable
fun ChildLocationScreen(
    container: AppContainer,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var tick by remember { mutableIntStateOf(0) }
    var message by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var confirmClear by remember { mutableStateOf(false) }
    val tzMinutes = remember {
        TimeZone.getDefault().getOffset(System.currentTimeMillis()) / 60000
    }

    fun startTracking() {
        if (LocationTrackingService.hasPermission(context)) {
            LocationTrackingService.start(context)
        }
    }

    fun enableNow() {
        if (busy) return
        busy = true
        scope.launch {
            runCatching {
                apiCall { container.api.setLocationSharing(LocationSharingRequest(true)) }
            }.onSuccess {
                startTracking()
                message = "Геолокация включена. Точки передаются родителям, пока идёт служба."
                tick++
            }.onFailure { message = it.message }
            busy = false
        }
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { grants ->
        val granted = grants[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
            grants[Manifest.permission.ACCESS_COARSE_LOCATION] == true
        if (granted) {
            enableNow()
        } else {
            message = "Без разрешения на геолокацию передача невозможна."
        }
    }

    fun requestEnable() {
        if (LocationTrackingService.hasPermission(context)) {
            enableNow()
        } else {
            permissionLauncher.launch(
                arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION,
                )
            )
        }
    }

    fun disable() {
        if (busy) return
        busy = true
        scope.launch {
            runCatching {
                apiCall { container.api.setLocationSharing(LocationSharingRequest(false)) }
            }.onSuccess {
                LocationTrackingService.stop(context)
                message = "Передача остановлена. Новые точки родителям не отправляются."
                tick++
            }.onFailure { message = it.message }
            busy = false
        }
    }

    ScreenScaffold(title = "Геолокация", onBack = onBack) { padding ->
        Load(
            key = "child-location:$tick",
            block = { container.api.locationStatus(tzMinutes) },
        ) { data, refresh ->
            LaunchedEffect(data.enabled, tick) {
                if (data.enabled && LocationTrackingService.hasPermission(context)) {
                    LocationTrackingService.start(context)
                } else if (!data.enabled) {
                    LocationTrackingService.stop(context)
                }
            }
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
                            Modifier.padding(16.dp),
                            verticalArrangement = Arrangement.spacedBy(10.dp),
                        ) {
                            Text("🛰️ Передача местоположения родителям", fontWeight = FontWeight.Bold)
                            Text(
                                "Если включить, родители увидят твою последнюю точку на карте " +
                                    "и трек за день. История хранится ${data.retentionDays} дней. " +
                                    "Это работает только по твоему согласию.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            KeyValue("Сейчас", if (data.enabled) "включена" else "выключена")
                            KeyValue(
                                "Последняя точка",
                                formatLocal(data.lastPoint?.recordedAt) ?: "ещё нет",
                            )
                            data.lastPoint?.accuracy?.let {
                                KeyValue("Точность", "±${it.toInt()} м")
                            }
                        }
                    }
                }

                item {
                    if (data.enabled) {
                        OutlinedButton(
                            onClick = { disable() },
                            enabled = !busy,
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text(if (busy) "Останавливаем…" else "⏹ Остановить передачу") }
                    } else {
                        Button(
                            onClick = { requestEnable() },
                            enabled = !busy,
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text(if (busy) "Включаем…" else "📍 Делиться геопозицией") }
                    }
                }

                if (message != null) {
                    item { InfoBox(message!!) }
                }

                item {
                    InfoBox(
                        "Без разрешения «Местоположение» в настройках Android передача " +
                            "не запустится. Для фоновой работы оставь уведомление службы включённым."
                    )
                }

                item { SectionTitle("История") }
                item {
                    OutlinedButton(
                        onClick = { confirmClear = true },
                        modifier = Modifier.fillMaxWidth(),
                    ) { Text("🗑 Удалить историю геолокации") }
                }

                item { Spacer(Modifier.height(16.dp)) }
            }

            if (confirmClear) {
                AlertDialog(
                    onDismissRequest = { confirmClear = false },
                    title = { Text("Удалить историю?") },
                    text = { Text("Родитель не сможет посмотреть старые точки. Это действие необратимо.") },
                    confirmButton = {
                        TextButton(onClick = {
                            confirmClear = false
                            scope.launch {
                                runCatching { apiCall { container.api.clearLocationHistory() } }
                                    .onSuccess {
                                        message = "История геолокации удалена"
                                        refresh()
                                    }
                                    .onFailure { message = it.message }
                            }
                        }) { Text("Удалить") }
                    },
                    dismissButton = {
                        TextButton(onClick = { confirmClear = false }) { Text("Отмена") }
                    },
                )
            }
        }
    }
}

private fun formatLocal(value: String?): String? {
    if (value.isNullOrBlank()) return null
    return runCatching {
        val parser = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", Locale.US).apply {
            timeZone = TimeZone.getTimeZone("UTC")
        }
        val date = parser.parse(value.take(19)) ?: return value
        SimpleDateFormat("dd.MM, HH:mm", Locale("ru")).format(date)
    }.getOrDefault(value)
}
