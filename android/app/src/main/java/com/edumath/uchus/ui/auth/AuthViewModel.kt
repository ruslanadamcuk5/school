package com.edumath.uchus.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.ApiException
import com.edumath.uchus.data.api.ApiJson
import com.edumath.uchus.data.api.CreateLearnerRequest
import com.edumath.uchus.data.api.GoogleFinishRequest
import com.edumath.uchus.data.api.GoogleLoginRequest
import com.edumath.uchus.data.api.LearnerDto
import com.edumath.uchus.data.api.LoginRequest
import com.edumath.uchus.data.api.SessionDto
import com.edumath.uchus.data.api.apiCall
import com.edumath.uchus.data.session.SessionStore
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class AuthViewModel(private val container: AppContainer) : ViewModel() {

    data class UiState(
        val busy: Boolean = false,
        val error: String? = null,
        val server: String = "",
        val learners: List<LearnerDto> = emptyList(),
        val learnersLoaded: Boolean = false,
        /** Новый Google-аккаунт: предлагаем выбрать роль и логин. */
        val googlePrompt: GooglePrompt? = null,
    )

    /** Данные из ID token для экрана завершения регистрации. */
    data class GooglePrompt(
        val signupToken: String,
        val email: String,
        val firstName: String,
        val lastName: String,
        val suggestedLogin: String,
    )

    private val _state = MutableStateFlow(UiState(server = container.session.baseUrl))
    val state = _state.asStateFlow()

    fun setServer(value: String) = _state.update { it.copy(server = value) }

    fun clearError() = _state.update { it.copy(error = null) }

    fun refreshLearners() {
        val server = _state.value.server
        insecureServerError(server)?.let { message ->
            _state.update { it.copy(learnersLoaded = true, error = message) }
            return
        }
        container.session.primeBaseUrl(server)
        viewModelScope.launch {
            runCatching { apiCall { container.api.learners() } }
                .onSuccess { response ->
                    _state.update {
                        it.copy(
                            learners = response.learners,
                            learnersLoaded = true,
                            error = null,
                        )
                    }
                }
                .onFailure { error ->
                    _state.update { it.copy(learnersLoaded = true, error = error.toText()) }
                }
        }
    }

    fun login(login: String, password: String) {
        if (login.isBlank() || password.isBlank()) {
            _state.update { it.copy(error = "Введите логин и пароль") }
            return
        }
        launchAuth { container.api.login(LoginRequest(login.trim(), password)) }
    }

    /** Показать ошибку, полученную вне ViewModel (например, от Credential Manager). */
    fun showError(message: String) = _state.update { it.copy(busy = false, error = message) }

    /** Вход по ID token от Google Credential Manager. */
    fun googleLogin(idToken: String, nonce: String) {
        val server = _state.value.server
        insecureServerError(server)?.let { message ->
            _state.update { it.copy(error = message) }
            return
        }
        container.session.primeBaseUrl(server)
        _state.update { it.copy(busy = true, error = null) }
        viewModelScope.launch {
            runCatching {
                apiCall { container.api.googleLogin(GoogleLoginRequest(idToken, nonce)) }
            }
                .onSuccess { response ->
                    val signupToken = response.signupToken
                    if (response.needsSignup && !signupToken.isNullOrBlank()) {
                        _state.update {
                            it.copy(
                                busy = false,
                                error = null,
                                googlePrompt = GooglePrompt(
                                    signupToken = signupToken,
                                    email = response.email.orEmpty(),
                                    firstName = response.firstName.orEmpty(),
                                    lastName = response.lastName.orEmpty(),
                                    suggestedLogin = response.suggestedLogin.orEmpty(),
                                ),
                            )
                        }
                    } else {
                        persist(server, response.toSession())
                    }
                }
                .onFailure { error ->
                    _state.update { it.copy(busy = false, error = error.toText()) }
                }
        }
    }

    /** Завершить регистрацию нового Google-пользователя. */
    fun googleFinishSignup(
        role: String,
        login: String,
        firstName: String,
        lastName: String,
        childCode: String,
    ) {
        val prompt = _state.value.googlePrompt
        if (prompt == null) {
            _state.update { it.copy(error = "Регистрация истекла, войдите через Google ещё раз") }
            return
        }
        if (firstName.isBlank()) {
            _state.update { it.copy(error = "Введите имя") }
            return
        }
        if (login.trim().length < 3) {
            _state.update { it.copy(error = "Логин должен содержать минимум 3 символа") }
            return
        }
        launchAuth {
            container.api.googleFinishSignup(
                GoogleFinishRequest(
                    signupToken = prompt.signupToken,
                    role = role,
                    login = login.trim().lowercase(),
                    firstName = firstName.trim(),
                    lastName = lastName.trim().ifBlank { null },
                    avatar = "🦊",
                    childCode = childCode.trim().uppercase().ifBlank { null },
                )
            )
        }
    }

    fun cancelGoogleSignup() = _state.update { it.copy(googlePrompt = null) }

    fun loginLearner(learner: LearnerDto, pin: String? = null) {
        if (learner.hasPin && pin.isNullOrBlank()) {
            _state.update { it.copy(error = "Введите PIN-код профиля") }
            return
        }
        launchAuth {
            container.api.loginLearner(
                learner.id,
                com.edumath.uchus.data.api.LearnerLoginRequest(pin?.takeIf { it.isNotBlank() }),
            )
        }
    }

    fun createLearner(name: String, grade: Int, pin: String) {
        if (name.isBlank()) {
            _state.update { it.copy(error = "Введите имя ребёнка") }
            return
        }
        if (pin.isNotBlank() && (pin.length != 4 || pin.any { !it.isDigit() })) {
            _state.update { it.copy(error = "PIN должен состоять из 4 цифр") }
            return
        }
        launchAuth {
            container.api.createLearner(
                CreateLearnerRequest(
                    name = name.trim(),
                    avatar = "🦊",
                    grade = grade,
                    pin = pin.ifBlank { null },
                )
            )
        }
    }

    private fun launchAuth(block: suspend () -> SessionDto) {
        val server = _state.value.server
        insecureServerError(server)?.let { message ->
            _state.update { it.copy(error = message) }
            return
        }
        container.session.primeBaseUrl(server)
        _state.update { it.copy(busy = true, error = null) }
        viewModelScope.launch {
            runCatching { apiCall { block() } }
                .onSuccess { persist(server, it) }
                .onFailure { error ->
                    _state.update { it.copy(busy = false, error = error.toText()) }
                }
        }
    }

    private fun insecureServerError(server: String): String? =
        if (SessionStore.isInsecureRemote(server)) {
            "Сервер должен работать по HTTPS. HTTP допустим только для localhost."
        } else {
            null
        }

    private suspend fun persist(server: String, session: SessionDto) {
        val token = session.token
        if (token.isNullOrBlank()) {
            _state.update { it.copy(busy = false, error = "Сервер не вернул токен") }
            return
        }
        container.session.save(server, token, ApiJson.gson.toJson(session))
        _state.update { it.copy(busy = false, error = null, googlePrompt = null) }
    }

    private fun Throwable.toText(): String = when (this) {
        is ApiException -> when (code) {
            "bad_credentials" -> "Неверный логин или пароль"
            "inactive" -> "Аккаунт отключён. Обратитесь к администратору."
            "bad_grade" -> message
            "google_disabled" -> "Вход через Google не настроен на сервере"
            "google_token_invalid" -> "Google не подтвердил вход. Попробуйте ещё раз."
            "bad_nonce", "signup_expired" -> message
            "login_taken" -> "Такой логин уже занят — выберите другой"
            "bad_role", "bad_name", "bad_login" -> message
            "too_many_attempts" -> message
            else -> message
        }
        else -> message ?: "Неизвестная ошибка"
    }
}
