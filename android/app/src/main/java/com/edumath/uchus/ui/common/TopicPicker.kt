package com.edumath.uchus.ui.common

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.material3.Card
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.Stable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.edumath.uchus.data.api.AdminTopicDto
import com.edumath.uchus.data.api.SubjectDto

/**
 * Состояние выбора тем: темы сгруппированы по предметам, предметы раскрываются.
 *
 * Используется вместе с [topicPicker], чтобы список оставался «ленивым»
 * и не создавал сотни строк одновременно.
 */
@Stable
class TopicPickerState internal constructor(
    internal val groups: List<SubjectGroup>,
    initialExpanded: Set<Int>,
) {
    var expandedIds by mutableStateOf(initialExpanded)
        private set

    val allExpanded: Boolean
        get() = groups.isNotEmpty() && expandedIds.size == groups.size

    fun toggle(subjectId: Int) {
        expandedIds = if (subjectId in expandedIds) {
            expandedIds - subjectId
        } else {
            expandedIds + subjectId
        }
    }

    fun expandAll() {
        expandedIds = groups.map { it.id }.toSet()
    }

    fun collapseAll() {
        expandedIds = emptySet()
    }
}

/**
 * Создаёт состояние выбора тем. При смене класса или ребёнка состояние
 * сбрасывается: все предметы свёрнуты, виден только их список.
 */
@Composable
fun rememberTopicPickerState(
    topics: List<AdminTopicDto>,
    subjects: List<SubjectDto>,
): TopicPickerState {
    val groups = remember(topics, subjects) { groupTopics(topics, subjects) }
    return remember(groups) {
        TopicPickerState(groups = groups, initialExpanded = emptySet())
    }
}

/**
 * Добавляет в LazyColumn список предметов с раскрывающимися темами.
 *
 * Каждый предмет — отдельный элемент списка, поэтому свёрнутые предметы
 * не создают строк с темами и экран не тормозит даже на больших каталогах.
 */
fun LazyListScope.topicPicker(
    state: TopicPickerState,
    selected: Set<String>,
    onToggle: (String) -> Unit,
) {
    val groups = state.groups
    if (groups.isEmpty()) {
        item(key = "topic-picker-empty") { InfoBox("Для этого класса нет доступных тем.") }
        return
    }

    if (groups.size > 1) {
        item(key = "topic-picker-header") {
            Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                Text(
                    "Предметы",
                    style = MaterialTheme.typography.labelLarge,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Spacer(Modifier.weight(1f))
                TextButton(
                    onClick = {
                        if (state.allExpanded) state.collapseAll() else state.expandAll()
                    },
                ) {
                    Text(if (state.allExpanded) "Свернуть всё" else "Развернуть всё")
                }
            }
        }
    }

    groups.forEach { group ->
        item(key = "subject-${group.id}") {
            SubjectCard(
                group = group,
                expanded = group.id in state.expandedIds,
                selected = selected,
                onToggleExpanded = { state.toggle(group.id) },
                onToggleTopic = onToggle,
            )
        }
    }
}

@Composable
private fun SubjectCard(
    group: SubjectGroup,
    expanded: Boolean,
    selected: Set<String>,
    onToggleExpanded: () -> Unit,
    onToggleTopic: (String) -> Unit,
) {
    val chosen = group.topics.count { it.slug in selected }
    val allSelected = chosen == group.topics.size

    Card(Modifier.fillMaxWidth()) {
        Column {
            Row(
                Modifier
                    .fillMaxWidth()
                    .clickable(onClick = onToggleExpanded)
                    .padding(horizontal = 14.dp, vertical = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(group.icon.ifBlank { "📘" }, fontSize = 22.sp)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(group.name, fontWeight = FontWeight.SemiBold)
                    Text(
                        buildString {
                            append("${group.topics.size} ${topicsWord(group.topics.size)}")
                            if (chosen > 0) append(" · выбрано $chosen")
                        },
                        style = MaterialTheme.typography.labelSmall,
                        color = if (chosen > 0) {
                            MaterialTheme.colorScheme.primary
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                    )
                }
                if (chosen > 0) {
                    Tag("$chosen")
                    Spacer(Modifier.width(8.dp))
                }
                Text(
                    if (expanded) "▾" else "▸",
                    fontSize = 18.sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            if (expanded) {
                HorizontalDivider()
                Row(
                    Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    TextButton(
                        onClick = {
                            group.topics.forEach { topic ->
                                val isSelected = topic.slug in selected
                                if (allSelected && isSelected) {
                                    onToggleTopic(topic.slug)
                                } else if (!allSelected && !isSelected) {
                                    onToggleTopic(topic.slug)
                                }
                            }
                        },
                    ) {
                        Text(if (allSelected) "Снять все" else "Выбрать все")
                    }
                    Spacer(Modifier.weight(1f))
                    Text(
                        "$chosen из ${group.topics.size}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(end = 14.dp),
                    )
                }

                group.topics.forEachIndexed { index, topic ->
                    TopicRow(
                        topic = topic,
                        checked = topic.slug in selected,
                        onClick = { onToggleTopic(topic.slug) },
                    )
                    if (index != group.topics.lastIndex) {
                        HorizontalDivider(Modifier.padding(start = 46.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun TopicRow(
    topic: AdminTopicDto,
    checked: Boolean,
    onClick: () -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 14.dp, vertical = 10.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(if (checked) "✅" else "⬜️", fontSize = 18.sp)
        Spacer(Modifier.width(10.dp))
        Column(Modifier.weight(1f)) {
            Text(
                (topic.icon?.takeIf { it.isNotBlank() }?.plus(" ") ?: "") +
                    (topic.title ?: topic.slug),
                fontWeight = if (checked) FontWeight.SemiBold else FontWeight.Normal,
            )
            val hint = topic.part?.takeIf { it.isNotBlank() }
            if (hint != null) {
                Text(
                    hint,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

internal data class SubjectGroup(
    val id: Int,
    val name: String,
    val icon: String,
    val topics: List<AdminTopicDto>,
)

private fun groupTopics(
    topics: List<AdminTopicDto>,
    subjects: List<SubjectDto>,
): List<SubjectGroup> {
    if (topics.isEmpty()) return emptyList()
    val subjectById = subjects.associateBy { it.id }
    val order = subjects.mapIndexed { index, subject -> subject.id to index }.toMap()
    return topics
        .groupBy { it.subjectId }
        .map { (subjectId, items) ->
            val subject = subjectById[subjectId]
            SubjectGroup(
                id = subjectId,
                name = subject?.name ?: items.firstOrNull()?.subjectName ?: "Другие темы",
                icon = subject?.icon ?: items.firstOrNull()?.icon ?: "📘",
                topics = items,
            )
        }
        .sortedWith(compareBy({ order[it.id] ?: Int.MAX_VALUE }, { it.name }))
}

private fun topicsWord(count: Int): String {
    val mod10 = count % 10
    val mod100 = count % 100
    return when {
        mod10 == 1 && mod100 != 11 -> "тема"
        mod10 in 2..4 && mod100 !in 12..14 -> "темы"
        else -> "тем"
    }
}
