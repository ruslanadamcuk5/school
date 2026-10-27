package com.edumath.uchus

import android.app.Application
import com.edumath.uchus.core.AppContainer
import com.edumath.uchus.data.worker.NotificationWorker

class UchusApp : Application() {

    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
        // Периодический опрос уведомлений (каждые 15 минут).
        NotificationWorker.enqueue(this)
    }
}
