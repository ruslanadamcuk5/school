package com.edumath.uchus.ui.admin

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.Checkbox
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.AdminShopAnnouncementRequest
import com.edumath.uchus.data.api.AdminShopEventDto
import com.edumath.uchus.data.api.AdminShopEventRequest
import com.edumath.uchus.data.api.AdminShopFeaturedRequest
import com.edumath.uchus.data.api.AdminShopGiftDto
import com.edumath.uchus.data.api.AdminShopGiftRequest
import com.edumath.uchus.data.api.AdminShopItemDto
import com.edumath.uchus.data.api.AdminShopItemRequest
import com.edumath.uchus.data.api.AdminShopLeaderDto
import com.edumath.uchus.data.api.AdminShopReasonDto
import com.edumath.uchus.data.api.AdminShopResponseDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.EmptyBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.KeyValue
import com.edumath.uchus.ui.common.Load
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.common.StatsRow
import com.edumath.uchus.ui.common.Tag
import kotlinx.coroutines.launch
import kotlin.math.roundToInt

/**
 * Админка магазина: рейтинг стараний, подарки, каталог, витрина и события.
 * Повторяет веб-страницу `/admin/shop`, но целиком на JSON API.
 */
@Composable
internal fun AdminShopTab(container: AppContainer) {
    val scope = rememberCoroutineScope()
    var tick by remember { mutableIntStateOf(0) }
    var message by remember { mutableStateOf<String?>(null) }
    var selectedId by remember { mutableStateOf<Int?>(null) }
    var giftTarget by remember { mutableStateOf<GiftTarget?>(null) }
    var editItem by remember { mutableStateOf<AdminShopItemDto?>(null) }
    var showFeatured by remember { mutableStateOf(false) }
    var showEvent by remember { mutableStateOf(false) }

    fun runAction(block: suspend () -> AdminShopResponseDto) {
        scope.launch {
            runCatching { apiCall { block() } }
                .onSuccess {
                    message = it.message ?: "Готово"
                    tick++
                }
                .onFailure { message = it.message ?: "Не удалось выполнить действие" }
        }
    }

    Load(key = "admin-shop:$tick", block = { container.api.adminShop() }) { data, _ ->
        val selected = data.board.firstOrNull { it.id == selectedId }
            ?: data.board.firstOrNull()

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            if (message != null) {
                item { InfoBox(message!!) }
            }

            item {
                StatsRow(
                    "ждут" to "${data.summary.pending}",
                    "открыто" to "${data.summary.claimed}",
                    "сегодня" to "${data.summary.today}",
                )
            }
            item {
                StatsRow(
                    "покупок" to "${data.summary.purchasesToday}",
                    "монет" to "${data.summary.coinsSpent}",
                )
            }

            item { SectionTitle("🔥 Кто старается", "за 7 дней") }
            if (data.board.isEmpty()) {
                item { EmptyBox("Пока нет профилей детей.", "👶") }
            }
            items(data.board.take(30)) { leader ->
                LeaderCard(
                    leader = leader,
                    selected = leader.id == selected?.id,
                    onSelect = { selectedId = leader.id },
                    onGift = {
                        selectedId = leader.id
                        giftTarget = GiftTarget(leader, null)
                    },
                )
            }

            if (selected != null) {
                item {
                    SelectedLearnerCard(
                        leader = selected,
                        onGift = { giftTarget = GiftTarget(selected, null) },
                        onIdea = { key -> giftTarget = GiftTarget(selected, key) },
                    )
                }
            }

            item { SectionTitle("🏷 Витрина") }
            item {
                FeaturedCard(
                    data = data.featuredKey ?: "",
                    catalog = data.catalog,
                    onPick = { showFeatured = true },
                )
            }
            item {
                AnnouncementCard(
                    initial = data.announcement ?: "",
                    onSave = { text ->
                        runAction { container.api.adminShopSetAnnouncement(AdminShopAnnouncementRequest(text)) }
                    },
                )
            }

            item { SectionTitle("🎉 События", "${data.events.size}") }
            item {
                OutlinedButton(
                    onClick = { showEvent = true },
                    modifier = Modifier.fillMaxWidth(),
                ) { Text("Запустить событие") }
            }
            items(data.events) { event ->
                EventCard(
                    event = event,
                    onStop = { runAction { container.api.adminShopStopEvent(event.id) } },
                )
            }

            item { SectionTitle("🧱 Каталог", "${data.catalog.size}") }
            data.categories.forEach { category ->
                item { SectionTitle("${category.icon ?: ""} ${category.name ?: category.key}") }
                items(data.catalog.filter { it.category == category.key }) { item ->
                    CatalogItemCard(item = item, onEdit = { editItem = item })
                }
            }

            item { SectionTitle("📜 История подарков", "${data.gifts.size}") }
            if (data.gifts.isEmpty()) {
                item { EmptyBox("Подарков пока нет.", "🎁") }
            }
            items(data.gifts) { gift ->
                GiftHistoryCard(
                    gift = gift,
                    onCancel = { runAction { container.api.adminShopCancelGift(gift.id) } },
                )
            }

            item { Spacer(Modifier.height(24.dp)) }
        }

        val target = giftTarget
        if (target != null) {
            GiftDialog(
                target = target,
                catalog = data.catalog,
                reasons = data.reasons,
                onDismiss = { giftTarget = null },
                onSend = { request ->
                    giftTarget = null
                    runAction { container.api.adminShopCreateGift(request) }
                },
            )
        }

        val editing = editItem
        if (editing != null) {
            ItemEditDialog(
                item = editing,
                onDismiss = { editItem = null },
                onSave = { request ->
                    editItem = null
                    runAction { container.api.adminShopSaveItem(editing.key, request) }
                },
                onReset = {
                    editItem = null
                    runAction { container.api.adminShopResetItem(editing.key) }
                },
            )
        }

        if (showFeatured) {
            FeaturedDialog(
                catalog = data.catalog,
                current = data.featuredKey ?: "",
                onDismiss = { showFeatured = false },
                onPick = { key ->
                    showFeatured = false
                    runAction { container.api.adminShopSetFeatured(AdminShopFeaturedRequest(key)) }
                },
            )
        }

        if (showEvent) {
            EventDialog(
                today = data.today ?: "",
                defaultEnd = data.defaultEnd ?: "",
                onDismiss = { showEvent = false },
                onCreate = { request ->
                    showEvent = false
                    runAction { container.api.adminShopCreateEvent(request) }
                },
            )
        }
    }
}

