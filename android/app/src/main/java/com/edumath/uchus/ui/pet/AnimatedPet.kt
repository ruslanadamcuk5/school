package com.edumath.uchus.ui.pet

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.spring
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.rotate
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.edumath.uchus.data.api.ShopPetDto
import kotlinx.coroutines.delay
import kotlin.math.sin

@Composable
fun AnimatedPet(
    pet: ShopPetDto?,
    modifier: Modifier = Modifier,
    size: Dp = 72.dp,
    showBubble: Boolean = true,
    enabled: Boolean = true,
    onClick: () -> Unit = {},
) {
    if (pet == null) return
    val transition = rememberInfiniteTransition(label = "pet-idle")
    val bounce by transition.animateFloat(
        initialValue = 0f,
        targetValue = -10f,
        animationSpec = infiniteRepeatable(
            animation = tween(900, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "bounce",
    )
    val tilt by transition.animateFloat(
        initialValue = -4f,
        targetValue = 4f,
        animationSpec = infiniteRepeatable(
            animation = tween(1400, easing = LinearEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "tilt",
    )
    val glow by transition.animateFloat(
        initialValue = 0.6f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1100, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse,
        ),
        label = "glow",
    )
    val sparkle by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(1600, easing = LinearEasing),
            repeatMode = RepeatMode.Restart,
        ),
        label = "sparkle",
    )

    val tip = pet.tip ?: ""
    var visibleTip by remember(pet.key, tip) { mutableStateOf(tip.isNotBlank() && showBubble) }
    LaunchedEffect(visibleTip, tip) {
        if (visibleTip && tip.isNotBlank()) {
            delay(6500)
            visibleTip = false
        }
    }
    LaunchedEffect(pet.grew) {
        if (pet.grew) {
            visibleTip = tip.isNotBlank()
            delay(8000)
            visibleTip = false
        }
    }

    val stageIndex = pet.index ?: 1
    val scale = if (enabled) 1f else 0.95f
    val tailOffset by animateDpAsState(
        targetValue = if (visibleTip) 0.dp else (-2).dp,
        animationSpec = spring(dampingRatio = Spring.DampingRatioMediumBouncy),
        label = "tail",
    )

    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = modifier,
    ) {
        if (visibleTip && tip.isNotBlank()) {
            PetBubble(
                text = tip,
                grew = pet.grew == true,
                modifier = Modifier.padding(bottom = 4.dp),
            )
            Box(
                modifier = Modifier
                    .offset(y = tailOffset)
                    .size(10.dp)
                    .rotate(45f)
                    .background(Color.White),
            )
        }
        Box(contentAlignment = Alignment.Center) {
            if (stageIndex >= 4) {
                Box(
                    modifier = Modifier
                        .size(size * (1f + 0.18f * glow))
                        .alpha(0.25f * glow)
                        .background(
                            brush = androidx.compose.ui.graphics.Brush.radialGradient(
                                listOf(
                                    MaterialTheme.colorScheme.tertiary.copy(alpha = 0.5f),
                                    Color.Transparent,
                                ),
                            ),
                            shape = CircleShape,
                        ),
                )
            }
            if (pet.canPat == true || pet.grew == true) {
                val spark = (sin(sparkle * 6.283f) + 1f) / 2f
                Text(
                    "✨",
                    fontSize = (10 + spark * 6).sp,
                    modifier = Modifier
                        .offset(x = size * 0.32f, y = -size * 0.26f - bounce.dp)
                        .alpha(0.8f),
                )
            }
            Text(
                text = pet.icon ?: "🐾",
                fontSize = (size.value * 0.72f).sp,
                modifier = Modifier
                    .offset(y = bounce.dp)
                    .rotate(tilt)
                    .scale(scale)
                    .clickable(enabled = enabled) {
                        visibleTip = tip.isNotBlank()
                        onClick()
                    },
                textAlign = TextAlign.Center,
            )
        }
        if (stageIndex >= 2 && showBubble) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(4.dp),
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.padding(top = 2.dp),
            ) {
                Text(pet.stageIcon ?: "🌟", fontSize = 12.sp)
                Text(
                    text = pet.stageName ?: "",
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.SemiBold,
                )
            }
        }
    }
}

@Composable
private fun PetBubble(
    text: String,
    grew: Boolean,
    modifier: Modifier = Modifier,
) {
    Surface(
        shape = RoundedCornerShape(16.dp),
        color = if (grew) MaterialTheme.colorScheme.primaryContainer else Color.White,
        shadowElevation = 4.dp,
        modifier = modifier,
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
            style = MaterialTheme.typography.bodySmall,
            textAlign = TextAlign.Center,
            fontWeight = if (grew) FontWeight.SemiBold else FontWeight.Normal,
        )
    }
}
