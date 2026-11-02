package com.edumath.uchus.ui.student

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
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
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.ShopDto
import com.edumath.uchus.data.api.ShopEquipRequest
import com.edumath.uchus.data.api.ShopGiftClaimRequest
import com.edumath.uchus.data.api.ShopGiftDto
import com.edumath.uchus.data.api.ShopItemDto
import com.edumath.uchus.data.api.ShopKeyRequest
import com.edumath.uchus.data.api.ShopPetDto
import com.edumath.uchus.data.api.ShopResponseDto
import com.edumath.uchus.data.api.ShopAvatarRequest
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.ui.common.ErrorBox
import com.edumath.uchus.ui.common.InfoBox
import com.edumath.uchus.ui.common.LoadingBox
import com.edumath.uchus.ui.common.ScreenScaffold
import com.edumath.uchus.ui.common.SectionTitle
import com.edumath.uchus.ui.pet.AnimatedPet
import com.edumath.uchus.ui.pet.PetProgressBar
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
    var petBusy by remember { mutableStateOf(false) }
    var party by remember { mutableStateOf<ShopItemDto?>(null) }
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

    fun perform(
        onSuccess: (ShopResponseDto) -> Unit = {},
        block: suspend () -> ShopResponseDto,
    ) {
        if (busy) return
        busy = true
        scope.launch {
            runCatching { apiCall { block() } }
                .onSuccess {
                    apply(it)
                    onSuccess(it)
                }
                .onFailure { message = it.message ?: "Не получилось. Попробуй ещё раз." }
            busy = false
        }
    }

    fun patPet() {
        if (petBusy) return
        petBusy = true
        scope.launch {
            runCatching { apiCall { container.api.petPat() } }
                .onSuccess { state ->
                    state.pet?.let { fresh -> shop = shop?.copy(pet = fresh) }
                    state.message?.let { message = it }
                    if (state.awarded > 0) {
                        runCatching { onRefreshSession() }
                    }
                }
                .onFailure { message = it.message ?: "Питомец не отвечает. Попробуй ещё раз." }
            petBusy = false
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
                    item { BalanceCard(data, petBusy, ::patPet) }

                    if (!message.isNullOrBlank()) {
                        item { InfoBox(message!!) }
                    }
                    if (error != null) {
                        item { ErrorBox(error!!) { tick++ } }
                    }

                    data.announcement?.takeIf { it.isNotBlank() }?.let {
                        item {
                            Surface(
                                color = MaterialTheme.colorScheme.tertiaryContainer,
                                shape = RoundedCornerShape(16.dp),
                                modifier = Modifier.fillMaxWidth(),
                            ) {
                                Text(
                                    "📣 $it",
                                    modifier = Modifier.padding(14.dp),
                                    fontWeight = FontWeight.SemiBold,
                                )
                            }
                        }
                    }

                    data.event?.let { event ->
                        item { EventCard(event.title, event.description, event.icon, event.effectText, event.daysLeft) }
                    }

                    if (data.gifts.isNotEmpty()) {
                        item {
                            SectionTitle("🎁 Тебе подарок!", "${data.gifts.size}")
                        }
                        items(data.gifts) { gift ->
                            GiftCard(gift, busy) {
                                perform { container.api.shopGiftClaim(ShopGiftClaimRequest(gift.id)) }
                            }
                        }
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
                                    onBuy = {
                                        perform(
                                            onSuccess = { if (featured.kind == "pet") party = featured },
                                        ) { container.api.shopBuy(ShopKeyRequest(featured.key)) }
                                    },
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
                                onBuy = {
                                    perform(
                                        onSuccess = { if (item.kind == "pet") party = item },
                                    ) { container.api.shopBuy(ShopKeyRequest(item.key)) }
                                },
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
            party?.let { bought ->
                PetPartyDialog(bought) { party = null }
            }
        }
    }
}

