package com.edumath.uchus.ui.parent

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Paint
import android.util.LruCache
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.gestures.detectTransformGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableDoubleStateOf
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.edumath.uchus.data.api.LocationTrackDto
import com.edumath.uchus.data.api.MapSettingsDto
import com.edumath.uchus.data.api.ParentLocationsDto
import java.io.File
import kotlin.math.PI
import kotlin.math.atan
import kotlin.math.cos
import kotlin.math.exp
import kotlin.math.floor
import kotlin.math.ln
import kotlin.math.log2
import kotlin.math.max
import kotlin.math.min
import kotlin.math.pow
import kotlin.math.roundToInt
import kotlin.math.sin
import kotlin.math.sinh
import kotlin.math.tan
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import okhttp3.Cache
import okhttp3.OkHttpClient
import okhttp3.Request

/**
 * Карта GPS-контроля, нарисованная средствами Compose.
 *
 * Раньше карта показывалась в WebView, и на части устройств он оставлял
 * пустой светлый прямоугольник. Здесь тайлы загружаются тем же OkHttp,
 * которым приложение ходит на сервер, и рисуются на Canvas — без WebView.
 *
 * Проекция зависит от провайдера: Яндекс отдаёт тайлы в EPSG:3395
 * (эллипсоидальный Меркатор), остальные — в привычном Web Mercator.
 * При отказе тайлов выбранного провайдера карта целиком переключается на
 * OpenStreetMap, чтобы не смешивать две разные проекции.
 */