private data class GiftTarget(
    val learner: AdminShopLeaderDto,
    val itemKey: String?,
)

@Composable
private fun LeaderCard(
    leader: AdminShopLeaderDto,
    selected: Boolean,
    onSelect: () -> Unit,
    onGift: () -> Unit,
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onSelect),
    ) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("#${leader.rank}", fontWeight = FontWeight.Bold, fontSize = 16.sp)
                Spacer(Modifier.width(8.dp))
                Text(leader.avatar ?: "👤", fontSize = 24.sp)
                Spacer(Modifier.width(8.dp))
                Column(Modifier.weight(1f)) {
                    Text(leader.name ?: "Ребёнок", fontWeight = FontWeight.SemiBold)
                    Text(
                        "${leader.grade} класс · ур. ${leader.level}" +
                            (leader.accountLogin?.takeIf { it.isNotBlank() }?.let { " · $it" } ?: ""),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Column(horizontalAlignment = Alignment.End) {
                    Text("${leader.score.roundToInt()}", fontWeight = FontWeight.Bold)
                    Text(
                        "старание",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            Spacer(Modifier.height(6.dp))
            Text(
                "${leader.daysActive}/7 дней · ${leader.attempts} заданий · " +
                    "точность ${leader.accuracy}% · 🔥 ${leader.streakDays}",
                style = MaterialTheme.typography.bodySmall,
            )
            leader.reasons.take(2).forEach { reason ->
                Text(
                    "${reason.icon ?: ""} ${reason.text}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                if (selected) Tag("выбран")
                if (leader.deserving) Tag("✨ заслуживает подарок")
                if (leader.pendingGifts > 0) Tag("🎁 ждёт: ${leader.pendingGifts}")
                Spacer(Modifier.weight(1f))
                TextButton(onClick = onGift) { Text("Подарить") }
            }
        }
    }
}

@Composable
private fun SelectedLearnerCard(
    leader: AdminShopLeaderDto,
    onGift: () -> Unit,
    onIdea: (String) -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(leader.avatar ?: "👤", fontSize = 28.sp)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        "Подарок для ${leader.name ?: "ребёнка"}",
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        "${leader.grade} класс · ${leader.attempts} заданий за неделю · " +
                            "точность ${leader.accuracy}%" +
                            (
                                leader.daysSinceGift?.let { " · последний подарок $it дн. назад" }
                                    ?: " · подарков ещё не было"
                                ),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            if (leader.reasons.isNotEmpty()) {
                LazyRow(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    contentPadding = PaddingValues(top = 8.dp),
                ) {
                    items(leader.reasons) { reason ->
                        FilterChip(
                            selected = false,
                            onClick = { onGift() },
                            label = { Text("${reason.icon ?: ""} ${reason.text}") },
                        )
                    }
                }
            }

            if (leader.ideas.isNotEmpty()) {
                Text(
                    "Идеи подарков — чего ещё нет:",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.padding(top = 8.dp),
                )
                LazyRow(
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                    contentPadding = PaddingValues(top = 4.dp),
                ) {
                    items(leader.ideas) { idea ->
                        OutlinedButton(onClick = { onIdea(idea.key) }) {
                            Text("${idea.icon ?: "🎁"} ${idea.name ?: idea.key}")
                        }
                    }
                }
            }

            Button(
                onClick = onGift,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 10.dp),
            ) { Text("🎁 Отправить подарок") }
        }
    }
}

