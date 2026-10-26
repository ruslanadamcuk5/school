package com.edumath.uchus.data.api

import com.google.gson.Gson
import com.google.gson.GsonBuilder
import com.google.gson.TypeAdapter
import com.google.gson.stream.JsonReader
import com.google.gson.stream.JsonToken
import com.google.gson.stream.JsonWriter

/**
 * Единый Gson для сети и локального кэша.
 *
 * Сервер и старые версии приложения могли присылать флаги как 0/1.
 * Такой адаптер не даёт входу и тренировкам падать на «Expected a boolean
 * but was NUMBER», а также принимает устаревшие имена полей.
 */
object ApiJson {

    private val booleanAdapter = object : TypeAdapter<Boolean>() {
        override fun write(out: JsonWriter, value: Boolean?) {
            if (value == null) out.nullValue() else out.value(value)
        }

        override fun read(input: JsonReader): Boolean = when (input.peek()) {
            JsonToken.BOOLEAN -> input.nextBoolean()
            JsonToken.NUMBER -> input.nextInt() != 0
            JsonToken.STRING -> {
                val value = input.nextString().trim().lowercase()
                value == "1" || value == "true" || value == "yes" || value == "on"
            }
            JsonToken.NULL -> {
                input.nextNull()
                false
            }
            else -> {
                input.skipValue()
                false
            }
        }
    }

    val gson: Gson = GsonBuilder()
        .setLenient()
        .registerTypeAdapter(Boolean::class.java, booleanAdapter)
        .registerTypeAdapter(Boolean::class.javaObjectType, booleanAdapter)
        .create()
}
