package com.edumath.uchus.ui.student

import android.annotation.SuppressLint
import android.graphics.Color
import android.net.Uri
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.ui.common.ScreenScaffold

/**
 * 3D-квест внутри темы.
 *
 * Плеер — тот же, что на сайте: один Three.js-сценарий обслуживает все
 * предметы и темы. Токен передаётся во фрагменте адреса (он не уходит на
 * сервер), а сайт сразу сохраняет его в localStorage встроенного WebView.
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun QuestScreen(
    container: AppContainer,
    slug: String,
    onBack: () -> Unit,
) {
    val token = container.session.token.orEmpty()
    val base = container.session.baseUrl.trimEnd('/')
    val url = "$base/app/quests/${Uri.encode(slug)}#token=${Uri.encode(token)}"
    var webView by remember { mutableStateOf<WebView?>(null) }

    BackHandler {
        val view = webView
        if (view != null && view.canGoBack()) view.goBack() else onBack()
    }

    ScreenScaffold(title = "3D-квест", onBack = onBack) { padding ->
        Box(Modifier.fillMaxSize().padding(padding)) {
            if (token.isBlank()) {
                Text(
                    text = "Войдите в аккаунт, чтобы открыть квест.",
                    color = MaterialTheme.colorScheme.onBackground,
                    modifier = Modifier.align(Alignment.Center),
                )
            } else {
                AndroidView(
                    modifier = Modifier.fillMaxSize(),
                    factory = { context ->
                        WebView(context).apply {
                            setBackgroundColor(Color.BLACK)
                            settings.javaScriptEnabled = true
                            settings.domStorageEnabled = true
                            settings.javaScriptCanOpenWindowsAutomatically = true
                            settings.mediaPlaybackRequiresUserGesture = false
                            settings.allowFileAccess = false
                            settings.allowContentAccess = false
                            settings.builtInZoomControls = false
                            settings.displayZoomControls = false
                            settings.useWideViewPort = true
                            settings.loadWithOverviewMode = true
                            settings.mixedContentMode = WebSettings.MIXED_CONTENT_COMPATIBILITY_MODE
                            webChromeClient = WebChromeClient()
                            webViewClient = WebViewClient()
                            loadUrl(url)
                            webView = this
                        }
                    },
                    update = { view -> webView = view },
                )
            }
        }
    }
}