@Composable
internal fun NativeMapView(
    track: LocationTrackDto?,
    overview: ParentLocationsDto?,
    mapSettings: MapSettingsDto?,
    modifier: Modifier = Modifier,
    showRoute: Boolean = true,
    viewKey: String = "",
    focusLearnerId: Int? = null,
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val density = LocalDensity.current

    val settings = mapSettings
    val primaryTemplate = settings?.tileUrl?.takeIf { it.isNotBlank() } ?: OSM_TILE_URL
    var fallbackMode by remember(primaryTemplate, settings?.crs) { mutableStateOf(false) }
    val isYandex = !fallbackMode && settings?.crs.equals("yandex", ignoreCase = true)
    val tileTemplate = if (fallbackMode) OSM_TILE_URL else primaryTemplate
    val attribution = when {
        fallbackMode -> "© OpenStreetMap"
        !settings?.attribution.isNullOrBlank() -> settings?.attribution ?: "© OpenStreetMap"
        else -> "© OpenStreetMap"
    }

    val minZoom = ((settings?.minZoom ?: 1).coerceIn(1, 19))
    val maxZoom = ((settings?.maxZoom ?: 19).coerceIn(minZoom, 19))
    val startZoom = ((settings?.zoom ?: 16).coerceIn(minZoom, maxZoom))

    val points = track?.points.orEmpty()
    val markers = overview?.children.orEmpty().mapNotNull { child ->
        val point = child.lastPoint ?: return@mapNotNull null
        Marker(
            learnerId = child.learner?.id ?: 0,
            lat = point.lat,
            lon = point.lon,
            label = child.learner?.name ?: "Ребёнок",
            stale = child.stale,
        )
    }
    val focusMarkers = if (focusLearnerId == null) {
        markers
    } else {
        markers.filter { it.learnerId == focusLearnerId }.ifEmpty { markers }
    }
    val fitCoords: List<Pair<Double, Double>> = when {
        points.isEmpty() -> focusMarkers.map { it.lat to it.lon }
        showRoute -> points.map { it.lat to it.lon }
        else -> listOfNotNull(points.lastOrNull()?.let { it.lat to it.lon })
    }

    fun worldX(lon: Double, zoomValue: Double): Double =
        (lon + 180.0) / 360.0 * TILE_SIZE * 2.0.pow(zoomValue)

    fun worldY(lat: Double, zoomValue: Double): Double =
        if (isYandex) yandexWorldY(lat, zoomValue) else sphericalWorldY(lat, zoomValue)

    fun latFromWorldY(y: Double, zoomValue: Double): Double =
        if (isYandex) yandexLatFromWorldY(y, zoomValue) else sphericalLatFromWorldY(y, zoomValue)

    var zoom by remember { mutableFloatStateOf(startZoom.toFloat()) }
    var centerLat by remember { mutableDoubleStateOf(settings?.centerLat ?: 53.9023) }
    var centerLon by remember { mutableDoubleStateOf(settings?.centerLon ?: 27.5619) }
    var pan by remember { mutableStateOf(Offset.Zero) }
    var size by remember { mutableStateOf(IntSize.Zero) }

    val tiles = remember { mutableStateMapOf<String, Bitmap>() }
    val failed = remember { mutableStateMapOf<String, Boolean>() }
    val loading = remember { mutableSetOf<String>() }
    val client = remember(context) { tileClient(context) }
    var retryTick by remember { mutableIntStateOf(0) }
    var fallbackFailures by remember(primaryTemplate, settings?.crs) { mutableIntStateOf(0) }

    // Переключение «маршруты видны/скрыты» тоже меняет охват: с выключенными
    // маршрутами карта приближается к последней точке ребёнка.
    val dataIdentity = listOf(
        viewKey,
        track?.learner?.id ?: 0,
        track?.day ?: "",
        if (showRoute) "route" else "point",
    ).joinToString("|")
    var lastIdentity by remember { mutableStateOf<String?>(null) }
    var fittedWithData by remember { mutableStateOf(false) }
    var fitTick by remember { mutableIntStateOf(0) }

    // Первый показ, смена ребёнка/дня и кнопка «◎» подбирают масштаб под
    // точки. Автообновление каждые 30 секунд вид карты не сбрасывает.
    LaunchedEffect(
        dataIdentity,
        size,
        fitCoords.size,
        fitTick,
        settings?.centerLat,
        settings?.centerLon,
        settings?.zoom,
    ) {
        if (size.width == 0 || size.height == 0) return@LaunchedEffect
        val reset = dataIdentity != lastIdentity || fitTick > 0
        if (!reset && fittedWithData) return@LaunchedEffect
        pan = Offset.Zero
        if (fitCoords.isEmpty()) {
            zoom = startZoom.toFloat()
            centerLat = settings?.centerLat ?: 53.9023
            centerLon = settings?.centerLon ?: 27.5619
            lastIdentity = dataIdentity
            fittedWithData = false
            fitTick = 0
            return@LaunchedEffect
        }
        var minX = Double.MAX_VALUE
        var maxX = -Double.MAX_VALUE
        var minY = Double.MAX_VALUE
        var maxY = -Double.MAX_VALUE
        fitCoords.forEach { (lat, lon) ->
            val x = worldX(lon, 0.0)
            val y = worldY(lat, 0.0)
            if (x < minX) minX = x
            if (x > maxX) maxX = x
            if (y < minY) minY = y
            if (y > maxY) maxY = y
        }
        val dx = maxX - minX
        val dy = maxY - minY
        val margin = with(density) { 44.dp.toPx() }.toDouble()
        val wide = (size.width - margin).coerceAtLeast(64.0)
        val tall = (size.height - margin).coerceAtLeast(64.0)
        val fitZoomX = if (dx > 0.5) log2(wide / dx) else 17.0
        val fitZoomY = if (dy > 0.5) log2(tall / dy) else 17.0
        val target = min(fitZoomX, fitZoomY)
            .coerceIn(max(minZoom.toDouble(), 2.0), min(maxZoom.toDouble(), 17.0))
        zoom = target.toFloat()
        centerLon = lonFromWorldX((minX + maxX) / 2.0)
        centerLat = latFromWorldY((minY + maxY) / 2.0, 0.0)
        lastIdentity = dataIdentity
        fittedWithData = true
        fitTick = 0
    }

    val tileZ = zoom.toInt().coerceIn(1, maxZoom)
    val tileScale = 2.0.pow((zoom - tileZ).toDouble())
    val tilePx = TILE_SIZE * tileScale
    val centerX = worldX(centerLon, zoom.toDouble())
    val centerY = worldY(centerLat, zoom.toDouble())
    val originX = centerX - size.width / 2.0 - pan.x
    val originY = centerY - size.height / 2.0 - pan.y
    val tileCount = 1 shl tileZ

    val visibleTiles = remember(tileTemplate, isYandex, tileZ, originX, originY, size, tilePx) {
        if (size.width <= 0 || size.height <= 0) return@remember emptyList()
        val firstX = floor(originX / tilePx).toInt()
        val lastX = floor((originX + size.width) / tilePx).toInt()
        val firstY = floor(originY / tilePx).toInt()
        val lastY = floor((originY + size.height) / tilePx).toInt()
        buildList {
            for (tx in firstX..lastX) {
                for (ty in firstY..lastY) {
                    if (ty < 0 || ty >= tileCount) continue
                    val wrapped = ((tx % tileCount) + tileCount) % tileCount
                    add(
                        TileSpec(
                            url = tileUrl(tileTemplate, tileZ, wrapped, ty),
                            left = tx * tilePx - originX,
                            top = ty * tilePx - originY,
                        )
                    )
                }
            }
        }
    }

    LaunchedEffect(visibleTiles, retryTick, tileTemplate) {
        visibleTiles.forEach { spec ->
            if (tiles.containsKey(spec.url) || failed.containsKey(spec.url)) return@forEach
            if (spec.url in loading) return@forEach
            val cached = memoryTiles.get(spec.url)
            if (cached != null) {
                tiles[spec.url] = cached
                return@forEach
            }
            loading.add(spec.url)
            scope.launch {
                val bitmap = loadTile(client, spec.url)
                loading.remove(spec.url)
                if (bitmap != null) {
                    memoryTiles.put(spec.url, bitmap)
                    tiles[spec.url] = bitmap
                    failed.remove(spec.url)
                } else {
                    failed[spec.url] = true
                    if (!fallbackMode && primaryTemplate != OSM_TILE_URL) {
                        fallbackFailures += 1
                        if (fallbackFailures >= FALLBACK_AFTER_FAILURES) {
                            // Яндексу (или своему серверу) сейчас плохо —
                            // показываем карту целиком на OpenStreetMap.
                            fallbackMode = true
                            fallbackFailures = 0
                            failed.clear()
                            tiles.clear()
                        }
                    }
                }
            }
        }
    }

    val labelPaint = remember(density) {
        Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = android.graphics.Color.parseColor("#1e293b")
            textSize = with(density) { 10.sp.toPx() }
            typeface = android.graphics.Typeface.DEFAULT_BOLD
        }
    }
    val attributionPaint = remember(density) {
        Paint(Paint.ANTI_ALIAS_FLAG).apply {
            color = android.graphics.Color.parseColor("#475569")
            textSize = with(density) { 9.sp.toPx() }
        }
    }
    val attributionBackground = Color(0xCCFFFFFF)

    Box(modifier = modifier) {
        Canvas(
            modifier = Modifier
                .matchParentSize()
                .background(Color(0xFFDFE7F5))
                .onSizeChanged { size = it }
                .pointerInput(Unit) {
                    detectTapGestures(
                        onDoubleTap = { tap ->
                            val oldZoom = zoom
                            val newZoom = (zoom + 1f).coerceAtMost(maxZoom.toFloat())
                            if (newZoom != oldZoom) {
                                val factor = 2.0.pow((newZoom - oldZoom).toDouble()).toFloat()
                                val center = Offset(this.size.width / 2f, this.size.height / 2f)
                                val offset = tap - center
                                pan = pan * factor + offset * (1f - factor)
                                zoom = newZoom
                            }
                        }
                    )
                }
                .pointerInput(Unit) {
                    detectTransformGestures { centroid, panChange, gestureZoom, _ ->
                        val oldZoom = zoom
                        val newZoom = (zoom + log2(gestureZoom.toDouble()).toFloat())
                            .coerceIn(minZoom.toFloat(), maxZoom.toFloat())
                        val factor = 2.0.pow((newZoom - oldZoom).toDouble()).toFloat()
                        if (factor != 1f && centroid != Offset.Zero) {
                            val center = Offset(this.size.width / 2f, this.size.height / 2f)
                            val offset = centroid - center
                            pan = pan * factor + offset * (1f - factor)
                        }
                        pan += panChange
                        zoom = newZoom
                    }
                },
        ) {
            val width = this.size.width
            val height = this.size.height
            if (width <= 0f || height <= 0f) return@Canvas

            visibleTiles.forEach { spec ->
                val bitmap = tiles[spec.url] ?: return@forEach
                drawImage(
                    image = bitmap.asImageBitmap(),
                    srcOffset = IntOffset.Zero,
                    srcSize = IntSize(bitmap.width, bitmap.height),
                    dstOffset = IntOffset(
                        spec.left.roundToInt(),
                        spec.top.roundToInt(),
                    ),
                    dstSize = IntSize(tilePx.roundToInt(), tilePx.roundToInt()),
                    filterQuality = FilterQuality.Low,
                )
            }

            fun screenOf(lat: Double, lon: Double): Offset {
                val x = worldX(lon, zoom.toDouble()) - originX
                val y = worldY(lat, zoom.toDouble()) - originY
                return Offset(x.toFloat(), y.toFloat())
            }

            if (showRoute && points.size > 1) {
                val path = Path()
                points.forEachIndexed { index, point ->
                    val position = screenOf(point.lat, point.lon)
                    if (index == 0) path.moveTo(position.x, position.y)
                    else path.lineTo(position.x, position.y)
                }
                drawPath(
                    path = path,
                    color = Color(0xFF6366F1),
                    style = Stroke(
                        width = with(density) { 4.dp.toPx() },
                        cap = StrokeCap.Round,
                        join = StrokeJoin.Round,
                    ),
                )
            }

            if (showRoute) {
                points.forEachIndexed { index, point ->
                    val position = screenOf(point.lat, point.lon)
                    val edge = index == 0 || index == points.lastIndex
                    drawCircle(
                        color = Color.White,
                        radius = if (edge) with(density) { 7.dp.toPx() } else with(density) { 4.5.dp.toPx() },
                        center = position,
                    )
                    drawCircle(
                        color = if (edge) Color(0xFF4338CA) else Color(0xFF6366F1),
                        radius = if (edge) with(density) { 5.dp.toPx() } else with(density) { 3.dp.toPx() },
                        center = position,
                    )
                }
            } else {
                points.lastOrNull()?.let { point ->
                    val position = screenOf(point.lat, point.lon)
                    drawCircle(
                        color = Color.White,
                        radius = with(density) { 8.dp.toPx() },
                        center = position,
                    )
                    drawCircle(
                        color = Color(0xFF4338CA),
                        radius = with(density) { 5.5.dp.toPx() },
                        center = position,
                    )
                }
            }

            markers.forEach { marker ->
                val position = screenOf(marker.lat, marker.lon)
                drawCircle(
                    color = Color.White,
                    radius = with(density) { 9.dp.toPx() },
                    center = position,
                )
                drawCircle(
                    color = if (marker.stale) Color(0xFF94A3B8) else Color(0xFF16A34A),
                    radius = with(density) { 6.dp.toPx() },
                    center = position,
                )
                drawContext.canvas.nativeCanvas.drawText(
                    marker.label.take(18),
                    position.x + with(density) { 12.dp.toPx() },
                    position.y - with(density) { 8.dp.toPx() },
                    labelPaint,
                )
            }

            // Подпись источника в правом нижнем углу.
            val textWidth = attributionPaint.measureText(attribution)
            val padding = with(density) { 4.dp.toPx() }
            drawRect(
                color = attributionBackground,
                topLeft = Offset(width - textWidth - padding * 2, height - attributionPaint.textSize - padding * 2),
                size = androidx.compose.ui.geometry.Size(textWidth + padding * 2, attributionPaint.textSize + padding * 2),
            )
            drawContext.canvas.nativeCanvas.drawText(
                attribution,
                width - textWidth - padding,
                height - padding,
                attributionPaint,
            )
        }

        // Кнопки масштаба.
        Column(
            modifier = Modifier
                .align(Alignment.TopEnd)
                .padding(8.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            MapButton("+") {
                val newZoom = (zoom + 1f).coerceAtMost(maxZoom.toFloat())
                if (newZoom != zoom) {
                    pan *= 2.0.pow((newZoom - zoom).toDouble()).toFloat()
                    zoom = newZoom
                }
            }
            MapButton("−") {
                val newZoom = (zoom - 1f).coerceAtLeast(minZoom.toFloat())
                if (newZoom != zoom) {
                    pan *= 2.0.pow((newZoom - zoom).toDouble()).toFloat()
                    zoom = newZoom
                }
            }
            MapButton("◎") {
                fitTick += 1
            }
        }

        if (fallbackMode) {
            Surface(
                modifier = Modifier
                    .align(Alignment.TopStart)
                    .padding(8.dp),
                shape = MaterialTheme.shapes.small,
                color = Color(0xE6FFFFFF),
            ) {
                Text(
                    "Резервная карта OpenStreetMap",
                    modifier = Modifier.padding(horizontal = 8.dp, vertical = 4.dp),
                    style = MaterialTheme.typography.labelSmall,
                    color = Color(0xFF475569),
                )
            }
        }

        val failedCount = failed.size
        when {
            tiles.isEmpty() && failedCount > 0 -> {
                Surface(
                    modifier = Modifier
                        .align(Alignment.Center)
                        .padding(16.dp),
                    shape = MaterialTheme.shapes.medium,
                    color = Color(0xF2FFFFFF),
                    shadowElevation = 3.dp,
                ) {
                    Column(
                        modifier = Modifier.padding(14.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(
                            "Карта не загрузилась. Проверьте интернет.",
                            style = MaterialTheme.typography.bodySmall,
                        )
                        Text(
                            "Нажмите, чтобы попробовать снова",
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.primary,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier
                                .padding(top = 6.dp)
                                .clickable {
                                    failed.clear()
                                    // Даём основному провайдеру ещё один шанс:
                                    // возможно, пропал интернет, а не Яндекс.
                                    fallbackMode = false
                                    fallbackFailures = 0
                                    retryTick += 1
                                },
                        )
                    }
                }
            }
            tiles.isEmpty() -> {
                Surface(
                    modifier = Modifier.align(Alignment.Center),
                    shape = MaterialTheme.shapes.small,
                    color = Color(0xD9FFFFFF),
                ) {
                    Text(
                        "Загрузка карты…",
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 6.dp),
                        style = MaterialTheme.typography.labelSmall,
                    )
                }
            }
        }
    }
}

