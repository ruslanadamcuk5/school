package com.edumath.uchus.ui.common

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import java.util.Locale

/**
 * Текст объяснения без markdown-разметки — для показа и озвучивания.
 */
fun plainAiText(text: String): String = text
    .replace(Regex("(?m)^#{1,6}\\s*"), "")
    .replace("**", "")
    .replace(Regex("(?m)^\\s*[-*]\\s+"), "• ")
    .replace(Regex("`+"), "")
    .trim()
/**
 * Озвучивание текста системным синтезатором речи.
 *
 * Работает без интернета и без сторонних сервисов: используется тот голос,
 * который уже установлен в Android. Длинный текст режется на фразы, чтобы
 * синтезатор не обрывал объяснение.
 */
class Speaker(context: Context) {

    private val main = Handler(Looper.getMainLooper())
    private var engine: TextToSpeech? = null
    private var ready = false
    private var pending: String? = null
    private var prefix = ""
    private var remaining = 0

    var speaking by mutableStateOf(false)
        private set
    var error by mutableStateOf<String?>(null)
        private set

    init {
        engine = TextToSpeech(context.applicationContext) { status ->
            if (status != TextToSpeech.SUCCESS) {
                main.post { error = "Синтез речи недоступен на этом устройстве." }
                return@TextToSpeech
            }
            val tts = engine ?: return@TextToSpeech
            tts.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                override fun onStart(utteranceId: String?) {
                    main.post { speaking = true }
                }

                override fun onDone(utteranceId: String?) {
                    finish(utteranceId)
                }

                @Deprecated("Deprecated in Java")
                override fun onError(utteranceId: String?) {
                    finish(utteranceId)
                }

                override fun onError(utteranceId: String?, errorCode: Int) {
                    finish(utteranceId)
                }
            })
            ready = true
            pending?.let { text ->
                pending = null
                speak(text)
            }
        }
        error = null
    }

    /** Прочитать текст вслух, заменив текущее озвучивание. */
    fun speak(text: String) {
        val clean = text.trim()
        if (clean.isEmpty()) return
        val tts = engine
        if (!ready || tts == null) {
            pending = clean
            return
        }
        error = null
        tts.stop()
        val pieces = split(clean)
        if (pieces.isEmpty()) return
        prefix = "u${System.nanoTime()}"
        remaining = pieces.size
        speaking = true
        val locale = preferredLocale(clean)
        val result = tts.setLanguage(locale)
        if (result == TextToSpeech.LANG_MISSING_DATA ||
            result == TextToSpeech.LANG_NOT_SUPPORTED
        ) {
            tts.setLanguage(Locale.getDefault())
        }
        pieces.forEachIndexed { index, piece ->
            tts.speak(
                piece,
                if (index == 0) TextToSpeech.QUEUE_FLUSH else TextToSpeech.QUEUE_ADD,
                null,
                "$prefix-$index",
            )
        }
    }

    fun stop() {
        pending = null
        remaining = 0
        speaking = false
        engine?.stop()
    }

    fun shutdown() {
        pending = null
        speaking = false
        engine?.stop()
        engine?.shutdown()
        engine = null
        ready = false
    }

    private fun finish(utteranceId: String?) {
        if (utteranceId == null || !utteranceId.startsWith(prefix)) return
        main.post {
            remaining -= 1
            if (remaining <= 0) speaking = false
        }
    }

    /** Русский для кириллицы, английский для латиницы. */
    private fun preferredLocale(text: String): Locale {
        val cyr = text.count { it in 'А'..'я' || it == 'ё' || it == 'Ё' }
        val lat = text.count { it in 'A'..'Z' || it in 'a'..'z' }
        return if (lat > cyr) Locale.US else Locale.forLanguageTag("ru-RU")
    }

    /** Нарезать текст на фразы до 700 символов. */
    private fun split(text: String): List<String> {
        val clean = text
            .replace(Regex("```[\\s\\S]*?```"), " ")
            .replace(Regex("[#*_`>]+"), " ")
            .replace(Regex("\\s+"), " ")
            .trim()
        if (clean.isEmpty()) return emptyList()
        val pieces = mutableListOf<String>()
        val buffer = StringBuilder()
        val sentences = clean.split(Regex("(?<=[.!?…:])\\s+"))
        for (sentence in sentences) {
            for (part in sentence.chunked(700)) {
                if (buffer.isNotEmpty() &&
                    buffer.length + part.length + 1 > 700
                ) {
                    pieces.add(buffer.toString())
                    buffer.clear()
                }
                if (buffer.isNotEmpty()) buffer.append(' ')
                buffer.append(part)
            }
        }
        if (buffer.isNotEmpty()) pieces.add(buffer.toString())
        return pieces
    }
}
