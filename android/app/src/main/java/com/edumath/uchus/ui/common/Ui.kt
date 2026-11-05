package com.edumath.uchus.ui.common

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.edumath.uchus.ui.theme.SitePalette

/**
 * Фон приложения как на сайте: глубокий «чернильный» градиент.
 */
@Composable
fun SiteBackground(content: @Composable BoxScope.() -> Unit) {
    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(
                Brush.verticalGradient(
                    listOf(SitePalette.Ink950, SitePalette.Ink900, SitePalette.Ink950),
                ),
            ),
        content = content,
    )
}

/** Карточка в стиле сайта: тёмная поверхность, тонкая рамка, мягкие углы. */
@Composable
fun SiteCard(
    modifier: Modifier = Modifier,
    content: @Composable () -> Unit,
) {
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .border(1.dp, SitePalette.Border, RoundedCornerShape(20.dp)),
        color = SitePalette.Ink850,
        contentColor = MaterialTheme.colorScheme.onSurface,
        shape = RoundedCornerShape(20.dp),
        content = content,
    )
}

@Composable
fun LoadingBox(text: String = "Загрузка…") {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .padding(32.dp),
        contentAlignment = Alignment.Center,
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            CircularProgressIndicator(
                modifier = Modifier.size(22.dp),
                strokeWidth = 2.dp,
                color = MaterialTheme.colorScheme.primary,
            )
            Spacer(Modifier.width(12.dp))
            Text(text, style = MaterialTheme.typography.bodyMedium, color = SitePalette.Muted)
        }
    }
}

@Composable
fun ErrorBox(message: String, onRetry: (() -> Unit)? = null) {
    Surface(
        color = MaterialTheme.colorScheme.errorContainer,
        contentColor = MaterialTheme.colorScheme.onErrorContainer,
        shape = RoundedCornerShape(18.dp),
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, MaterialTheme.colorScheme.error.copy(alpha = 0.35f), RoundedCornerShape(18.dp)),
    ) {
        Column(Modifier.padding(16.dp)) {
            Text("Не получилось", fontWeight = FontWeight.Bold)
            Spacer(Modifier.height(4.dp))
            Text(message, style = MaterialTheme.typography.bodySmall)
            if (onRetry != null) {
                Spacer(Modifier.height(10.dp))
                Button(onClick = onRetry) { Text("Повторить") }
            }
        }
    }
}

@Composable
fun InfoBox(text: String, color: Color = SitePalette.Ink800) {
    Surface(
        color = color,
        shape = RoundedCornerShape(16.dp),
        modifier = Modifier
            .fillMaxWidth()
            .border(1.dp, SitePalette.Border, RoundedCornerShape(16.dp)),
    ) {
        Text(
            text,
            modifier = Modifier.padding(14.dp),
            style = MaterialTheme.typography.bodySmall,
            color = SitePalette.Muted,
        )
    }
}

@Composable
fun EmptyBox(text: String, emoji: String = "🕊") {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(28.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(emoji, style = MaterialTheme.typography.headlineLarge)
        Text(
            text,
            style = MaterialTheme.typography.bodyMedium,
            color = SitePalette.Muted,
            textAlign = TextAlign.Center,
        )
    }
}

@Composable
fun StatPill(label: String, value: String) {
    Surface(
        color = SitePalette.Ink850,
        contentColor = SitePalette.Text,
        shape = RoundedCornerShape(16.dp),
        modifier = Modifier.border(1.dp, SitePalette.Border, RoundedCornerShape(16.dp)),
    ) {
        Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp)) {
            Text(value, fontWeight = FontWeight.ExtraBold, style = MaterialTheme.typography.titleMedium)
            Text(
                label.uppercase(),
                style = MaterialTheme.typography.labelSmall,
                color = SitePalette.MutedDim,
            )
        }
    }
}
