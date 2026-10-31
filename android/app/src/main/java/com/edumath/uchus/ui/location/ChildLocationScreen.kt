package com.edumath.uchus.ui.location

import android.Manifest
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
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
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.data.location.LocationTrackingService
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.KeyValue
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import java.text.SimpleDateFormat
import java.util.Locale
import java.util.TimeZone
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Геолокация ребёнка.
 *
 * Согласие больше не запрашивается: передача включена всегда. Экран показывает
 * статус, помогает выдать системное разрешение и принимает команду родителя
 * «включить геолокацию» на этом телефоне.
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
    var forcePending by remember { mutableStateOf(false) }
    var autoAsked by remember { mutableStateOf(false) }
    val tzMinutes = remember {
        TimeZone.getDefault().getOffset(System.currentTimeMillis()) / 60000
    }

    fun acknowledge() {
        scope.launch {
            runCatching { apiCall { container.api.ackLocationForce() } }
                .onSuccess { forcePending = false }
        }
    }

    fun startTracking(ackForce: Boolean) {
        if (!LocationTrackingService.hasPermission(context)) return
        LocationTrackingService.start(context)
        if (ackForce) acknowledge()
    }

    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestMultiplePermissions()
    ) { grants ->
        val granted = grants[Manifest.permission.ACCESS_FINE_LOCATION] == true ||
            grants[Manifest.permission.ACCESS_COARSE_LOCATION] == true
        if (granted) {
            message = "Доступ к геолокации разрешён — родитель видит твою позицию."
            startTracking(forcePending)
        } else {
            message = "Без разрешения «Местоположение» передача не запустится. " +
                "Разрешите его в настройках Android."
        }
    }

    fun requestPermissionOrStart() {
        if (LocationTrackingService.hasPermission(context)) {
            startTracking(forcePending)
            message = "Служба геолокации запущена."
        } else {
            permissionLauncher.launch(
                arrayOf(
                    Manifest.permission.ACCESS_FINE_LOCATION,
                    Manifest.permission.ACCESS_COARSE_LOCATION,
                )
            )
        }
    }

    fun openSystemSettings() {
        val intent = Intent(
            Settings.ACTION_APPLICATION_DETAILS_SETTINGS,
            Uri.fromParts("package", context.packageName, null),
        )
        runCatching { context.startActivity(intent) }
        message = "Включите «Местоположение» для приложения «Школьник», затем вернитесь сюда."
    }

    // Возврат из настроек Android — сразу проверяем разрешение и статус.
    val lifecycleOwner = LocalLifecycleOwner.current
    DisposableEffect(lifecycleOwner) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) tick++
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    // Статус и команда родителя проверяются сами, без кнопок «подтвердить».
    LaunchedEffect(Unit) {
        while (true) {
            delay(30_000)
            tick++
        }
    }

    ScreenScaffold(title = "Геолокация", onBack = onBack) { padding ->
        Load(
            key = "child-location:$tick",
            block = { container.api.locationStatus(tzMinutes) },
        ) { data, refresh ->
            forcePending = data.forcePending || data.settings?.forcePending == true
            val granted = LocationTrackingService.hasPermission(context)
            LaunchedEffect(data.forcePending, data.lastPoint?.recordedAt, tick) {
                if (LocationTrackingService.hasPermission(context)) {
                    startTracking(forcePending)
                } else if (!autoAsked) {
                    autoAsked = true
                    permissionLauncher.launch(
                        arrayOf(
                            Manifest.permission.ACCESS_FINE_LOCATION,
                            Manifest.permission.ACCESS_COARSE_LOCATION,
                        )
                    )
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
                            Text("🛰️ Родитель видит, где ты находишься", fontWeight = FontWeight.Bold)
                            Text(
                                "Передача местоположения работает постоянно. Родитель видит " +
                                    "последнюю точку на карте и историю за день. История хранится " +
                                    "${data.retentionDays} дней.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            KeyValue(
                                "Статус",
                                when {
                                    !granted -> "нужно разрешение"
                                    LocationTrackingService.isRunning -> "включена, передача идёт"
                                    else -> "разрешение есть, запускаем службу"
                                },
                            )
                            if (!granted) {
                                Text(
                                    "Разрешите «Местоположение» — без этого родитель не увидит точку.",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.error,
                                )
                            }
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

                if (forcePending) {
                    item {
                        InfoBox(
                            "📍 Родитель включил геолокацию. Разрешите доступ к " +
                                "местоположению — передача запустится сама, подтверждать " +
                                "ничего не нужно."
                        )
                    }
                }

                item {
                    Button(
                        onClick = { requestPermissionOrStart() },
                        enabled = !busy,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            when {
                                busy -> "Запускаем…"
                                LocationTrackingService.hasPermission(context) ->
                                    "📍 Обновить геолокацию"
                                else -> "📍 Разрешить геолокацию"
                            }
                        )
                    }
                }

                if (!granted) {
                    item {
                        OutlinedButton(
                            onClick = { openSystemSettings() },
                            modifier = Modifier.fillMaxWidth(),
                        ) { Text("⚙️ Открыть настройки Android") }
                    }
                }

                if (message != null) {
                    item { InfoBox(message!!) }
                }

                item {
                    InfoBox(
                        "Для фоновой работы оставь уведомление службы включённым. " +
                            "Если геолокация выключена в настройках Android, приложение " +
                            "напомнит включить её после команды родителя."
                    )
                }

                item { Spacer(Modifier.height(16.dp)) }
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
