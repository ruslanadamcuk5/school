package com.edumath.uchus.core

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import com.edumath.uchus.ui.auth.AuthViewModel

/** Фабрика ViewModel: отдаёт зависимости из AppContainer. */
fun appViewModelFactory(container: AppContainer): ViewModelProvider.Factory =
    object : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T = when {
            modelClass.isAssignableFrom(AuthViewModel::class.java) ->
                AuthViewModel(container) as T

            else -> throw IllegalArgumentException("Неизвестная ViewModel: ${modelClass.name}")
        }
    }
