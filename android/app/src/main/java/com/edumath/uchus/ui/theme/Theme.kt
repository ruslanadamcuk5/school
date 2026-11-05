package com.edumath.uchus.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Stable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

enum class DesignMode {
    PLAYFUL,
    STRICT
}

@Stable
data class DesignTheme(
    val mode: DesignMode,
    val isDark: Boolean = true,
)

/**
 * Палитра сайта school-v2: тёмный «чернильный» фон, фиолетовый iris и
 * бирюзовые акценты. Один и тот же стиль для всех ролей, чтобы приложение
 * выглядело как сайт.
 */
object SitePalette {
    val Ink950 = Color(0xFF070A12)
    val Ink900 = Color(0xFF0B1020)
    val Ink850 = Color(0xFF0E1526)
    val Ink800 = Color(0xFF131C31)
    val Border = Color(0xFF222C44)
    val Iris400 = Color(0xFF9B87FF)
    val Iris500 = Color(0xFF7C5CFF)
    val Iris600 = Color(0xFF6A45F5)
    val Cyan400 = Color(0xFF22D3EE)
    val Gold400 = Color(0xFFF5B84B)
    val Rose400 = Color(0xFFFF6B81)
    val Text = Color(0xFFE8EBF5)
    val Muted = Color(0xFF98A2C0)
    val MutedDim = Color(0xFF6C7896)
}

private val SiteDarkColors = darkColorScheme(
    primary = SitePalette.Iris500,
    onPrimary = Color.White,
    primaryContainer = Color(0xFF241B4D),
    onPrimaryContainer = Color(0xFFE4DEFF),
    secondary = SitePalette.Cyan400,
    onSecondary = Color(0xFF04212A),
    secondaryContainer = Color(0xFF0D3040),
    onSecondaryContainer = Color(0xFFB9F3FF),
    tertiary = SitePalette.Gold400,
    onTertiary = Color(0xFF2A1C00),
    background = SitePalette.Ink950,
    onBackground = SitePalette.Text,
    surface = SitePalette.Ink900,
    onSurface = SitePalette.Text,
    surfaceVariant = SitePalette.Ink800,
    onSurfaceVariant = SitePalette.Muted,
    surfaceContainer = SitePalette.Ink850,
    surfaceContainerHigh = SitePalette.Ink800,
    outline = SitePalette.Border,
    outlineVariant = Color(0xFF1A2337),
    error = SitePalette.Rose400,
    onError = Color(0xFF2B0710),
    errorContainer = Color(0xFF3A1220),
    onErrorContainer = Color(0xFFFFD9DF),
)

private val SiteLightColors = lightColorScheme(
    primary = SitePalette.Iris600,
    onPrimary = Color.White,
    primaryContainer = Color(0xFFE8E2FF),
    onPrimaryContainer = Color(0xFF23144F),
    secondary = Color(0xFF0891B2),
    onSecondary = Color.White,
    background = Color(0xFFF5F6FB),
    onBackground = Color(0xFF0D1326),
    surface = Color.White,
    onSurface = Color(0xFF0D1326),
    surfaceVariant = Color(0xFFEDF0F8),
    onSurfaceVariant = Color(0xFF5B6480),
    outline = Color(0xFFD4DAEA),
    error = Color(0xFFD92D4C),
)

private val SiteTypography = Typography(
    displayLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.ExtraBold,
        fontSize = 40.sp,
        letterSpacing = (-1).sp,
    ),
    headlineLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.ExtraBold,
        fontSize = 30.sp,
        letterSpacing = (-0.6).sp,
    ),
    headlineMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.ExtraBold,
        fontSize = 25.sp,
        letterSpacing = (-0.4).sp,
    ),
    titleLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Bold,
        fontSize = 20.sp,
        letterSpacing = (-0.2).sp,
    ),
    titleMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 16.sp,
    ),
    bodyLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Normal,
        fontSize = 16.sp,
        lineHeight = 24.sp,
    ),
    bodyMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        lineHeight = 21.sp,
    ),
    bodySmall = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Normal,
        fontSize = 12.5.sp,
        lineHeight = 18.sp,
    ),
    labelLarge = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 13.sp,
    ),
    labelMedium = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.SemiBold,
        fontSize = 12.sp,
    ),
    labelSmall = TextStyle(
        fontFamily = FontFamily.SansSerif,
        fontWeight = FontWeight.Bold,
        fontSize = 10.5.sp,
        letterSpacing = 0.6.sp,
    ),
)

val LocalDesignMode = staticCompositionLocalOf { DesignMode.PLAYFUL }

@Composable
fun UchusTheme(
    designMode: DesignMode = DesignMode.PLAYFUL,
    darkTheme: Boolean = true,
    content: @Composable () -> Unit,
) {
    val colors = if (darkTheme) SiteDarkColors else SiteLightColors
    val shapes = androidx.compose.material3.Shapes(
        extraSmall = RoundedCornerShape(10.dp),
        small = RoundedCornerShape(12.dp),
        medium = RoundedCornerShape(18.dp),
        large = RoundedCornerShape(24.dp),
        extraLarge = RoundedCornerShape(30.dp),
    )
    CompositionLocalProvider(LocalDesignMode provides designMode) {
        MaterialTheme(
            colorScheme = colors,
            shapes = shapes,
            typography = SiteTypography,
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