@Composable
private fun FeaturedCard(
    data: String,
    catalog: List<AdminShopItemDto>,
    onPick: () -> Unit,
) {
    val item = catalog.firstOrNull { it.key == data }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Text("Товар дня", fontWeight = FontWeight.SemiBold)
            Text(
                if (item != null) {
                    "${item.icon ?: ""} ${item.name ?: item.key} · скидка 25%"
                } else {
                    "Автоматически — витрина выбирает сама"
                },
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            OutlinedButton(
                onClick = onPick,
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
            ) { Text("Выбрать товар дня") }
        }
    }
}

@Composable
private fun AnnouncementCard(initial: String, onSave: (String) -> Unit) {
    var text by remember(initial) { mutableStateOf(initial) }
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp)) {
            Text("Объявление для детей", fontWeight = FontWeight.SemiBold)
            OutlinedTextField(
                value = text,
                onValueChange = { text = it.take(300) },
                label = { Text("Например: на выходных двойные монеты!") },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
            )
            Button(
                onClick = { onSave(text.trim()) },
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 8.dp),
            ) { Text("Сохранить объявление") }
        }
    }
}

@Composable
private fun EventCard(event: AdminShopEventDto, onStop: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(event.icon ?: "🎉", fontSize = 24.sp)
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(event.title ?: "Событие", fontWeight = FontWeight.Medium)
                Text(
                    "${event.startsOn ?: ""} — ${event.endsOn ?: ""} · ${eventEffect(event)}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (event.isActive) {
                TextButton(onClick = onStop) { Text("Остановить") }
            } else {
                Tag("завершено")
            }
        }
    }
}

private fun eventEffect(event: AdminShopEventDto): String = when (event.kind) {
    "double_xp" -> "⭐ ×${formatValue(event.value)}"
    "discount" -> "🏷 −${event.value.roundToInt()}%"
    else -> "🪙 ×${formatValue(event.value)}"
}

private fun formatValue(value: Double): String =
    if (value == value.roundToInt().toDouble()) "${value.roundToInt()}" else "$value"

@Composable
private fun CatalogItemCard(item: AdminShopItemDto, onEdit: () -> Unit) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onEdit),
    ) {
        Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(item.icon ?: "🎁", fontSize = 24.sp)
            Spacer(Modifier.width(10.dp))
            Column(Modifier.weight(1f)) {
                Text(item.name ?: item.key, fontWeight = FontWeight.Medium)
                Text(
                    "${item.rarityName ?: ""} · ур. ${item.level} · 💰 ${item.coins}" +
                        (if (item.xp > 0) " + ⭐ ${item.xp}" else ""),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Tag(if (item.isActive) "в продаже" else "выключен")
        }
    }
}

