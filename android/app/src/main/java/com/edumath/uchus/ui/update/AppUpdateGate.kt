package com.edumath.uchus.ui.update

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import com.edumath.uchus.BuildConfig
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.AppVersionDto
import com.edumath.uchus.data.api.apiCall
import java.util.Locale
import kotlin.math.roundToInt
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private sealed interface UpdatePhase {
    data object Idle : UpdatePhase
    data class Downloading(
        val progress: Float,
        val downloaded: Long,
        val total: Long,
    ) : UpdatePhase

    data object Verifying : UpdatePhase
    data object Installing : UpdatePhase
    data object NeedPermission : UpdatePhase
    data class Error(val message: String) : UpdatePhase
}

/**
 * Проверяет опубликованную версию и обновляет приложение внутри него самого:
 * скачивание с прогрессом → проверка SHA-256 и подписи → системный установщик.
 *
 * После замены APK приложение пытается открыться само и показывает
 * «Обновление выполнено». Системное подтверждение установки Android может
 * оставить — обойти его обычное приложение не имеет права.
 */
@Composable
fun AppUpdateGate(container: AppContainer) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val lifecycleOwner = LocalLifecycleOwner.current
    var update by remember { mutableStateOf<AppVersionDto?>(null) }
    var dismissedCode by rememberSaveable {
        mutableStateOf(UpdateStateStore.dismissedCode(context))
    }
    var phase by remember { mutableStateOf<UpdatePhase>(UpdatePhase.Idle) }
    var completedVersion by remember { mutableStateOf<String?>(null) }
    var downloadJob by remember { mutableStateOf<Job?>(null) }
    var lastCheckAt by remember { mutableLongStateOf(0L) }

    /**
     * Проверка опубликованной версии. Вызывается при запуске, при возврате
     * в приложение и раз в 10 минут — новая версия появляется без перезапуска.
     */
    fun checkForUpdate(force: Boolean) {
        val now = System.currentTimeMillis()
        if (!force && now - lastCheckAt < 2 * 60_000L) return
        lastCheckAt = now
        scope.launch {
            val busy = phase is UpdatePhase.Downloading ||
                phase is UpdatePhase.Verifying ||
                phase is UpdatePhase.Installing ||
                phase is UpdatePhase.NeedPermission
            if (busy) return@launch
            val info = findUpdate(container) ?: return@launch
            val skipped = UpdateStateStore.dismissedCode(context)
            if (skipped >= info.versionCode) {
                update = null
                return@launch
            }
            if (update?.versionCode != info.versionCode) {
                update = info
            }
        }
    }

    // Итог установки: новая версия уже запущена, а в хранилище остался
    // номер версии, которую устанавливали.
    LaunchedEffect(Unit) {
        val pending = UpdateStateStore.pendingCode(context)
        if (pending > 0 && BuildConfig.VERSION_CODE >= pending) {
            completedVersion = UpdateStateStore.pendingName(context)
                ?.takeIf { it.isNotBlank() }
                ?: BuildConfig.VERSION_NAME
            UpdateStateStore.clearPending(context)
            UpdateStateStore.clearError(context)
        }
    }

    LaunchedEffect(Unit) {
        checkForUpdate(force = true)
    }

    // Пока приложение открыто, раз в 10 минут проверяем новую версию.
    LaunchedEffect(Unit) {
        while (true) {
            delay(10 * 60_000L)
            checkForUpdate(force = true)
        }
    }

    LaunchedEffect(update) {
        if (update == null) return@LaunchedEffect
        UpdateStateStore.error(context)?.let { message ->
            phase = UpdatePhase.Error(message)
            UpdateStateStore.clearError(context)
        }
    }

    fun startDownload() {
        val release = update ?: return
        if (!ApkUpdater.canInstallPackages(context)) {
            phase = UpdatePhase.NeedPermission
            ApkUpdater.openInstallPermissionSettings(context)
            return
        }

        downloadJob?.cancel()
        phase = UpdatePhase.Downloading(0f, 0L, release.size)
        downloadJob = scope.launch {
            try {
                val apk = ApkUpdater.download(context, release) { progress ->
                    phase = UpdatePhase.Downloading(
                        progress.fraction,
                        progress.downloaded,
                        progress.total,
                    )
                }
                phase = UpdatePhase.Verifying
                if (!ApkUpdater.isTrustedUpdate(context, apk)) {
                    apk.delete()
                    phase = UpdatePhase.Error(
                        "Подпись файла не совпала с установленным приложением. " +
                            "Обновление отменено."
                    )
                    return@launch
                }
                UpdateStateStore.rememberPending(context, release)
                phase = UpdatePhase.Installing
                ApkUpdater.install(context, apk)
            } catch (_: CancellationException) {
                phase = UpdatePhase.Idle
            } catch (failure: Throwable) {
                val message = failure.message
                    ?.takeIf { it.isNotBlank() }
                    ?: "Не удалось скачать обновление"
                UpdateStateStore.clearPending(context)
                UpdateStateStore.setError(context, message)
                phase = UpdatePhase.Error(message)
            }
        }
    }

    // Вернулись из настроек «Установка неизвестных приложений» — продолжаем.
    DisposableEffect(lifecycleOwner, phase) {
        val observer = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                when {
                    phase is UpdatePhase.NeedPermission &&
                        ApkUpdater.canInstallPackages(context) -> {
                        phase = UpdatePhase.Idle
                        startDownload()
                    }

                    // Вернулись из установщика, но версия не изменилась:
                    // значит, установку отменили или Android её отклонил.
                    phase is UpdatePhase.Installing -> {
                        phase = UpdatePhase.Error(
                            "Установка не завершилась. Попробуйте ещё раз."
                        )
                    }

                    phase is UpdatePhase.Idle -> checkForUpdate(force = false)
                }
            }
        }
        lifecycleOwner.lifecycle.addObserver(observer)
        onDispose { lifecycleOwner.lifecycle.removeObserver(observer) }
    }

    completedVersion?.let { version ->
        AlertDialog(
            onDismissRequest = { completedVersion = null },
            title = { Text("Обновление выполнено") },
            text = {
                Text(
                    "Приложение обновлено до версии $version. " +
                        "Все данные и профиль сохранены."
                )
            },
            confirmButton = {
                TextButton(onClick = { completedVersion = null }) {
                    Text("Продолжить")
                }
            },
        )
        return
    }

    val release = update
    if (release == null || dismissedCode >= release.versionCode) return

    val version = release.versionName?.takeIf { it.isNotBlank() }
        ?: release.versionCode.toString()
    val notes = release.notes?.trim().orEmpty()
    val busy = phase is UpdatePhase.Downloading ||
        phase is UpdatePhase.Verifying ||
        phase is UpdatePhase.Installing

    AlertDialog(
        onDismissRequest = {
            if (!busy) {
                UpdateStateStore.rememberDismissed(context, release.versionCode)
                dismissedCode = release.versionCode
            }
        },
        title = {
            Text(
                when (phase) {
                    is UpdatePhase.Downloading -> "Загрузка обновления"
                    is UpdatePhase.Verifying -> "Проверяем обновление"
                    is UpdatePhase.Installing -> "Устанавливаем обновление"
                    is UpdatePhase.NeedPermission -> "Разрешите установку"
                    is UpdatePhase.Error -> "Не удалось обновить"
                    else -> "Доступно обновление"
                }
            )
        },
        text = {
            Column(
                modifier = Modifier
                    .heightIn(max = 360.dp)
                    .verticalScroll(rememberScrollState()),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                when (val current = phase) {
                    is UpdatePhase.Downloading -> {
                        LinearProgressIndicator(
                            progress = { current.progress },
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 8.dp),
                        )
                        Text(
                            "${(current.progress * 100).roundToInt()}% · " +
                                "${formatBytes(current.downloaded)} из " +
                                formatBytes(current.total),
                            style = MaterialTheme.typography.bodyMedium,
                            fontWeight = FontWeight.Bold,
                        )
                        Text(
                            "Файл скачивается внутри приложения. После загрузки " +
                                "установщик откроется автоматически.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }

                    is UpdatePhase.Verifying -> {
                        CircularProgressIndicator()
                        Text("Сверяем SHA-256 и подпись с установленной версией…")
                    }

                    is UpdatePhase.Installing -> {
                        Text(
                            "Системный установщик сейчас откроется. Нажмите " +
                                "«Установить» — Android требует этот шаг для любого APK. " +
                                "После установки приложение закроется и откроется само."
                        )
                        Text(
                            "Мы уже проверили файл: он подписан тем же ключом, что и " +
                                "текущее приложение, а контрольная сумма совпала.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }

                    is UpdatePhase.NeedPermission -> {
                        Text(
                            "Чтобы обновление установилось без браузера и папки " +
                                "«Загрузки», разрешите приложению установку. " +
                                "Нажмите «Разрешить» и включите переключатель."
                        )
                        Text(
                            "Это стандартное разрешение Android для обновления " +
                                "приложения с сайта.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }

                    is UpdatePhase.Error -> {
                        Text(current.message)
                        Text(
                            "Можно попробовать снова. Если ошибка повторится, " +
                                "скачайте APK с сайта вручную.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }

                    else -> {
                        Text(
                            "На сайте версия $version. Что нового:",
                            style = MaterialTheme.typography.bodyMedium,
                        )
                        if (notes.isNotEmpty()) {
                            Text(
                                notes,
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                        Text(
                            "Обновление скачается внутри приложения, будет проверено " +
                                "по SHA-256 и подписи, затем сразу откроется установщик.",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                        if (release.size > 0) {
                            Text(
                                "Размер: ${formatBytes(release.size)}",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        }
                    }
                }
            }
        },
        confirmButton = {
            when (phase) {
                is UpdatePhase.Idle -> TextButton(onClick = { startDownload() }) {
                    Text("Обновить")
                }

                is UpdatePhase.NeedPermission -> TextButton(
                    onClick = { ApkUpdater.openInstallPermissionSettings(context) },
                ) {
                    Text("Разрешить")
                }

                is UpdatePhase.Error -> TextButton(onClick = { startDownload() }) {
                    Text("Повторить")
                }

                is UpdatePhase.Downloading -> TextButton(
                    onClick = {
                        downloadJob?.cancel()
                        phase = UpdatePhase.Idle
                    },
                ) {
                    Text("Отмена")
                }

                else -> Unit
            }
        },
        dismissButton = {
            when (phase) {
                is UpdatePhase.Verifying, is UpdatePhase.Installing -> Unit
                else -> TextButton(
                    onClick = {
                        if (phase is UpdatePhase.Downloading) {
                            downloadJob?.cancel()
                        }
                        UpdateStateStore.rememberDismissed(context, release.versionCode)
                        dismissedCode = release.versionCode
                    },
                ) {
                    Text(
                        if (phase is UpdatePhase.Downloading) "Отменить"
                        else "Позже"
                    )
                }
            }
        },
    )
}

private suspend fun findUpdate(container: AppContainer): AppVersionDto? {
    val info = runCatching { apiCall { container.api.appVersion() } }.getOrNull()
        ?: return null
    return info.takeIf {
        it.ok &&
            it.versionCode > BuildConfig.VERSION_CODE &&
            !it.downloadUrl.isNullOrBlank()
    }
}

private fun formatBytes(bytes: Long): String {
    if (bytes <= 0) return "0 КБ"
    val mb = bytes / (1024.0 * 1024.0)
    return if (mb >= 1.0) {
        String.format(Locale.US, "%.1f МБ", mb)
    } else {
        "${(bytes / 1024).coerceAtLeast(1)} КБ"
    }
}
