plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}
android {
    namespace="com.datbeo.routermonitor"
    compileSdk=35

    defaultConfig {
        applicationId="com.datbeo.routermonitor"
        minSdk=26
        targetSdk=35
        versionCode=6
        versionName="2.1.1"
    }

    compileOptions {
        sourceCompatibility=JavaVersion.VERSION_17
        targetCompatibility=JavaVersion.VERSION_17
    }
}

kotlin {
    jvmToolchain(17)
    compilerOptions {
        jvmTarget.set(org.jetbrains.kotlin.gradle.dsl.JvmTarget.JVM_17)
    }
}
