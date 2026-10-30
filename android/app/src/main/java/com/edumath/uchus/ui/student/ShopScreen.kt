package com.edumath.uchus.ui.student

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.ShopDto
import com.edumath.uchus.data.api.ShopEquipRequest
import com.edumath.uchus.data.api.ShopItemDto
import com.edumath.uchus.data.api.ShopKeyRequest
import com.edumath.uchus.data.api.ShopResponseDto
import com.edumath.uchus.data.api.ShopAvatarRequest
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.ErrorBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.LoadingBox
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import kotlinx.coroutines.launch

/**
 * Магазин: усилители, подсказки, стиль, темы и питомцы.
 *
 * Покупки тратят свободный опыт, но уровень не понижается. После каждого
 * действия обновляем снимок сессии, чтобы монеты и опыт сразу поменялись
 * на главной и в профиле.
 */
@Composable
fun ShopScreen(
    container: AppContainer,
    onBack: () -> Unit,
    onRefreshSession: suspend () -> Unit = {},
) {
    val scope = rememberCoroutineScope()
    var shop by remember { mutableStateOf<ShopDto?>(null) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    var message by remember { mutableStateOf<String?>(null) }
    var busy by remember { mutableStateOf(false) }
    var tick by remember { mutableIntStateOf(0) }

    LaunchedEffect(tick) {
        loading = true
        error = null
        runCatching { apiCall { container.api.shop() } }
            .onSuccess { shop = it; loading = false }
            .onFailure { error = it.message ?: "Не удалось открыть магазин"; loading = false }
    }

    fun apply(response: ShopResponseDto) {
        response.shop?.let { shop = it }
        response.message?.let { message = it }
        scope.launch {
            runCatching { onRefreshSession() }
        }
    }

    fun perform(block: suspend () -> ShopResponseDto) {
        if (busy) return
        busy = true
        scope.launch {
            runCatching { apiCall { block() } }
                .onSuccess { apply(it) }
                .onFailure { message = it.message ?: "Не получилось. Попробуй ещё раз." }
            busy = false
        }
    }

    ScreenScaffold(title = "🛍 Магазин", onBack = onBack) { padding ->
        Box(
            Modifier
                .fillMaxSize()
                .padding(padding),
        ) {
            val data = shop
            when {
                data == null && loading -> LoadingBox("Открываем магазин…")
                data == null -> ErrorBox(error ?: "Нет данных") { tick++ }
                else -> LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(horizontal = 14.dp),
                    contentPadding = PaddingValues(vertical = 14.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    item { BalanceCard(data) }

                    if (!message.isNullOrBlank()) {
                        item { InfoBox(message!!) }
                    }
                    if (error != null) {
                        item { ErrorBox(error!!) { tick++ } }
                    }

                    if (!data.effects.isNullOrEmpty()) {
                        item {
                            LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                items(data.effects) { effect ->
                                    Surface(
                                        color = MaterialTheme.colorScheme.tertiaryContainer,
                                        shape = RoundedCornerShape(999.dp),
                                    ) {
                                        Text(
                                            "${effect.icon ?: "✨"} ${effect.name ?: ""} · " +
                                                "${effect.remainingMinutes} мин",
                                            modifier = Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
                                            style = MaterialTheme.typography.labelMedium,
                                            fontWeight = FontWeight.Bold,
                                        )
                                    }
                                }
                            }
                        }
                    }

                    data.chest?.let { chest ->
                        item { ChestCard(chest.available, chest.minCoins, chest.maxCoins, busy) { perform { container.api.shopChest() } } }
                    }

                    data.featured?.let { featured ->
                        if ((featured.discount) > 0) {
                            item {
                                SectionTitle("🔥 Товар дня", "−${featured.discount}%")
                                ShopItemCard(
                                    item = featured,
                                    busy = busy,
                                    onBuy = { perform { container.api.shopBuy(ShopKeyRequest(featured.key)) } },
                                    onEquip = { perform { container.api.shopEquip(ShopEquipRequest(itemKey = featured.key)) } },
                                    onUnequip = { perform { container.api.shopEquip(ShopEquipRequest(slot = featured.slot)) } },
                                )
                            }
                        }
                    }

                    data.collection?.let { collection ->
                        item {
                            Card(Modifier.fillMaxWidth()) {
                                Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Text(
                                        "🏆 Коллекция: ${collection.owned} из ${collection.total}",
                                        fontWeight = FontWeight.SemiBold,
                                    )
                                    Bar(collection.percent)
                                    Text(
                                        "${collection.percent}% постоянных предметов уже твои",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                            }
                        }
                    }

                    data.categories.forEach { category ->
                        item { SectionTitle("${category.icon ?: ""} ${category.name ?: ""}") }
                        items(category.items) { item ->
                            ShopItemCard(
                                item = item,
                                busy = busy,
                                onBuy = { perform { container.api.shopBuy(ShopKeyRequest(item.key)) } },
                                onEquip = { perform { container.api.shopEquip(ShopEquipRequest(itemKey = item.key)) } },
                                onUnequip = { perform { container.api.shopEquip(ShopEquipRequest(slot = item.slot)) } },
                            )
                        }
                    }

                    if (data.avatars.isNotEmpty()) {
                        item {
                            SectionTitle("🙂 Мой аватар", "выбери")
                            Card(Modifier.fillMaxWidth()) {
                                Column(Modifier.padding(12.dp)) {
                                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                        items(data.avatars) { emoji ->
                                            OutlinedButton(
                                                onClick = {
                                                    perform {
                                                        container.api.shopAvatar(ShopAvatarRequest(emoji))
                                                    }
                                                },
                                                modifier = Modifier.size(52.dp),
                                                contentPadding = PaddingValues(0.dp),
                                            ) {
                                                Text(emoji, fontSize = 22.sp)
                                            }
                                        }
                                    }
                                    Spacer(Modifier.height(8.dp))
                                    Text(
                                        "Новые аватары открываются наборами из магазина.",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                    )
                                }
                            }
                        }
                    }

                    item {
                        InfoBox(
                            "Покупки тратят свободный опыт, но не понижают уровень: " +
                                "уровень считается по всему заработанному опыту.",
                        )
                    }
                    item { Spacer(Modifier.height(12.dp)) }
                }
            }
        }
    }
}

