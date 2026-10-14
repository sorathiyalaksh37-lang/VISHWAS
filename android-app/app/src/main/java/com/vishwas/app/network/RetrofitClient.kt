package com.vishwas.app.network

import android.content.Context
import android.content.SharedPreferences
import com.vishwas.app.BuildConfig
import okhttp3.OkHttpClient
import okhttp3.logging.HttpLoggingInterceptor
import okhttp3.Interceptor
import okhttp3.Response
import retrofit2.Retrofit
import retrofit2.converter.gson.GsonConverterFactory
import java.util.concurrent.TimeUnit

/**
 * Manages JWT token storage in SharedPreferences.
 */
object TokenManager {
    private const val PREFS_NAME = "vishwas_prefs"
    private const val KEY_TOKEN  = "auth_token"
    private const val KEY_EMAIL  = "user_email"

    private lateinit var prefs: SharedPreferences

    fun init(context: Context) {
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
    }

    fun saveToken(token: String, email: String = "") {
        prefs.edit().putString(KEY_TOKEN, token).putString(KEY_EMAIL, email).apply()
    }

    fun getToken(): String? = prefs.getString(KEY_TOKEN, null)

    fun getEmail(): String = prefs.getString(KEY_EMAIL, "") ?: ""

    fun isLoggedIn(): Boolean = !getToken().isNullOrBlank()

    fun clear() {
        prefs.edit().remove(KEY_TOKEN).remove(KEY_EMAIL).apply()
    }
}

/**
 * OkHttp interceptor that attaches the JWT Bearer token to every request.
 */
class AuthInterceptor : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = TokenManager.getToken()
        val request = if (!token.isNullOrBlank()) {
            chain.request().newBuilder()
                .addHeader("Authorization", "Bearer $token")
                .build()
        } else {
            chain.request()
        }
        return chain.proceed(request)
    }
}

/**
 * Retrofit client singleton — now includes AuthInterceptor for JWT.
 */
object RetrofitClient {

    private const val CONNECT_TIMEOUT = 30L
    private const val READ_TIMEOUT    = 60L
    private const val WRITE_TIMEOUT   = 60L

    private val loggingInterceptor = HttpLoggingInterceptor().apply {
        level = if (BuildConfig.DEBUG) {
            HttpLoggingInterceptor.Level.BODY
        } else {
            HttpLoggingInterceptor.Level.NONE
        }
    }

    private val okHttpClient = OkHttpClient.Builder()
        .addInterceptor(AuthInterceptor())          // ← JWT auth header on every request
        .addInterceptor(loggingInterceptor)
        .connectTimeout(CONNECT_TIMEOUT, TimeUnit.SECONDS)
        .readTimeout(READ_TIMEOUT, TimeUnit.SECONDS)
        .writeTimeout(WRITE_TIMEOUT, TimeUnit.SECONDS)
        .build()

    private val retrofit = Retrofit.Builder()
        .baseUrl(BuildConfig.API_BASE_URL)
        .client(okHttpClient)
        .addConverterFactory(GsonConverterFactory.create())
        .build()

    val apiService: VishwasApiService = retrofit.create(VishwasApiService::class.java)
}