@Composable
private fun MapButton(text: String, onClick: () -> Unit) {
    Surface(
        shape = CircleShape,
        color = Color(0xF2FFFFFF),
        shadowElevation = 2.dp,
        modifier = Modifier
            .size(32.dp)
            .clickable(onClick = onClick),
    ) {
        Box(contentAlignment = Alignment.Center) {
            Text(text, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
        }
    }
}

private data class Marker(
    val learnerId: Int,
    val lat: Double,
    val lon: Double,
    val label: String,
    val stale: Boolean,
)

private data class TileSpec(
    val url: String,
    val left: Double,
    val top: Double,
)

private const val TILE_SIZE = 256.0
private const val OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
private const val FALLBACK_AFTER_FAILURES = 3

// EPSG:3857 / Web Mercator.
private const val EARTH_RADIUS = 6378137.0
// EPSG:3395 / эллипсоидальный Меркатор (Яндекс).
private const val ECCENTRICITY = 0.08181919084262149

private val memoryTiles = LruCache<String, Bitmap>(240)

private fun tileClient(context: Context): OkHttpClient = OkHttpClient.Builder()
    .cache(Cache(File(context.cacheDir, "map-tiles"), 48L * 1024 * 1024))
    .build()

private suspend fun loadTile(client: OkHttpClient, url: String): Bitmap? =
    withContext(Dispatchers.IO) {
        runCatching {
            val request = Request.Builder()
                .url(url)
                .header("User-Agent", "Uchus-Android/1.9.13")
                .header("Accept", "image/png,image/*;q=0.8")
                .build()
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) return@use null
                BitmapFactory.decodeStream(response.body?.byteStream())
            }
        }.getOrNull()
    }