@Composable
private fun BalanceCard(
    shop: ShopDto,
    petBusy: Boolean,
    onPat: () -> Unit,
) {
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
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        AnimatedPet(
                            pet = pet,
                            size = 46.dp,
                            showBubble = false,
                            enabled = false,
                        )
                        Spacer(Modifier.width(8.dp))
                        Column(Modifier.weight(1f)) {
                            Row(
                                verticalAlignment = Alignment.CenterVertically,
                                horizontalArrangement = Arrangement.spacedBy(6.dp),
                            ) {
                                Text(
                                    "${pet.name ?: "Питомец"} · ${pet.stageName ?: "Малыш"}",
                                    style = MaterialTheme.typography.bodySmall,
                                    fontWeight = FontWeight.SemiBold,
                                )
                                if (pet.grew == true) {
                                    Text("🎉", fontSize = 14.sp)
                                }
                            }
                            PetProgressBar(pet.percent ?: 0)
                        }
                        Spacer(Modifier.width(8.dp))
                        Text(
                            if (pet.max == true) "макс." else "${pet.progress}/${pet.nextAt ?: 0}",
                            style = MaterialTheme.typography.labelSmall,
                        )
                    }
                    pet.tip?.takeIf { it.isNotBlank() }?.let { tip ->
                        Surface(
                            color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.8f),
                            shape = RoundedCornerShape(14.dp),
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(
                                "💬 $tip",
                                modifier = Modifier.padding(horizontal = 10.dp, vertical = 7.dp),
                                style = MaterialTheme.typography.labelSmall,
                            )
                        }
                    }
                    if (pet.canPat == true) {
                        Button(
                            onClick = onPat,
                            enabled = !petBusy,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            Text(
                                if (petBusy) "Обнимаемся…"
                                else "🤗 Погладить · +${pet.xpReward ?: 0} XP"
                            )
                        }
                    }
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
private fun EventCard(
    title: String?,
    description: String?,
    icon: String?,
    effect: String?,
    daysLeft: Int,
) {
    Surface(
        color = MaterialTheme.colorScheme.primaryContainer,
        shape = RoundedCornerShape(18.dp),
        modifier = Modifier.fillMaxWidth(),
    ) {
        Row(Modifier.padding(14.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(icon ?: "🎉", fontSize = 32.sp)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(title ?: "Живое событие", fontWeight = FontWeight.Bold)
                description?.takeIf { it.isNotBlank() }?.let {
                    Text(it, style = MaterialTheme.typography.bodySmall)
                }
                if (daysLeft > 0) {
                    Text(
                        "Ещё $daysLeft дн.",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            effect?.let {
                Surface(
                    color = MaterialTheme.colorScheme.secondaryContainer,
                    shape = RoundedCornerShape(999.dp),
                ) {
                    Text(
                        it,
                        modifier = Modifier.padding(horizontal = 10.dp, vertical = 5.dp),
                        fontWeight = FontWeight.Bold,
                        style = MaterialTheme.typography.labelMedium,
                    )
                }
            }
        }
    }
}

@Composable
private fun GiftCard(gift: ShopGiftDto, busy: Boolean, onOpen: () -> Unit) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(7.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                AnimatedEmoji(
                    icon = gift.icon ?: "🎁",
                    seedKey = "gift-${gift.id}",
                    fontSize = 40.sp,
                    lively = true,
                    glow = true,
                )
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(
                        "🎁 ${gift.name ?: "Подарок"}",
                        fontWeight = FontWeight.Bold,
                    )
                    Text(
                        gift.rarityName ?: "Особый подарок",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }
            gift.reason?.takeIf { it.isNotBlank() }?.let {
                Surface(
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    shape = RoundedCornerShape(12.dp),
                ) {
                    Text(
                        "«$it»",
                        modifier = Modifier.padding(10.dp),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
            gift.message?.takeIf { it.isNotBlank() }?.let {
                Text(it, style = MaterialTheme.typography.bodySmall)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                if (gift.coins > 0) PricePill("💰", gift.coins)
                if (gift.xp > 0) PricePill("⭐", gift.xp)
            }
            Button(onClick = onOpen, enabled = !busy, modifier = Modifier.fillMaxWidth()) {
                Text("Открыть подарок")
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
            AnimatedEmoji(
                icon = if (available) "🎁" else "📦",
                seedKey = "chest",
                fontSize = 38.sp,
                lively = available,
                glow = available,
            )
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
                AnimatedShopIcon(item)
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
                    item.rarityName?.let {
                        Text(
                            "${item.rarityIcon ?: ""} $it".trim(),
                            style = MaterialTheme.typography.labelSmall,
                            fontWeight = FontWeight.SemiBold,
                            color = MaterialTheme.colorScheme.tertiary,
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

/** Анимированная иконка товара: у питомцев — танец, у усилителей — пульс. */
@Composable
private fun AnimatedShopIcon(item: ShopItemDto) {
    val lively = item.kind == "pet" ||
        item.kind == "perk" ||
        item.kind?.startsWith("boost") == true
    val rare = item.rarity == "epic" || item.rarity == "legendary"
    AnimatedEmoji(
        icon = item.icon ?: "✨",
        seedKey = item.key,
        fontSize = if (item.kind == "pet") 34.sp else 32.sp,
        lively = lively,
        glow = rare || item.owned,
    )
}

@Composable
private fun AnimatedEmoji(
    icon: String,
    seedKey: String,
    fontSize: TextUnit,
    modifier: Modifier = Modifier,
    lively: Boolean = false,
    glow: Boolean = false,
) {
    val duration = remember(seedKey) {
        1700 + (seedKey.hashCode() and 0x7fffffff) % 900
    }
    val transition = rememberInfiniteTransition(label = "shop-$seedKey")
    val bob by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(duration, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "shop-bob",
    )
    val sway by transition.animateFloat(
        initialValue = -1f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(duration + 500, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "shop-sway",
    )
    Box(contentAlignment = Alignment.Center, modifier = modifier) {
        if (glow) {
            Box(
                Modifier
                    .size((fontSize.value * 1.55f).dp)
                    .alpha(0.10f + 0.09f * bob)
                    .background(
                        brush = Brush.radialGradient(
                            listOf(
                                MaterialTheme.colorScheme.tertiary.copy(alpha = 0.55f),
                                Color.Transparent,
                            )
                        ),
                        shape = CircleShape,
                    ),
            )
        }
        Text(
            text = icon,
            fontSize = fontSize,
            modifier = Modifier
                .offset(y = (-3f * bob).dp)
                .rotate(if (lively) 7f * sway else 2.5f * sway),
        )
    }
}

/** Полноэкранное празднование после покупки питомца. */
@Composable
private fun PetPartyDialog(item: ShopItemDto, onClose: () -> Unit) {
    val stage = item.stage
    val pet = remember(item.key) {
        ShopPetDto(
            key = item.key,
            icon = item.icon,
            name = item.name,
            index = stage?.index ?: 1,
            stageName = stage?.stageName ?: "Малыш",
            stageIcon = stage?.stageIcon ?: "🐣",
            progress = stage?.progress ?: 0,
            nextAt = stage?.nextAt,
            percent = stage?.percent ?: 0,
            max = stage?.max == true,
            tip = item.tagline,
            canPat = true,
            xpReward = 3,
        )
    }
    Dialog(
        onDismissRequest = onClose,
        properties = DialogProperties(usePlatformDefaultWidth = false),
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(Color(0xB3000000))
                .clickable(onClick = onClose)
                .padding(24.dp),
            contentAlignment = Alignment.Center,
        ) {
            Card(
                modifier = Modifier.fillMaxWidth(),
                shape = RoundedCornerShape(28.dp),
            ) {
                Column(
                    modifier = Modifier.padding(24.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    Text(
                        "🎉 Новый друг!",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                    )
                    AnimatedPet(
                        pet = pet,
                        size = 120.dp,
                        showBubble = false,
                        enabled = false,
                    )
                    Text(
                        item.name ?: "Питомец",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        "Теперь он живёт на главном экране: танцует, подсказывает, " +
                            "когда пора заниматься, и дарит опыт за обнимашки.",
                        style = MaterialTheme.typography.bodySmall,
                        textAlign = TextAlign.Center,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                    Button(onClick = onClose, modifier = Modifier.fillMaxWidth()) {
                        Text("Ура!")
                    }
                }
            }
        }
    }
}
