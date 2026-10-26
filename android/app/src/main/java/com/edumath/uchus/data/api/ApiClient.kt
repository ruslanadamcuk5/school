package com.edumath.uchus.data.api

import com.edumath.uchus.BuildConfig
import com.edumath.uchus.data.session.SessionStore
import java.io.IOException
import java.util.concurrent.TimeUnit
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.Interceptor
import okhttp3.OkHttpClient
import okhttp3.Response
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.HttpException
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory

/** Ошибка API с машинным кодом и понятным текстом. */
class ApiException(
    val code: String,
    override val message: String,
    val status: Int = 0,
) : Exception(message)

/** Выполнить запрос, превратив сетевые ошибки в ApiException. */
suspend fun <T> apiCall(block: suspend () -> T): T {
    try {
        return block()
    } catch (e: HttpException) {
        val raw = runCatching { e.response()?.errorBody()?.string() }.getOrNull()
        val parsed = runCatching { ApiJson.gson.fromJson(raw, ApiErrorDto::class.java) }.getOrNull()
        throw ApiException(
            code = parsed?.error ?: "http_${e.code()}",
            message = parsed?.message ?: "Ошибка сервера (${e.code()})",
            status = e.code(),
        )
    } catch (e: IOException) {
        throw ApiException("network", "Нет связи с сервером. Проверьте адрес и интернет.")
    }
}

private class BaseUrlInterceptor(private val session: SessionStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val base = session.baseUrl.toHttpUrlOrNull() ?: return chain.proceed(chain.request())
        val request = chain.request()
        val newUrl = request.url.newBuilder()
            .scheme(base.scheme)
            .host(base.host)
            .port(base.port)
            .build()
        return chain.proceed(request.newBuilder().url(newUrl).build())
    }
}

private class AuthInterceptor(private val session: SessionStore) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val builder = chain.request().newBuilder()
        val token = session.token
        if (!token.isNullOrBlank()) {
            builder.header("Authorization", "Bearer $token")
        }
        val device = session.deviceId
        if (device.isNotBlank()) {
            builder.header("X-Device-Id", device)
        }
        return chain.proceed(builder.build())
    }
}

object ApiClient {

    private fun httpClient(session: SessionStore): OkHttpClient {
        val logging = HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG) HttpLoggingInterceptor.Level.BASIC
            else HttpLoggingInterceptor.Level.NONE
        }
        return OkHttpClient.Builder()
            .connectTimeout(20, TimeUnit.SECONDS)
            .readTimeout(90, TimeUnit.SECONDS)
            .writeTimeout(90, TimeUnit.SECONDS)
            .addInterceptor(BaseUrlInterceptor(session))
            .addInterceptor(AuthInterceptor(session))
            .addInterceptor(logging)
            .build()
    }

    fun create(session: SessionStore): ApiService {
        return Retrofit.Builder()
            // Реальный адрес подставляется перехватчиком из настроек сессии.
            .baseUrl("https://placeholder.invalid/api/v1/")
            .client(httpClient(session))
            .addConverterFactory(GsonConverterFactory.create(ApiJson.gson))
            .build()
            .create(ApiService::class.java)
    }

    /** Клиент для загрузки картинок (страницы PDF): тот же токен и адрес. */
    fun imageClient(session: SessionStore): OkHttpClient = httpClient(session)
}