private fun tileUrl(template: String, z: Int, x: Int, y: Int): String =
    template
        .replace("{z}", z.toString())
        .replace("{x}", x.toString())
        .replace("{y}", y.toString())
        .replace("{-y}", ((1 shl z) - 1 - y).toString())

private fun lonFromWorldX(x: Double): Double = x / TILE_SIZE * 360.0 - 180.0

private fun sphericalWorldY(lat: Double, zoom: Double): Double {
    val clamped = lat.coerceIn(-85.05112878, 85.05112878)
    val rad = Math.toRadians(clamped)
    return (1.0 - ln(tan(rad) + 1.0 / cos(rad)) / PI) / 2.0 *
        TILE_SIZE * 2.0.pow(zoom)
}

private fun sphericalLatFromWorldY(y: Double, zoom: Double): Double {
    val n = PI - 2.0 * PI * y / (TILE_SIZE * 2.0.pow(zoom))
    return Math.toDegrees(atan(sinh(n)))
}

/**
 * Эллипсоидальный Меркатор EPSG:3395, в котором Яндекс нумерует тайлы.
 * Сферическая формула Web Mercator здесь не подходит: на широте Минска
 * расхождение достигает сотни тайлов, и точка уезжает в другой район.
 */
private fun yandexWorldY(lat: Double, zoom: Double): Double {
    val clamped = lat.coerceIn(-85.05112878, 85.05112878)
    val rad = Math.toRadians(clamped)
    val sinLat = sin(rad)
    val ecc = ((1.0 - ECCENTRICITY * sinLat) / (1.0 + ECCENTRICITY * sinLat))
        .pow(ECCENTRICITY / 2.0)
    val mercatorY = EARTH_RADIUS * ln(tan(PI / 4.0 + rad / 2.0) * ecc)
    return (0.5 - mercatorY / (2.0 * PI * EARTH_RADIUS)) *
        TILE_SIZE * 2.0.pow(zoom)
}

private fun yandexLatFromWorldY(y: Double, zoom: Double): Double {
    val norm = y / (TILE_SIZE * 2.0.pow(zoom))
    val ts = exp(-(0.5 - norm) * 2.0 * PI)
    var phi = PI / 2.0 - 2.0 * atan(ts)
    repeat(15) {
        val sinLat = sin(phi)
        val ecc = ((1.0 - ECCENTRICITY * sinLat) / (1.0 + ECCENTRICITY * sinLat))
            .pow(ECCENTRICITY / 2.0)
        phi = PI / 2.0 - 2.0 * atan(ts * ecc)
    }
    return Math.toDegrees(phi)
}
