package com.edumath.uchus

import android.app.Application
import com.edumath.uchus.core.AppContainer

class UchusApp : Application() {

    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}
