plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
    id("org.jetbrains.kotlin.plugin.compose")
}

android {
    namespace = "com.edumath.uchus"
    compileSdk = 35

    defaultConfig {
        applicationId = "com.edumath.uchus"
        minSdk = 24
        targetSdk = 35
        versionCode = 30
        versionName = "1.9.15"

        vectorDrawables { useSupportLibrary = true }

        // Адрес сервера по умолчанию. Его можно изменить на экране входа
        // или передать при сборке: gradle assembleDebug -PserverUrl=https://…
        val serverUrl = (findProperty("serverUrl") as String?)
            ?.trim()
            ?.takeIf { it.isNotEmpty() }
            ?: "https://virusadk.alwaysdata.net"
        buildConfigField("String", "DEFAULT_SERVER_URL", "\"$serverUrl\"")

        // Web-клиент OAuth из Google Cloud. Именно он передаётся в Credential
        // Manager как serverClientId; ID token приходит с aud = этому клиенту.
        val googleClientId = (findProperty("googleClientId") as String?)
            ?.trim()
            ?.takeIf { it.isNotEmpty() }
            ?: "1012001456335-jjo5s9ptivbsr0j94qvfkpre2q72grvb.apps.googleusercontent.com"
        buildConfigField("String", "GOOGLE_CLIENT_ID", "\"$googleClientId\"")
    }

    signingConfigs {
        // Единый debug-ключ для локальной сборки и GitHub Actions.
        // Нужен, чтобы APK с сайта устанавливался поверх ранее установленного
        // приложения как обновление (одинаковая подпись). Это не ключ для
        // публикации в Google Play — для магазина нужен отдельный release-ключ.
        create("siteDebug") {
            storeFile = rootProject.file("keystore/uchus-debug.keystore")
            storePassword = "android"
            keyAlias = "androiddebugkey"
            keyPassword = "android"
        }
    }

    buildTypes {
        debug {
            signingConfig = signingConfigs.getByName("siteDebug")
        }
        release {
            isMinifyEnabled = false
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
                "proguard-rules.pro"
            )
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    kotlinOptions {
        jvmTarget = "17"
    }

    buildFeatures {
        compose = true
        buildConfig = true
    }

    packaging {
        resources {
            excludes += "/META-INF/{AL2.0,LGPL2.1}"
        }
    }
}

dependencies {
    implementation(platform("androidx.compose:compose-bom:2024.12.01"))

    implementation("androidx.core:core-ktx:1.15.0")
    implementation("androidx.exifinterface:exifinterface:1.3.7")
    implementation("androidx.activity:activity-compose:1.9.3")
    implementation("androidx.lifecycle:lifecycle-runtime-ktx:2.8.7")
    implementation("androidx.lifecycle:lifecycle-viewmodel-compose:2.8.7")
    implementation("androidx.lifecycle:lifecycle-runtime-compose:2.8.7")
    implementation("androidx.navigation:navigation-compose:2.8.5")
    implementation("androidx.datastore:datastore-preferences:1.1.1")
    implementation("androidx.work:work-runtime-ktx:2.9.1")

    implementation("androidx.compose.ui:ui")
    implementation("androidx.compose.ui:ui-tooling-preview")
    implementation("androidx.compose.material3:material3")

    implementation("com.squareup.retrofit2:retrofit:2.11.0")
    implementation("com.squareup.retrofit2:converter-gson:2.11.0")
    implementation("com.squareup.okhttp3:okhttp:4.12.0")
    implementation("com.squareup.okhttp3:logging-interceptor:4.12.0")
    implementation("com.google.code.gson:gson:2.11.0")
    implementation("io.coil-kt:coil-compose:2.7.0")
    implementation("org.jetbrains.kotlinx:kotlinx-coroutines-android:1.9.0")

    // Вход через Google: Credential Manager + Google ID token.
    implementation("androidx.credentials:credentials:1.3.0")
    implementation("androidx.credentials:credentials-play-services-auth:1.3.0")
    implementation("com.google.android.libraries.identity.googleid:googleid:1.1.1")

    // Запасной вход через Google в браузере телефона.
    implementation("androidx.browser:browser:1.8.0")

    debugImplementation("androidx.compose.ui:ui-tooling")
    testImplementation("junit:junit:4.13.2")
}
