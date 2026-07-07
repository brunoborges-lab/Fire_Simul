[app]

# (str) Title of your application
title = Calculadora de Incendios

# (str) Package name
package.name = calculadoraincendios

# (str) Package domain (needed for android packaging)
package.domain = org.bombeiros.pt

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include (let empty to include all the files)
source.include_exts = py,png,jpg,kv,atlas

# (str) Application versioning (method 1)
version = 1.0.0

# (list) Application requirements
# NOTA: Fixamos as versões exatas que funcionam sem quebrar no ecossistema Android em 2026
requirements = python3,kivy==2.3.0,cython<3.0.0

# (str) Supported orientations (landscape, portrait or all)
orientation = portrait

# -----------------------------------------------------------------------------
# Android specific configurations
# -----------------------------------------------------------------------------

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 1

# (list) Permissions
# Adicionada permissão de INTERNET para futuras consultas automáticas à API do IPMA
android.permissions = INTERNET

# (int) Target Android API, should be as high as possible.
android.api = 34

# (int) Minimum API your APK will support. (Android 8.0+)
android.minapi = 26

# (int) Android SDK version to use
android.sdk = 34

# (str) Android NDK version to use (Deixar em branco para o Buildozer escolher a melhor)
android.ndk = 25b

# (bool) If True, then skip trying to update the Android sdk leaves it down to the user
android.skip_update = False

# (bool) If True, then automatically accept SDK license
# CRUCIAL para o GitHub Actions correr sem intervenção humana
android.accept_sdk_license = True

# (list) Android architectures to build for.
# IMPORTANTE: Apenas arm64-v8a. Isto poupa metade do tempo de compilação e evita erros de RAM.
android.archs = arm64-v8a

# (str) The Android bounty king bootstrap to use (sdl2, webview, etc.)
p4a.bootstrap = sdl2

# -----------------------------------------------------------------------------
# Buildozer configurations
# -----------------------------------------------------------------------------

[buildozer]

# (int) Log level (0 = error only, 1 = info, 2 = debug (with command output))
log_level = 2

# (int) Display warning if buildozer is run as root (0 = False, 1 = True)
warn_on_root = 1
