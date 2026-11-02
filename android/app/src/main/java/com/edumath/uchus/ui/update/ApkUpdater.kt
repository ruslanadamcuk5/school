package com.edumath.uchus.ui.update

import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageInfo
import android.content.pm.PackageInstaller
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.SystemClock
import android.provider.Settings
import com.edumath.uchus.data.api.AppVersionDto
import java.io.File
import java.security.MessageDigest
import java.util.concurrent.TimeUnit
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request

/** Прогресс скачивания APK для строки загрузки в приложении. */
data class ApkDownloadProgress(
    val downloaded: Long,
    val total: Long,
) {
    val fraction: Float
        get() = if (total > 0) {
            (downloaded.toFloat() / total.toFloat()).coerceIn(0f, 1f)
        } else {
            0f
        }
}

/**
 * Скачивание и установка обновления без браузера и папки «Загрузки».
 *
 * APK кладётся во внутренний кэш приложения, проверяется по SHA-256 и
 * подписи установленной версии, после чего передаётся системному
 * PackageInstaller. Android всё равно может показать одно системное
 * подтверждение установки — обойти его обычное приложение не может.
 */
object ApkUpdater {

    private const val UPDATE_DIR = "updates"
    private const val BUFFER = 64 * 1024

    fun canInstallPackages(context: Context): Boolean {
        return Build.VERSION.SDK_INT < Build.VERSION_CODES.O ||
            context.packageManager.canRequestPackageInstalls()
    }

