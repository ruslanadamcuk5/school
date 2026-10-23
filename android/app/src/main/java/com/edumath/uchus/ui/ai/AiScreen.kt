package com.edumath.uchus.ui.ai

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.AiAskRequest
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.ErrorBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import kotlinx.coroutines.launch

private data class ChatLine(val fromUser: Boolean, val text: String)

@Composable
fun AiScreen(
    container: AppContainer,
    onBack: () -> Unit,
) {
    val scope = rememberCoroutineScope()
    var question by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val history = remember { mutableStateListOf<ChatLine>() }

    ScreenScaffold(title = "ИИ-помощник", onBack = onBack) { padding ->
        Load(key = "ai-status", block = { container.api.aiStatus() }) { status, _ ->
            if (status.ai?.enabled != true) {
                Column(Modifier.padding(padding).padding(16.dp)) {
                    InfoBox("ИИ не настроен администратором. Раздел скрыт до настройки.")
                }
                return@Load
            }

            Column(
                Modifier
                    .fillMaxSize()
                    .padding(padding)
                    .padding(12.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (history.isEmpty()) {
                    InfoBox(
                        "Спросите о теме, правиле или способе решения. " +
                            "ИИ объяснит по-русски и не заменяет учителя."
                    )
                }

                LazyColumn(
                    modifier = Modifier
                        .fillMaxWidth()
                        .weight(1f),
                    contentPadding = PaddingValues(vertical = 4.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(history) { line ->
                        Card(
                            Modifier.fillMaxWidth(),
                            colors = androidx.compose.material3.CardDefaults.cardColors(
                                containerColor = if (line.fromUser) {
                                    MaterialTheme.colorScheme.primaryContainer
                                } else {
                                    MaterialTheme.colorScheme.surfaceVariant
                                }
                            ),
                        ) {
                            Column(Modifier.padding(12.dp)) {
                                Text(
                                    if (line.fromUser) "Вы" else "ИИ-помощник",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.SemiBold,
                                )
                                Text(line.text, style = MaterialTheme.typography.bodyMedium)
                            }
                        }
                    }
                }

                if (error != null) {
                    ErrorBox(error!!)
                }

                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    OutlinedTextField(
                        value = question,
                        onValueChange = { question = it },
                        label = { Text("Ваш вопрос") },
                        modifier = Modifier.weight(1f),
                        enabled = !busy,
                    )
                    Button(
                        onClick = {
                            val text = question.trim()
                            if (text.isNotEmpty() && !busy) {
                                busy = true
                                error = null
                                history += ChatLine(true, text)
                                question = ""
                                scope.launch {
                                    runCatching {
                                        apiCall { container.api.aiAsk(AiAskRequest(text, null)) }
                                    }
                                        .onSuccess {
                                            history += ChatLine(
                                                false,
                                                it.answer ?: "Пустой ответ",
                                            )
                                        }
                                        .onFailure { error = it.message }
                                    busy = false
                                }
                            }
                        },
                        enabled = !busy && question.isNotBlank(),
                    ) { Text(if (busy) "…" else "Спросить") }
                }
            }
        }
    }
}
