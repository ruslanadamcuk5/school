package com.edumath.uchus.ui.auth

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Base64
import androidx.browser.customtabs.CustomTabsIntent
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.security.MessageDigest
import java.security.SecureRandom

/**
 * Вход через Google в браузере телефона (Custom Tabs) — запасной путь, если
 * Credential Manager на устройстве недоступен.
 *
 * Приложение открывает ``/auth/google?client=android&challenge=…``, сайт
 * проводит обычный OAuth и возвращает одноразовый код по схеме
 * ``uchus://auth?code=…``. Код бесполезен без ``verifier`` (PKCE), который
 * остаётся в приложении, поэтому перехват ссылки другим приложением не даёт
 * войти в аккаунт.
 */
object GoogleBrowserAuth {

    data class Callback(val code: String?, val error: String?)

    private const val PREFS = "google_browser_auth"
    private const val KEY_VERIFIER = "verifier"

    private val _callbacks = MutableStateFlow<Callback?>(null)
    val callbacks = _callbacks.asStateFlow()

    /** Открыть страницу входа Google в браузере. false — браузер не открылся. */
    fun start(context: Context, serverUrl: String): Boolean {
        val base = serverUrl.trim().trimEnd('/')
        if (!base.startsWith("https://") && !base.startsWith("http://")) return false
        val verifier = randomVerifier()
        val challenge = challengeFor(verifier)
        val uri = Uri.parse("$base/auth/google")
            .buildUpon()
            .appendQueryParameter("client", "android")
            .appendQueryParameter("challenge", challenge)
            .build()
        saveVerifier(context, verifier)
        return try {
            CustomTabsIntent.Builder().build().launchUrl(context, uri)
            true
        } catch (e: Exception) {
            clearVerifier(context)
            false
        }
    }

    /** Разобрать ссылку возврата из браузера (вызывается из MainActivity). */
    fun handleIntent(intent: Intent?) {
        val data = intent?.data ?: return
        if (data.scheme != "uchus" || data.host != "auth") return
        val code = data.getQueryParameter("code")?.takeIf { it.isNotBlank() }
        val error = data.getQueryParameter("error")?.takeIf { it.isNotBlank() }
        if (code == null && error == null) return
        _callbacks.value = Callback(code, error)
    }

    fun consume() {
        _callbacks.value = null
    }

    /** Забрать verifier (однократно) для обмена кода на токен. */
    fun takeVerifier(context: Context): String? {
        val prefs = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
        val value = prefs.getString(KEY_VERIFIER, null)
        if (value != null) prefs.edit().remove(KEY_VERIFIER).apply()
        return value
    }

    fun errorText(error: String): String = when (error) {
        "cancelled" -> "Вход через Google отменён"
        "no_code" -> "Google не вернул код входа. Попробуйте ещё раз"
        "google_error" -> "Не удалось войти через Google. Попробуйте ещё раз"
        "inactive" -> "Аккаунт отключён. Обратитесь к администратору"
        else -> "Не удалось войти через Google. Попробуйте ещё раз"
    }

    private fun saveVerifier(context: Context, verifier: String) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .putString(KEY_VERIFIER, verifier)
            .apply()
    }

    private fun clearVerifier(context: Context) {
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)
            .edit()
            .remove(KEY_VERIFIER)
            .apply()
    }

    private fun randomVerifier(): String {
        val bytes = ByteArray(32)
        SecureRandom().nextBytes(bytes)
        return Base64.encodeToString(
            bytes,
            Base64.NO_WRAP or Base64.URL_SAFE or Base64.NO_PADDING,
        )
    }

    private fun challengeFor(verifier: String): String {
        val digest = MessageDigest.getInstance("SHA-256")
            .digest(verifier.toByteArray(Charsets.US_ASCII))
        return Base64.encodeToString(
            digest,
            Base64.NO_WRAP or Base64.URL_SAFE or Base64.NO_PADDING,
        )
    }
}
