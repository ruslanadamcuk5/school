package com.edumath.uchus.ui.about

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.edumath.uchus.BuildConfig
import com.edumath.uchus.data.api.ApiException
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.ErrorBox
import com.edumath.uchus.ui.common.InfoBox
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AboutScreen(
    serverUrl: String,
    api: com.edumath.uchus.data.api.ApiService,
    onBack: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var status by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var checking by remember { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("О приложении") },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Назад")
                    }
                },
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text("Учусь", style = MaterialTheme.typography.headlineSmall, fontWeight = FontWeight.Bold)
            Text(
                "Версия ${BuildConfig.VERSION_NAME} (${BuildConfig.VERSION_CODE})",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(
                "Школьная платформа для 1–11 классов: математика, языки и литература, «Человек и мир».",
                style = MaterialTheme.typography.bodyMedium,
            )

            Spacer(Modifier.height(4.dp))
            InfoBox("Сервер: $serverUrl")

            Button(
                onClick = {
                    checking = true
                    error = null
                    status = null
                    scope.launch {
                        runCatching { apiCall { api.health() } }
                            .onSuccess { health ->
                                status = if (health.status == "ok") {
                                    "Сервер доступен, база данных в порядке."
                                } else {
                                    "Сервер отвечает, но база недоступна."
                                }
                            }
                            .onFailure { failure ->
                                error = when (failure) {
                                    is ApiException -> failure.message
                                    else -> failure.message ?: "Неизвестная ошибка"
                                }
                            }
                        checking = false
                    }
                },
                enabled = !checking,
                modifier = Modifier.fillMaxWidth(),
            ) {
                Text(if (checking) "Проверяем…" else "Проверить связь")
            }

            status?.let { InfoBox(it, MaterialTheme.colorScheme.primaryContainer) }
            error?.let { ErrorBox(it) }

            Spacer(Modifier.height(8.dp))
            Text(
                "Данные приложения хранятся на вашем сервере. Приложение не отправляет их третьим лицам.",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}