    fun openInstallPermissionSettings(context: Context) {
        val intent = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            Intent(
                Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                Uri.parse("package:${context.packageName}"),
            )
        } else {
            Intent(Settings.ACTION_SECURITY_SETTINGS)
        }
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        runCatching { context.startActivity(intent) }
    }

    suspend fun download(
        context: Context,
        info: AppVersionDto,
        onProgress: (ApkDownloadProgress) -> Unit,
    ): File = withContext(Dispatchers.IO) {
        val url = info.downloadUrl?.takeIf { it.isNotBlank() }
            ?: error("Сервер не передал ссылку на обновление")

        val dir = File(context.cacheDir, UPDATE_DIR).apply { mkdirs() }
        dir.listFiles()?.forEach { it.delete() }
        val target = File(dir, "uchus-${info.versionCode}.apk")
        val part = File(dir, "uchus-${info.versionCode}.apk.part")

        val client = OkHttpClient.Builder()
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(60, TimeUnit.SECONDS)
            .writeTimeout(60, TimeUnit.SECONDS)
            .followRedirects(true)
            .build()
        val request = Request.Builder()
            .url(url)
            .header("Accept", "application/vnd.android.package-archive")
            .build()

        try {
            client.newCall(request).execute().use { response ->
                if (!response.isSuccessful) {
                    error("Сервер вернул ошибку ${response.code}")
                }
                val body = response.body ?: error("Сервер прислал пустой файл")
                val total = if (info.size > 0) info.size else body.contentLength()
                var downloaded = 0L
                var lastReport = 0L
                val digest = MessageDigest.getInstance("SHA-256")

                part.outputStream().use { output ->
                    body.byteStream().use { input ->
                        val buffer = ByteArray(BUFFER)
                        while (true) {
                            currentCoroutineContext().ensureActive()
                            val read = input.read(buffer)
                            if (read < 0) break
                            output.write(buffer, 0, read)
                            digest.update(buffer, 0, read)
                            downloaded += read
                            val now = SystemClock.elapsedRealtime()
                            if (now - lastReport >= 100L || downloaded == total) {
                                lastReport = now
                                onProgress(ApkDownloadProgress(downloaded, total))
                            }
                        }
                    }
                }

                if (total > 0 && downloaded != total) {
                    error("Файл скачан не полностью. Попробуйте ещё раз.")
                }

                val actual = digest.digest().toHex()
                val expected = info.sha256?.trim()?.lowercase().orEmpty()
                if (expected.isNotEmpty() && actual != expected) {
                    error("Контрольная сумма не совпала. Обновление отменено.")
                }
            }
        } catch (failure: Throwable) {
            part.delete()
            throw failure
        }

        if (target.exists()) target.delete()
        if (!part.renameTo(target)) {
            part.copyTo(target, overwrite = true)
            part.delete()
        }
        onProgress(ApkDownloadProgress(target.length(), target.length()))
        target
    }

    /**
     * Проверяет, что APK подписан тем же ключом, что и установленное
     * приложение, и что внутри тот же package name.
     */
    suspend fun isTrustedUpdate(context: Context, apk: File): Boolean =
        withContext(Dispatchers.IO) {
            verifyTrusted(context, apk)
        }

    private fun verifyTrusted(context: Context, apk: File): Boolean {
        val manager = context.packageManager
        val flags = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            PackageManager.GET_SIGNING_CERTIFICATES
        } else {
            @Suppress("DEPRECATION")
            PackageManager.GET_SIGNATURES
        }
        val archive = manager.getPackageArchiveInfo(apk.absolutePath, flags)
            ?: return false
        if (archive.packageName != context.packageName) return false

        val installed = runCatching {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                manager.getPackageInfo(
                    context.packageName,
                    PackageManager.PackageInfoFlags.of(flags.toLong()),
                )
            } else {
                @Suppress("DEPRECATION")
                manager.getPackageInfo(context.packageName, flags)
            }
        }.getOrNull() ?: return false

        val newSignatures = signatureHashes(archive)
        val oldSignatures = signatureHashes(installed)
        return newSignatures.isNotEmpty() && newSignatures == oldSignatures
    }

    /** Передать APK системному установщику и сразу открыть его экран. */
    suspend fun install(context: Context, apk: File) = withContext(Dispatchers.IO) {
        val installer = context.packageManager.packageInstaller
        val params = PackageInstaller.SessionParams(
            PackageInstaller.SessionParams.MODE_FULL_INSTALL
        ).apply {
            setAppPackageName(context.packageName)
            setSize(apk.length())
        }

        val sessionId = installer.createSession(params)
        try {
            installer.openSession(sessionId).use { session ->
                apk.inputStream().use { input ->
                    session.openWrite("base.apk", 0, apk.length()).use { output ->
                        input.copyTo(output)
                        session.fsync(output)
                    }
                }
                val statusIntent = Intent(
                    context,
                    UpdateInstallReceiver::class.java,
                ).apply {
                    action = UpdateInstallReceiver.ACTION_INSTALL_STATUS
                    setPackage(context.packageName)
                }
                val pendingFlags =
                    PendingIntent.FLAG_UPDATE_CURRENT or
                        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                            PendingIntent.FLAG_MUTABLE
                        } else {
                            0
                        }
                val pending = PendingIntent.getBroadcast(
                    context,
                    sessionId,
                    statusIntent,
                    pendingFlags,
                )
                session.commit(pending.intentSender)
            }
        } catch (failure: Throwable) {
            runCatching { installer.abandonSession(sessionId) }
            throw failure
        }
        // PackageInstaller уже скопировал APK в свою сессию.
        apk.delete()
        Unit
    }

    private fun signatureHashes(info: PackageInfo): Set<String> {
        val signatures = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            info.signingInfo?.apkContentsSigners
        } else {
            @Suppress("DEPRECATION")
            info.signatures
        }
        return signatures
            ?.map { sha256(it.toByteArray()) }
            ?.toSet()
            .orEmpty()
    }

    private fun sha256(bytes: ByteArray): String {
        return MessageDigest.getInstance("SHA-256").digest(bytes).toHex()
    }

    private fun ByteArray.toHex(): String = joinToString("") {
        (it.toInt() and 0xff).toString(16).padStart(2, '0')
    }
}

/** Небольшое хранилище состояния обновления между запусками. */
object UpdateStateStore {

    private const val PREFS = "app_update_state"
    private const val KEY_PENDING_CODE = "pending_version_code"
    private const val KEY_PENDING_NAME = "pending_version_name"
    private const val KEY_ERROR = "last_error"

    private fun prefs(context: Context) =
        context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    fun rememberPending(context: Context, info: AppVersionDto) {
        prefs(context).edit()
            .putInt(KEY_PENDING_CODE, info.versionCode)
            .putString(KEY_PENDING_NAME, info.versionName)
            .remove(KEY_ERROR)
            .apply()
    }

    fun pendingCode(context: Context): Int =
        prefs(context).getInt(KEY_PENDING_CODE, 0)

    fun pendingName(context: Context): String? =
        prefs(context).getString(KEY_PENDING_NAME, null)

    fun clearPending(context: Context) {
        prefs(context).edit()
            .remove(KEY_PENDING_CODE)
            .remove(KEY_PENDING_NAME)
            .apply()
    }

    fun setError(context: Context, message: String) {
        prefs(context).edit().putString(KEY_ERROR, message).apply()
    }

    fun error(context: Context): String? =
        prefs(context).getString(KEY_ERROR, null)

    fun clearError(context: Context) {
        prefs(context).edit().remove(KEY_ERROR).apply()
    }
}
