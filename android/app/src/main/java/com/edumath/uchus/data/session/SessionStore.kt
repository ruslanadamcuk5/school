package com.edumath.uchus.data.session

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import com.edumath.uchus.BuildConfig
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

private val Context.sessionDataStore by preferencesDataStore(name = "uchus_session")

data class StoredSession(
    val token: String,
    val baseUrl: String,
    val sessionJson: String,
)

/**
 * Хранилище сессии: токен, адрес сервера и последний снимок профиля.
 * Токен и адрес дублируются в памяти — их читает сетевой перехватчик.
 */
class SessionStore(private val context: Context) {

    @Volatile
    var baseUrl: String = BuildConfig.DEFAULT_SERVER_URL
        private set

    @Volatile
    var token: String? = null
        private set

    @Volatile
    var deviceId: String = ""
        private set

    private val _current = MutableStateFlow<StoredSession?>(null)
    val current: StateFlow<StoredSession?> = _current.asStateFlow()

    private val _loaded = MutableStateFlow(false)
    val loaded: StateFlow<Boolean> = _loaded.asStateFlow()

    private val flow: Flow<StoredSession?> = context.sessionDataStore.data.map { prefs ->
        val token = prefs[Keys.TOKEN]
        val baseUrl = prefs[Keys.BASE_URL]
        val json = prefs[Keys.SESSION]
        if (token.isNullOrBlank() || baseUrl.isNullOrBlank() || json.isNullOrBlank()) {
            null
        } else {
            StoredSession(token, baseUrl, json)
        }
    }

    suspend fun hydrate(): StoredSession? {
        val stored = flow.first()
        if (stored != null) {
            token = stored.token
            baseUrl = stored.baseUrl
        }
        loadOrCreateDeviceId()
        _current.value = stored
        _loaded.value = true
        return stored
    }

    /** Идентификатор устройства: к нему привязаны семейные профили. */
    suspend fun loadOrCreateDeviceId(): String {
        val prefs = context.sessionDataStore.data.first()
        val existing = prefs[Keys.DEVICE]
        if (!existing.isNullOrBlank()) {
            deviceId = existing
            return existing
        }
        val generated = java.util.UUID.randomUUID().toString()
        context.sessionDataStore.edit { it[Keys.DEVICE] = generated }
        deviceId = generated
        return generated
    }

    /** Задать адрес сервера до первого входа (ещё не сохранён). */
    fun primeBaseUrl(raw: String) {
        baseUrl = normalizeBaseUrl(raw)
    }

    suspend fun save(baseUrl: String, token: String, sessionJson: String) {
        val normalized = normalizeBaseUrl(baseUrl)
        this.baseUrl = normalized
        this.token = token
        context.sessionDataStore.edit { prefs ->
            prefs[Keys.TOKEN] = token
            prefs[Keys.BASE_URL] = normalized
            prefs[Keys.SESSION] = sessionJson
        }
        _current.value = StoredSession(token, normalized, sessionJson)
        _loaded.value = true
    }

    /** Обновить только снимок профиля (после /auth/me). */
    suspend fun updateSnapshot(sessionJson: String) {
        val token = token ?: return
        val baseUrl = baseUrl
        context.sessionDataStore.edit { prefs ->
            prefs[Keys.SESSION] = sessionJson
        }
        _current.value = StoredSession(token, baseUrl, sessionJson)
    }

    suspend fun clear() {
        token = null
        context.sessionDataStore.edit { prefs ->
            prefs.remove(Keys.TOKEN)
            prefs.remove(Keys.SESSION)
        }
        _current.value = null
    }

    private object Keys {
        val TOKEN = stringPreferencesKey("token")
        val BASE_URL = stringPreferencesKey("base_url")
        val SESSION = stringPreferencesKey("session_json")
        val DEVICE = stringPreferencesKey("device_id")
    }

    companion object {
        fun normalizeBaseUrl(raw: String): String {
            var value = raw.trim()
            if (value.isEmpty()) return BuildConfig.DEFAULT_SERVER_URL
            if (!value.startsWith("http://") && !value.startsWith("https://")) {
                value = "https://$value"
            }
            return value.trimEnd('/')
        }
    }
}