@Composable
private fun BalanceCard(shop: ShopDto) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("🛍", fontSize = 34.sp)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text("Магазин приключений", fontWeight = FontWeight.Bold)
                    Text(
                        "Уровень ${shop.level}" +
                            (shop.levelInfo?.title?.let { " · $it" } ?: ""),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                BigPill("💰", "${shop.balance?.coins ?: 0}", "монет")
                BigPill("⭐", "${shop.balance?.xp ?: 0}", "свободно")
            }
            Column(Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(
                    "Всего заработано: ${shop.totalXp} XP",
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Bar(shop.levelInfo?.percent ?: 0)
                shop.levelInfo?.let {
                    Text(
                        "До уровня ${shop.level + 1}: ${it.need} XP",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            val pet = shop.pet
            if (pet != null) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(pet.icon ?: "🐾", fontSize = 26.sp)
                    Spacer(Modifier.width(8.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            "${pet.name ?: "Питомец"} · ${pet.stageName ?: "Малыш"}",
                            style = MaterialTheme.typography.bodySmall,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Bar(pet.percent)
                    }
                    Spacer(Modifier.width(8.dp))
                    Text(
                        if (pet.max) "макс." else "${pet.progress}/${pet.nextAt ?: 0}",
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            }
        }
    }
}

@Composable
private fun RowScope.BigPill(icon: String, value: String, label: String) {
    Surface(
        color = MaterialTheme.colorScheme.secondaryContainer,
        shape = RoundedCornerShape(16.dp),
        modifier = Modifier.weight(1f),
    ) {
        Row(
            Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(icon, fontSize = 22.sp)
            Spacer(Modifier.width(8.dp))
            Column {
                Text(value, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                Text(label, style = MaterialTheme.typography.labelSmall)
            }
        }
    }
}

@Composable
private fun ChestCard(
    available: Boolean,
    minCoins: Int,
    maxCoins: Int,
    busy: Boolean,
    onOpen: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(if (available) "🎁" else "📦", fontSize = 38.sp)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                Text(
                    if (available) "Сундук дня готов!" else "Сундук уже открыт",
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    if (available) {
                        "Бесплатно: $minCoins–$maxCoins монет и немного опыта."
                    } else {
                        "Возвращайся завтра — сундук наполнится снова."
                    },
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            if (available) {
                Button(onClick = onOpen, enabled = !busy) { Text("Открыть") }
            }
        }
    }
}

@Composable
private fun ShopItemCard(
    item: ShopItemDto,
    busy: Boolean,
    onBuy: () -> Unit,
    onEquip: () -> Unit,
    onUnequip: () -> Unit,
) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(14.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.Top) {
                Text(item.icon ?: "✨", fontSize = 32.sp)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            item.name ?: "Предмет",
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.weight(1f),
                        )
                        if (item.discount > 0) {
                            Surface(
                                color = MaterialTheme.colorScheme.error,
                                shape = RoundedCornerShape(999.dp),
                            ) {
                                Text(
                                    "−${item.discount}%",
                                    modifier = Modifier.padding(horizontal = 7.dp, vertical = 2.dp),
                                    color = MaterialTheme.colorScheme.onError,
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.Bold,
                                )
                            }
                        }
                    }
                    item.tagline?.let {
                        Text(
                            it,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                }
            }

            item.description?.let {
                Text(it, style = MaterialTheme.typography.bodySmall)
            }

            item.stage?.let { stage ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(stage.stageIcon ?: "🐾", fontSize = 24.sp)
                    Spacer(Modifier.width(8.dp))
                    Column(Modifier.weight(1f)) {
                        Text(
                            "${stage.stageName ?: "Малыш"} · ${stage.progress}" +
                                if (stage.max) " (максимум)" else " / ${stage.nextAt ?: 0}",
                            style = MaterialTheme.typography.labelSmall,
                        )
                        Bar(stage.percent)
                    }
                }
            }

            if (item.avatars.isNotEmpty()) {
                Text(
                    item.avatars.joinToString("  "),
                    fontSize = 22.sp,
                )
            }

            if (item.owned && item.repeatable && item.quantity > 0) {
                Text(
                    "В копилке: ${item.quantity}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }

            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                PricePill("💰", item.priceCoins)
                PricePill("⭐", item.priceXp)
                Spacer(Modifier.weight(1f))
                if (item.canBuy) {
                    Button(onClick = onBuy, enabled = !busy) {
                        Text(if (item.owned) "Ещё" else "Купить")
                    }
                }
            }

            val slot = item.slot.orEmpty()
            if (item.owned && slot.isNotBlank()) {
                if (item.equipped) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(
                            "✅ Надето",
                            color = MaterialTheme.colorScheme.primary,
                            fontWeight = FontWeight.Bold,
                            style = MaterialTheme.typography.bodySmall,
                        )
                        OutlinedButton(onClick = onUnequip, enabled = !busy) {
                            Text("Снять")
                        }
                    }
                } else {
                    OutlinedButton(onClick = onEquip, enabled = !busy) {
                        Text("Надеть")
                    }
                }
            } else if (item.owned && !item.repeatable) {
                Text(
                    "✅ В коллекции",
                    color = MaterialTheme.colorScheme.primary,
                    fontWeight = FontWeight.Bold,
                    style = MaterialTheme.typography.bodySmall,
                )
            }

            if (!item.canBuy && !item.owned && !item.reason.isNullOrBlank()) {
                Text(
                    item.reason,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
    }
}

@Composable
private fun PricePill(icon: String, value: Int) {
    if (value <= 0) return
    Surface(
        color = MaterialTheme.colorScheme.surfaceVariant,
        shape = RoundedCornerShape(999.dp),
    ) {
        Text(
            "$icon $value",
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 4.dp),
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.Bold,
        )
    }
}

@Composable
private fun Bar(percent: Int) {
    Box(
        Modifier
            .fillMaxWidth()
            .height(7.dp)
            .clip(RoundedCornerShape(999.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Box(
            Modifier
                .fillMaxHeight()
                .fillMaxWidth((percent.coerceIn(0, 100)) / 100f)
                .clip(RoundedCornerShape(999.dp))
                .background(MaterialTheme.colorScheme.primary),
        )
    }
}
