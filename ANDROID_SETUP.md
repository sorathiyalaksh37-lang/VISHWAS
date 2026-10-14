# Android App Setup - VISHWAS

Quick setup guide.

## Important: RetrofitClient.kt

File contains DEV_TOKEN placeholder:

private const val DEV_TOKEN = "REPLACE_WITH_YOUR_TOKEN"

Replace locally with your own token from /api/v1/auth/login.

## Get Token

Backend must be running.
$body = '{"email":"m1@vishwas.dev","password":"Test@1234"}'
Invoke-RestMethod -Uri "http://localhost:8000/api/v1/auth/login" -Method Post -ContentType "application/json" -Body $body

## Build

cd android-app
.\gradlew.bat assembleDebug

See android-app/README.md for details.
