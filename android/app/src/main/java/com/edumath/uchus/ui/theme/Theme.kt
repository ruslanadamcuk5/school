package com.edumath.uchus.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.runtime.Stable
import androidx.compose.ui.unit.dp

enum class DesignMode {
    PLAYFUL,
    STRICT
}

@Stable
data class DesignTheme(
    val mode: DesignMode,
    val isDark: Boolean = false
)

private val PlayfulLightColors = lightColorScheme(
    primary = Color(0xFF4F46E5),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE0E7FF),
    onPrimaryContainer = Color(0xFF1E1B4B),
    secondary = Color(0xFF06B6D4),
    onSecondary = Color.White,
    tertiary = Color(0xFFF59E0B),
    background = Color(0xFFF6F7FB),
    onBackground = Color(0xFF0F172A),
    surface = Color.White,
    onSurface = Color(0xFF0F172A),
    surfaceVariant = Color(0xFFEEF2F7),
    error = Color(0xFFDC2626),
)

private val PlayfulDarkColors = darkColorScheme(
    primary = Color(0xFFA5B4FC),
    onPrimary = Color(0xFF1E1B4B),
    secondary = Color(0xFF67E8F9),
    background = Color(0xFF0F172A),
    onBackground = Color(0xFFE2E8F0),
    surface = Color(0xFF1E293B),
    onSurface = Color(0xFFE2E8F0),
    surfaceVariant = Color(0xFF334155),
    error = Color(0xFFFCA5A5),
)

private val StrictLightColors = lightColorScheme(
    primary = Color(0xFF1E3A5F),
    onPrimary = Color.White,
    primaryContainer = Color(0xFFD6E4F0),
    onPrimaryContainer = Color(0xFF0C1F3A),
    secondary = Color(0xFF475569),
    onSecondary = Color.White,
    tertiary = Color(0xFF334155),
    background = Color(0xFFF2F4F7),
    onBackground = Color(0xFF0F172A),
    surface = Color.White,
    onSurface = Color(0xFF0F172A),
    surfaceVariant = Color(0xFFE7EAEF),
    error = Color(0xFF8F3333),
)

private val StrictDarkColors = darkColorScheme(
    primary = Color(0xFF93B7E6),
    onPrimary = Color(0xFF0C1F3A),
    secondary = Color(0xFFB8C5D6),
    background = Color(0xFF0F172A),
    onBackground = Color(0xFFE2E8F0),
    surface = Color(0xFF1E293B),
    onSurface = Color(0xFFE2E8F0),
    surfaceVariant = Color(0xFF334155),
    error = Color(0xFFFCA5A5),
)

val LocalDesignMode = staticCompositionLocalOf { DesignMode.PLAYFUL }

@Composable
fun UchusTheme(
    designMode: DesignMode = DesignMode.PLAYFUL,
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colors = when {
        designMode == DesignMode.STRICT && darkTheme -> StrictDarkColors
        designMode == DesignMode.STRICT -> StrictLightColors
        darkTheme -> PlayfulDarkColors
        else -> PlayfulLightColors
    }
    val shapes = when (designMode) {
        DesignMode.PLAYFUL -> androidx.compose.material3.Shapes(
            extraSmall = 8.dp,
            small = 12.dp,
            medium = 16.dp,
            large = 24.dp,
            extraLarge = 32.dp,
        )
        DesignMode.STRICT -> androidx.compose.material3.Shapes(
            extraSmall = 6.dp,
            small = 8.dp,
            medium = 10.dp,
            large = 12.dp,
            extraLarge = 14.dp,
        )
    }
    CompositionLocalProvider(LocalDesignMode provides designMode) {
        MaterialTheme(
            colorScheme = colors,
            shapes = shapes,
            content = content,
        )
    }
}

@Composable
fun DesignMode.current(): DesignMode = LocalDesignMode.current

@Composable
fun DesignMode.isPlayful(): Boolean = LocalDesignMode.current == DesignMode.PLAYFUL

@Composable
fun DesignMode.isStrict(): Boolean = LocalDesignMode.current == DesignMode.STRICT