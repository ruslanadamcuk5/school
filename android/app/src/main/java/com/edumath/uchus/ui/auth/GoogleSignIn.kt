package com.edumath.uchus.ui.auth

import android.content.Context
import android.content.MutableContextWrapper
import android.util.Base64
import androidx.credentials.CredentialManager
import androidx.credentials.CustomCredential
import androidx.credentials.GetCredentialRequest
import androidx.credentials.GetCredentialResponse
import androidx.credentials.exceptions.GetCredentialCancellationException
import androidx.credentials.exceptions.GetCredentialException
import androidx.credentials.exceptions.GetCredentialProviderConfigurationException
import androidx.credentials.exceptions.NoCredentialException
import com.edumath.uchus.BuildConfig
import com.google.android.libraries.identity.googleid.GetGoogleIdOption
import com.google.android.libraries.identity.googleid.GetSignInWithGoogleOption
import com.google.android.libraries.identity.googleid.GoogleIdTokenCredential
import com.google.android.libraries.identity.googleid.GoogleIdTokenParsingException
import java.security.MessageDigest
import java.security.SecureRandom

/** Понятная пользователю ошибка входа через Google. */
class GoogleSignInException(override val message: String) : Exception(message)

/**
 * Вход через Google средствами Credential Manager.
 *
 * Наружу отдаём ID token и «сырой» nonce: сервер сам проверит подпись,
 * аудиторию и nonce. Google получает SHA-256 от nonce (так делают Firebase и
 * Supabase), а сервер принимает и сырое значение, и его хеш — поэтому вход
 * не сломается, если Google начнёт возвращать nonce без изменений.
 *
 * Порядок попыток повторяет рекомендации Google:
 * 1. аккаунты, которыми уже входили в приложение;
 * 2. любой аккаунт на устройстве;
 * 3. кнопка «Войти через Google» — она умеет добавлять новый аккаунт,
 *    когда на устройстве его нет или он требует повторного входа.
 */
object GoogleSignIn {

    data class Result(val idToken: String, val nonce: String)

    suspend fun signIn(context: Context): Result {
        val clientId = BuildConfig.GOOGLE_CLIENT_ID.trim()
        if (clientId.isEmpty()) {
            throw GoogleSignInException("Вход через Google не настроен в этой сборке приложения")
        }

        val rawNonce = randomNonce()
        val googleNonce = sha256Hex(rawNonce)
        val credentialManager = CredentialManager.create(context)
        val requestContext = MutableContextWrapper(context)

        val requests = listOf(
            idTokenRequest(clientId, googleNonce, authorizedOnly = true),
            idTokenRequest(clientId, googleNonce, authorizedOnly = false),
            buttonRequest(clientId, googleNonce),
        )

        var lastNoCredential: NoCredentialException? = null
        for (request in requests) {
            val response = try {
                credentialManager.getCredential(
                    context = requestContext,
                    request = request,
                )
            } catch (e: GetCredentialCancellationException) {
                val detail = e.message?.trim().orEmpty()
                throw GoogleSignInException(
                    if (detail.isEmpty()) "Вход через Google отменён"
                    else "Вход через Google отменён ($detail)"
                )
            } catch (e: NoCredentialException) {
                // Нет подходящего аккаунта — пробуем следующую стратегию.
                lastNoCredential = e
                continue
            } catch (e: GetCredentialProviderConfigurationException) {
                throw GoogleSignInException(
                    "На устройстве нет сервисов Google Play — вход через Google недоступен. " +
                        "Войдите по логину и паролю."
                )
            } catch (e: GetCredentialException) {
                throw GoogleSignInException(describeFailure(e))
            }
            return parseResponse(response, rawNonce)
        }

        val type = lastNoCredential?.type ?: "NoCredentialException"
        throw GoogleSignInException(
            "Не удалось войти через Google: на устройстве не найден аккаунт, " +
                "и окно добавления аккаунта не открылось. Добавьте аккаунт Google " +
                "в настройках телефона или войдите по логину и паролю. ($type)"
        )
    }

    private fun idTokenRequest(
        clientId: String,
        nonce: String,
        authorizedOnly: Boolean,
    ): GetCredentialRequest {
        val option = GetGoogleIdOption.Builder()
            // false — показываем все аккаунты на устройстве, а не только те,
            // которыми уже входили в приложение: иначе новый пользователь
            // не увидит свою почту.
            .setFilterByAuthorizedAccounts(authorizedOnly)
            .setServerClientId(clientId)
            .setNonce(nonce)
            .setAutoSelectEnabled(false)
            .build()
        return GetCredentialRequest.Builder()
            .addCredentialOption(option)
            .build()
    }

    private fun buttonRequest(clientId: String, nonce: String): GetCredentialRequest {
        val option = GetSignInWithGoogleOption.Builder(clientId)
            .setNonce(nonce)
            .build()
        return GetCredentialRequest.Builder()
            .addCredentialOption(option)
            .build()
    }

    private fun parseResponse(response: GetCredentialResponse, rawNonce: String): Result {
        val credential = response.credential
        if (credential is CustomCredential &&
            credential.type == GoogleIdTokenCredential.TYPE_GOOGLE_ID_TOKEN_CREDENTIAL
        ) {
            val googleCredential = try {
                GoogleIdTokenCredential.createFrom(credential.data)
            } catch (e: GoogleIdTokenParsingException) {
                throw GoogleSignInException("Не удалось прочитать ответ Google. Обновите приложение.")
            }
            val idToken = googleCredential.idToken
            if (idToken.isBlank()) {
                throw GoogleSignInException("Google вернул пустой токен. Попробуйте ещё раз.")
            }
            return Result(idToken = idToken, nonce = rawNonce)
        }
        throw GoogleSignInException("Google вернул неожиданный тип учётных данных")
    }

    private fun describeFailure(e: GetCredentialException): String {
        val base = when (e.type) {
            "androidx.credentials.TYPE_GET_CREDENTIAL_PROVIDER_CONFIGURATION_EXCEPTION" ->
                "На устройстве нет сервисов Google Play — вход через Google недоступен"
            else -> "Google не разрешил вход"
        }
        val detail = e.message?.trim()?.takeIf { it.isNotEmpty() }
        return if (detail == null) {
            "$base (${e.type}). Проверьте, что в телефоне есть Play Маркет и аккаунт Google."
        } else {
            "$base (${e.type}): $detail"
        }
    }

    private fun randomNonce(): String {
        val bytes = ByteArray(32)
        SecureRandom().nextBytes(bytes)
        return Base64.encodeToString(
            bytes,
            Base64.NO_WRAP or Base64.URL_SAFE or Base64.NO_PADDING,
        )
    }

    private fun sha256Hex(value: String): String {
        val digest = MessageDigest.getInstance("SHA-256").digest(value.toByteArray())
        return digest.joinToString("") { "%02x".format(it) }
    }
}
