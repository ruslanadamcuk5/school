package com.edumath.uchus.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.api.ApiException
import com.edumath.uchus.data.api.CreateLearnerRequest
import com.edumath.uchus.data.api.LearnerDto
import com.edumath.uchus.data.api.LoginRequest
import com.edumath.uchus.data.api.SessionDto
import com.edumath.uchus.data.api.apiCall
import com.google.gson.Gson
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
    )

    private val _state = MutableStateFlow(UiState(server = container.session.baseUrl))
    val state = _state.asStateFlow()

    private val gson = Gson()

    fun setServer(value: String) = _state.update { it.copy(server = value) }

    fun clearError() = _state.update { it.copy(error = null) }

    fun refreshLearners() {
        val server = _state.value.server
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

    private suspend fun persist(server: String, session: SessionDto) {
        val token = session.token
        if (token.isNullOrBlank()) {
            _state.update { it.copy(busy = false, error = "Сервер не вернул токен") }
            return
        }
        container.session.save(server, token, gson.toJson(session))
        _state.update { it.copy(busy = false, error = null) }
    }

    private fun Throwable.toText(): String = when (this) {
        is ApiException -> when (code) {
            "bad_credentials" -> "Неверный логин или пароль"
            "inactive" -> "Аккаунт отключён. Обратитесь к администратору."
            "bad_grade" -> message
            else -> message
        }
        else -> message ?: "Неизвестная ошибка"
    }
}
