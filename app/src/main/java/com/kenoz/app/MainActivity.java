package com.kenoz.app;

import android.app.Activity;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.view.View;
import android.view.Window;
import android.webkit.JavascriptInterface;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Toast;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;

public class MainActivity extends Activity {

    private WebView web;
    private SharedPreferences prefs;
    private boolean backHandled = false;

    public class KenozBridge {
        @JavascriptInterface
        public String readAsset(String path) {
            StringBuilder sb = new StringBuilder();
            InputStream input = null;
            try {
                input = getAssets().open(path);
                BufferedReader reader = new BufferedReader(new InputStreamReader(input, "UTF-8"), 32768);
                char[] buffer = new char[32768];
                int len;
                while ((len = reader.read(buffer)) != -1) {
                    sb.append(buffer, 0, len);
                }
                reader.close();
                return sb.toString();
            } catch (Exception e) {
                return "";
            } finally {
                try { if (input != null) input.close(); } catch (Exception ignored) { }
            }
        }

        @JavascriptInterface
        public String getPref(String key) {
            return prefs.getString(key, "");
        }

        @JavascriptInterface
        public void setPref(String key, String value) {
            prefs.edit().putString(key, value).apply();
        }

        @JavascriptInterface
        public void copy(final String text) {
            runOnUiThread(new Runnable() {
                @Override public void run() {
                    ClipboardManager cm = (ClipboardManager) getSystemService(Context.CLIPBOARD_SERVICE);
                    if (cm != null) {
                        cm.setPrimaryClip(ClipData.newPlainText("كنوز", text));
                        Toast.makeText(MainActivity.this, "تم نسخ النص", Toast.LENGTH_SHORT).show();
                    }
                }
            });
        }

        @JavascriptInterface
        public void share(final String text, final String subject) {
            runOnUiThread(new Runnable() {
                @Override public void run() {
                    Intent send = new Intent(Intent.ACTION_SEND);
                    send.setType("text/plain");
                    send.putExtra(Intent.EXTRA_SUBJECT, subject);
                    send.putExtra(Intent.EXTRA_TEXT, text);
                    startActivity(Intent.createChooser(send, "مشاركة"));
                }
            });
        }

        @JavascriptInterface
        public String versionName() {
            try {
                return getPackageManager().getPackageInfo(getPackageName(), 0).versionName;
            } catch (PackageManager.NameNotFoundException e) {
                return "1.0.0";
            }
        }

        @JavascriptInterface
        public void setTheme(final boolean dark) {
            runOnUiThread(new Runnable() {
                @Override public void run() {
                    int navColor = dark ? Color.rgb(11, 20, 32) : Color.rgb(15, 43, 70);
                    getWindow().setNavigationBarColor(navColor);
                    getWindow().setStatusBarColor(Color.rgb(15, 43, 70));
                }
            });
        }

        @JavascriptInterface
        public void toast(final String message) {
            runOnUiThread(new Runnable() {
                @Override public void run() {
                    Toast.makeText(MainActivity.this, message, Toast.LENGTH_SHORT).show();
                }
            });
        }
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        prefs = getSharedPreferences("kenoz", MODE_PRIVATE);

        Window window = getWindow();
        window.setStatusBarColor(Color.rgb(15, 43, 70));
        window.setNavigationBarColor(Color.rgb(15, 43, 70));
        window.setBackgroundDrawableResource(R.color.kenoz_navy);

        web = new WebView(this);
        web.setBackgroundColor(Color.rgb(15, 43, 70));
        WebSettings settings = web.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setAllowFileAccess(true);
        try { settings.setAllowFileAccessFromFileURLs(true); } catch (Exception ignored) { }
        settings.setCacheMode(WebSettings.LOAD_NO_CACHE);
        settings.setLoadWithOverviewMode(true);
        settings.setUseWideViewPort(true);
        settings.setTextZoom(100);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.LOLLIPOP) {
            settings.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        }

        web.addJavascriptInterface(new KenozBridge(), "KenozAndroid");
        web.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                if (url != null && (url.startsWith("http://") || url.startsWith("https://"))) {
                    try {
                        startActivity(new Intent(Intent.ACTION_VIEW, android.net.Uri.parse(url)));
                    } catch (Exception ignored) { }
                    return true;
                }
                return false;
            }
        });
        web.setWebChromeClient(new WebChromeClient());

        setContentView(web);
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.KITKAT) {
            WebView.setWebContentsDebuggingEnabled(false);
        }
        web.loadUrl("file:///android_asset/index.html");
    }

    @Override
    public void onBackPressed() {
        if (web == null) {
            super.onBackPressed();
            return;
        }
        if (backHandled) {
            super.onBackPressed();
            return;
        }
        backHandled = true;
        web.evaluateJavascript(
                "(function(){try{return !!(window.kenozBack && window.kenozBack());}catch(e){return false;}})()",
                new ValueCallback<String>() {
                    @Override
                    public void onReceiveValue(String value) {
                        if (!"true".equals(value)) {
                            finish();
                        }
                        backHandled = false;
                    }
                });
    }

    @Override
    protected void onDestroy() {
        if (web != null) {
            web.removeJavascriptInterface("KenozAndroid");
            web.destroy();
            web = null;
        }
        super.onDestroy();
    }
}
