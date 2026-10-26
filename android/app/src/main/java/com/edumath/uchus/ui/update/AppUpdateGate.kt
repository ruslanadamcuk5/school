package com.edumath.uchus.ui.update

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import com.edumath.uchus.BuildConfig
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.AppVersionDto
import com.edumath.uchus.data.api.apiCall

/**
 * Проверяет опубликованную на сайте версию приложения и предлагает обновиться.
 *
 * Проверка выполняется один раз за запуск после загрузки сохранённой сессии.
 * Если сервер недоступен или версия не новее — ничего не показываем.
 */
@Composable
fun AppUpdateGate(container: AppContainer) {
    val context = LocalContext.current
    var update by remember { mutableStateOf<AppVersionDto?>(null) }
    var dismissed by rememberSaveable { mutableStateOf(false) }

    LaunchedEffect(Unit) {
        val info = runCatching { apiCall { container.api.appVersion() } }.getOrNull()
            ?: return@LaunchedEffect
        if (
            info.ok &&
            info.versionCode > BuildConfig.VERSION_CODE &&
            !info.downloadUrl.isNullOrBlank()
        ) {
            update = info
        }
    }

    val release = update
    if (release == null || dismissed) return

    val version = release.versionName?.takeIf { it.isNotBlank() }
        ?: release.versionCode.toString()
    val notes = release.notes?.trim().orEmpty()

    AlertDialog(
        onDismissRequest = { dismissed = true },
        title = { Text("Доступно обновление") },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text(
                    "На сайте уже версия $version. Установите её, чтобы получить " +
                        "новые возможности и исправления."
                )
                if (notes.isNotEmpty()) {
                    Text(
                        notes,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    val url = release.downloadUrl
                    if (!url.isNullOrBlank()) {
                        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                        runCatching { context.startActivity(intent) }
                    }
                    dismissed = true
                },
            ) {
                Text("Скачать")
            }
        },
        dismissButton = {
            TextButton(onClick = { dismissed = true }) {
                Text("Позже")
            }
        },
    )
}
