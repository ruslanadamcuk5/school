package com.edumath.uchus.data.cache

import android.content.Context
import java.io.File

/**
 * Простой кэш JSON-ответов для чтения без сети.
 * Ключ — произвольная строка (например, "map:3:1").
 */
class JsonCache(
    context: Context,
    private val ttlMillis: Long = 12 * 60 * 60 * 1000L,
) {

    private val dir: File = File(context.cacheDir, "api").apply { mkdirs() }

    fun put(key: String, json: String) {
        runCatching {
            fileFor(key).writeText("${System.currentTimeMillis()}\n$json", Charsets.UTF_8)
        }
    }

    fun get(key: String): String? {
        val file = fileFor(key)
        if (!file.isFile) return null
        return runCatching {
            val text = file.readText(Charsets.UTF_8)
            val newline = text.indexOf('\n')
            if (newline <= 0) return@runCatching null
            val ts = text.substring(0, newline).toLongOrNull() ?: return@runCatching null
            if (System.currentTimeMillis() - ts > ttlMillis) {
                file.delete()
                null
            } else {
                text.substring(newline + 1)
            }
        }.getOrNull()
    }

    fun clear() {
        runCatching { dir.listFiles()?.forEach { it.delete() } }
    }

    private fun fileFor(key: String): File {
        val safe = key.replace(Regex("[^A-Za-z0-9_.-]"), "_").take(80)
        return File(dir, "$safe.json")
    }
}
