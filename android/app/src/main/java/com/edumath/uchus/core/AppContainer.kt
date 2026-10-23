package com.edumath.uchus.core

import android.content.Context
import coil.ImageLoader
import com.edumath.uchus.data.api.ApiClient
import com.edumath.uchus.data.api.ApiService
import com.edumath.uchus.data.cache.JsonCache
import com.edumath.uchus.data.session.SessionStore

/** Простой контейнер зависимостей (без DI-фреймворка). */
class AppContainer(context: Context) {

    private val appContext = context.applicationContext

    val session = SessionStore(appContext)
    val cache = JsonCache(appContext)
    val api: ApiService = ApiClient.create(session)

    /** Загрузчик картинок с токеном и адресом сервера (страницы PDF). */
    val imageLoader: ImageLoader by lazy {
        ImageLoader.Builder(appContext)
            .okHttpClient { ApiClient.imageClient(session) }
            .crossfade(true)
            .build()
    }
}
