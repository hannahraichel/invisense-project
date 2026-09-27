package com.invisense.app.api;

import android.content.Context;
import android.content.SharedPreferences;

import com.invisense.app.BuildConfig;

import okhttp3.OkHttpClient;
import okhttp3.Request;
import okhttp3.logging.HttpLoggingInterceptor;
import retrofit2.Retrofit;
import retrofit2.converter.gson.GsonConverterFactory;

/**
 * Singleton Retrofit client.
 * Base URL defaults to BuildConfig.BASE_URL, but can be overridden dynamically in SharedPreferences.
 * Auth token is injected automatically from SharedPreferences.
 */
public class ApiClient {

    private static final String PREFS_NAME = "invisense_prefs";
    private static final String KEY_TOKEN  = "auth_token";
    private static final String KEY_SERVER_URL = "server_url";

    private static Retrofit retrofit;

    public static String getServerUrl(Context context) {
        SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);
        return prefs.getString(KEY_SERVER_URL, BuildConfig.BASE_URL);
    }

    public static void setServerUrl(Context context, String url) {
        if (url == null) return;
        url = url.trim();
        while (url.endsWith("/")) {
            url = url.substring(0, url.length() - 1);
        }
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit().putString(KEY_SERVER_URL, url).apply();
        reset();
    }

    public static InviSenseApi getApi(Context context) {
        if (retrofit == null) {
            SharedPreferences prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE);

            HttpLoggingInterceptor logging = new HttpLoggingInterceptor();
            logging.setLevel(HttpLoggingInterceptor.Level.BODY);

            OkHttpClient client = new OkHttpClient.Builder()
                    .addInterceptor(chain -> {
                        String token = prefs.getString(KEY_TOKEN, null);
                        Request.Builder reqBuilder = chain.request().newBuilder()
                                .addHeader("Content-Type", "application/json")
                                .addHeader("Accept", "application/json")
                                .addHeader("ngrok-skip-browser-warning", "true");
                        if (token != null && !token.isEmpty()) {
                            reqBuilder.addHeader("Authorization", "Token " + token);
                        }
                        return chain.proceed(reqBuilder.build());
                    })
                    .addInterceptor(logging)
                    .build();

            String baseUrl = getServerUrl(context);
            if (!baseUrl.endsWith("/")) {
                baseUrl += "/";
            }

            retrofit = new Retrofit.Builder()
                    .baseUrl(baseUrl)
                    .client(client)
                    .addConverterFactory(GsonConverterFactory.create())
                    .build();
        }
        return retrofit.create(InviSenseApi.class);
    }

    /** Call this after login or server URL change to rebuild the client. */
    public static void reset() {
        retrofit = null;
    }

    public static void saveToken(Context context, String token) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit().putString(KEY_TOKEN, token).apply();
    }

    public static String getToken(Context context) {
        return context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .getString(KEY_TOKEN, null);
    }

    public static void clearToken(Context context) {
        context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
                .edit().remove(KEY_TOKEN).apply();
        reset();
    }
}
