package com.edumath.uchus.ui.notifications

import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.NotificationDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.EmptyBox
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.ScreenScaffold
import kotlinx.coroutines.launch

/** Уведомления: новые задания, выполненные и пропущенные работы. */
@Composable
fun NotificationsScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onOpenAssignment: (Int) -> Unit = {},
) {
    var tick by remember { mutableIntStateOf(0) }
    val scope = rememberCoroutineScope()

    ScreenScaffold(
        title = "Уведомления",
        onBack = onBack,
        actions = {
            OutlinedButton(
                onClick = {
                    scope.launch {
                        runCatching { apiCall { container.api.notificationsReadAll() } }
                        tick++
                    }
                },
            ) { Text("Прочитать все") }
        },
    ) { padding ->
        Load(key = "notifications:$tick", block = { container.api.notifications() }) { data, reload ->
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(padding),
                contentPadding = PaddingValues(16.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp),
            ) {
                if (data.notifications.isEmpty()) {
                    item { EmptyBox("Пока нет уведомлений.", "🔔") }
                }
                items(data.notifications) { item ->
                    NotificationCard(
                        item = item,
                        onClick = {
                            if (!item.isRead) {
                                scope.launch {
                                    runCatching {
                                        apiCall { container.api.notificationRead(item.id) }
                                    }
                                }
                            }
                            if (item.assignmentId > 0) onOpenAssignment(item.assignmentId)
                        },
                    )
                }
                item { Spacer(Modifier.height(16.dp)) }
            }
        }
    }
}

@Composable
private fun NotificationCard(item: NotificationDto, onClick: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick),
    ) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    (if (item.isRead) "" else "● ") + (item.title ?: "Уведомление"),
                    fontWeight = if (item.isRead) FontWeight.Normal else FontWeight.Bold,
                    modifier = Modifier.weight(1f),
                )
                Text(
                    kindEmoji(item.kind),
                    style = MaterialTheme.typography.titleMedium,
                )
            }
            Text(
                item.body ?: "",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            if (!item.createdAt.isNullOrBlank()) {
                Text(
                    item.createdAt ?: "",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

private fun kindEmoji(kind: String?): String = when (kind) {
    "assignment_new" -> "📝"
    "assignment_done" -> "✅"
    "assignment_missed" -> "⚠️"
    else -> "🔔"
}