@Composable
private fun GiftHistoryCard(gift: AdminShopGiftDto, onCancel: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(gift.learnerAvatar ?: "🎁", fontSize = 22.sp)
                Spacer(Modifier.width(8.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        "${gift.icon ?: ""} ${gift.name ?: "Особый подарок"}",
                        fontWeight = FontWeight.Medium,
                    )
                    Text(
                        "${gift.learnerName ?: "—"} · ${gift.learnerGrade} кл. · ${gift.createdAt ?: ""}",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                Tag(
                    when (gift.status) {
                        "pending" -> "ждёт"
                        "claimed" -> "открыт"
                        else -> "отменён"
                    }
                )
            }
            if (!gift.reason.isNullOrBlank()) {
                Text(
                    "За что: ${gift.reason}",
                    style = MaterialTheme.typography.bodySmall,
                    modifier = Modifier.padding(top = 6.dp),
                )
            }
            if (!gift.message.isNullOrBlank()) {
                Text(
                    gift.message ?: "",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Row(
                modifier = Modifier.padding(top = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                if (gift.coins > 0) Tag("💰 ${gift.coins}")
                if (gift.xp > 0) Tag("⭐ ${gift.xp}")
                if (gift.status == "pending") {
                    Spacer(Modifier.weight(1f))
                    TextButton(onClick = onCancel) { Text("Отменить") }
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun GiftDialog(
    target: GiftTarget,
    catalog: List<AdminShopItemDto>,
    reasons: List<AdminShopReasonDto>,
    onDismiss: () -> Unit,
    onSend: (AdminShopGiftRequest) -> Unit,
) {
    var itemKey by remember(target) { mutableStateOf(target.itemKey ?: "") }
    var coins by remember(target) { mutableStateOf("0") }
    var xp by remember(target) { mutableStateOf("0") }
    var reason by remember(target) { mutableStateOf(target.learner.reasonText ?: "") }
    var message by remember(target) { mutableStateOf("") }
    var itemsOpen by remember { mutableStateOf(false) }

    val selectedItem = catalog.firstOrNull { it.key == itemKey }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Подарок для ${target.learner.name ?: "ребёнка"}") },
        text = {
            Column(
                modifier = Modifier.heightIn(max = 460.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                BoxWithMenu(
                    label = if (selectedItem != null) {
                        "${selectedItem.icon ?: ""} ${selectedItem.name ?: selectedItem.key}"
                    } else {
                        "— только монеты/опыт —"
                    },
                    expanded = itemsOpen,
                    onToggle = { itemsOpen = !itemsOpen },
                ) {
                    DropdownMenuItem(
                        text = { Text("— только монеты/опыт —") },
                        onClick = {
                            itemKey = ""
                            itemsOpen = false
                        },
                    )
                    catalog.forEach { item ->
                        DropdownMenuItem(
                            text = { Text("${item.icon ?: ""} ${item.name ?: item.key} · ур. ${item.level}") },
                            onClick = {
                                itemKey = item.key
                                itemsOpen = false
                            },
                        )
                    }
                }

                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = coins,
                        onValueChange = { coins = it.filter { ch -> ch.isDigit() }.take(5) },
                        label = { Text("Монет") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = xp,
                        onValueChange = { xp = it.filter { ch -> ch.isDigit() }.take(5) },
                        label = { Text("Опыта") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                }

                OutlinedTextField(
                    value = reason,
                    onValueChange = { reason = it.take(500) },
                    label = { Text("За что подарок (увидит ребёнок)") },
                    modifier = Modifier.fillMaxWidth(),
                )
                if (reasons.isNotEmpty()) {
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        items(reasons) { value ->
                            FilterChip(
                                selected = false,
                                onClick = { reason = value.text },
                                label = { Text("${value.icon ?: ""} ${value.text}") },
                            )
                        }
                    }
                }
                OutlinedTextField(
                    value = message,
                    onValueChange = { message = it.take(500) },
                    label = { Text("Личное сообщение (необязательно)") },
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(
                enabled = reason.isNotBlank(),
                onClick = {
                    onSend(
                        AdminShopGiftRequest(
                            learnerId = target.learner.id,
                            itemKey = itemKey.ifBlank { null },
                            reason = reason.trim(),
                            message = message.trim().ifBlank { null },
                            coins = coins.toIntOrNull() ?: 0,
                            xp = xp.toIntOrNull() ?: 0,
                        )
                    )
                },
            ) { Text("Отправить") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Отмена") } },
    )
}

@Composable
private fun BoxWithMenu(
    label: String,
    expanded: Boolean,
    onToggle: () -> Unit,
    menu: @Composable () -> Unit,
) {
    Column {
        OutlinedButton(onClick = onToggle, modifier = Modifier.fillMaxWidth()) {
            Text(label)
        }
        DropdownMenu(expanded = expanded, onDismissRequest = onToggle) {
            menu()
        }
    }
}

@Composable
private fun ItemEditDialog(
    item: AdminShopItemDto,
    onDismiss: () -> Unit,
    onSave: (AdminShopItemRequest) -> Unit,
    onReset: () -> Unit,
) {
    val override = item.override
    var name by remember(item.key) { mutableStateOf(override?.name ?: "") }
    var icon by remember(item.key) { mutableStateOf(override?.icon ?: "") }
    var tagline by remember(item.key) { mutableStateOf(override?.tagline ?: "") }
    var description by remember(item.key) { mutableStateOf(override?.description ?: "") }
    var priceCoins by remember(item.key) {
        mutableStateOf(override?.priceCoins?.toString() ?: "")
    }
    var priceXp by remember(item.key) {
        mutableStateOf(override?.priceXp?.toString() ?: "")
    }
    var discount by remember(item.key) {
        mutableStateOf(override?.discountPercent?.toString() ?: "")
    }
    var level by remember(item.key) {
        mutableStateOf((override?.level ?: item.level).toString())
    }
    var isActive by remember(item.key) { mutableStateOf(item.isActive) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("${item.icon ?: ""} ${item.name ?: item.key}") },
        text = {
            Column(
                modifier = Modifier.heightIn(max = 500.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it.take(80) },
                    label = { Text("Название") },
                    placeholder = { Text(item.name ?: "") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = icon,
                        onValueChange = { icon = it.take(8) },
                        label = { Text("Иконка") },
                        placeholder = { Text(item.icon ?: "") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = level,
                        onValueChange = { level = it.filter { ch -> ch.isDigit() }.take(2) },
                        label = { Text("Уровень") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                }
                OutlinedTextField(
                    value = tagline,
                    onValueChange = { tagline = it.take(120) },
                    label = { Text("Короткая подпись") },
                    placeholder = { Text(item.tagline ?: "") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it.take(500) },
                    label = { Text("Описание") },
                    placeholder = { Text(item.description ?: "") },
                    modifier = Modifier.fillMaxWidth(),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = priceCoins,
                        onValueChange = { priceCoins = it.filter { ch -> ch.isDigit() }.take(6) },
                        label = { Text("Цена, монеты") },
                        placeholder = { Text("${item.coins}") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = priceXp,
                        onValueChange = { priceXp = it.filter { ch -> ch.isDigit() }.take(6) },
                        label = { Text("Цена, опыт") },
                        placeholder = { Text("${item.xp}") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = discount,
                        onValueChange = { discount = it.filter { ch -> ch.isDigit() }.take(2) },
                        label = { Text("Скидка, %") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    Text(
                        if (override == null) "Значения из каталога кода" else "Есть ручные настройки",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier
                            .weight(1f)
                            .padding(top = 20.dp),
                    )
                }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Checkbox(
                        checked = isActive,
                        onCheckedChange = { isActive = it },
                    )
                    Text("Показывать в магазине")
                }
            }
        },
        confirmButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                if (override != null) {
                    TextButton(onClick = onReset) { Text("Сбросить") }
                }
                TextButton(
                    onClick = {
                        onSave(
                            AdminShopItemRequest(
                                name = name.trim().ifBlank { null },
                                icon = icon.trim().ifBlank { null },
                                tagline = tagline.trim().ifBlank { null },
                                description = description.trim().ifBlank { null },
                                priceCoins = priceCoins.toIntOrNull(),
                                priceXp = priceXp.toIntOrNull(),
                                discountPercent = discount.toIntOrNull(),
                                level = level.toIntOrNull(),
                                isActive = isActive,
                            )
                        )
                    },
                ) { Text("Сохранить") }
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Отмена") } },
    )
}

@Composable
private fun FeaturedDialog(
    catalog: List<AdminShopItemDto>,
    current: String,
    onDismiss: () -> Unit,
    onPick: (String?) -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Товар дня") },
        text = {
            LazyColumn(Modifier.heightIn(max = 420.dp)) {
                item {
                    TextButton(onClick = { onPick(null) }) {
                        Text(if (current.isBlank()) "✓ Автоматически" else "Автоматически")
                    }
                }
                items(catalog) { item ->
                    TextButton(
                        onClick = { onPick(item.key) },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(
                            (if (item.key == current) "✓ " else "") +
                                "${item.icon ?: ""} ${item.name ?: item.key}",
                            modifier = Modifier.fillMaxWidth(),
                        )
                    }
                }
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text("Закрыть") } },
    )
}

@Composable
private fun EventDialog(
    today: String,
    defaultEnd: String,
    onDismiss: () -> Unit,
    onCreate: (AdminShopEventRequest) -> Unit,
) {
    var title by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var icon by remember { mutableStateOf("🎉") }
    var kind by remember { mutableStateOf("double_coins") }
    var value by remember { mutableStateOf("2") }
    var startsOn by remember { mutableStateOf(today) }
    var endsOn by remember { mutableStateOf(defaultEnd) }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Новое событие") },
        text = {
            Column(
                modifier = Modifier.heightIn(max = 460.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = title,
                        onValueChange = { title = it.take(120) },
                        label = { Text("Название") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = icon,
                        onValueChange = { icon = it.take(8) },
                        label = { Text("Иконка") },
                        singleLine = true,
                        modifier = Modifier.width(90.dp),
                    )
                }
                OutlinedTextField(
                    value = description,
                    onValueChange = { description = it.take(500) },
                    label = { Text("Описание") },
                    modifier = Modifier.fillMaxWidth(),
                )
                Text("Бонус", style = MaterialTheme.typography.labelLarge)
                LazyRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    items(
                        listOf(
                            "double_coins" to "🪙 Монеты",
                            "double_xp" to "⭐ Опыт",
                            "discount" to "🏷 Скидка",
                        )
                    ) { (key, label) ->
                        FilterChip(
                            selected = kind == key,
                            onClick = {
                                kind = key
                                value = if (key == "discount") "25" else "2"
                            },
                            label = { Text(label) },
                        )
                    }
                }
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedTextField(
                        value = value,
                        onValueChange = { value = it.filter { ch -> ch.isDigit() || ch == '.' }.take(5) },
                        label = { Text(if (kind == "discount") "Скидка, %" else "Множитель") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                    OutlinedTextField(
                        value = startsOn,
                        onValueChange = { startsOn = it.take(10) },
                        label = { Text("Начало") },
                        singleLine = true,
                        modifier = Modifier.weight(1f),
                    )
                }
                OutlinedTextField(
                    value = endsOn,
                    onValueChange = { endsOn = it.take(10) },
                    label = { Text("Окончание") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        },
        confirmButton = {
            TextButton(
                enabled = title.isNotBlank(),
                onClick = {
                    onCreate(
                        AdminShopEventRequest(
                            title = title.trim(),
                            description = description.trim().ifBlank { null },
                            icon = icon.trim().ifBlank { "🎉" },
                            kind = kind,
                            value = value.toDoubleOrNull() ?: 2.0,
                            startsOn = startsOn.trim().ifBlank { today },
                            endsOn = endsOn.trim().ifBlank { startsOn.trim() },
                        )
                    )
                },
            ) { Text("Запустить") }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text("Отмена") } },
    )
}
