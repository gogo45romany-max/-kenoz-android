package com.kenoz.app;

import android.app.Activity;
import android.os.Bundle;
import android.webkit.JavascriptInterface;
import android.webkit.WebChromeClient;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.graphics.Color;
import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;

public class MainActivity extends Activity {
    private class KenozBridge {
        @JavascriptInterface
        public String loadBibleData() {
            StringBuilder result = new StringBuilder();
            try {
                InputStream input = getAssets().open("bible-data.json");
                BufferedReader reader = new BufferedReader(new InputStreamReader(input, "UTF-8"));
                String line;
                while ((line = reader.readLine()) != null) result.append(line);
                reader.close();
                input.close();
                return result.toString();
            } catch (Exception e) {
                return "";
            }
        }
    }

    @Override public void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().setStatusBarColor(Color.rgb(18,48,68));
        getWindow().setNavigationBarColor(Color.rgb(18,48,68));
        WebView web = new WebView(this);
        web.setBackgroundColor(Color.rgb(248,247,242));
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setDomStorageEnabled(true);
        web.getSettings().setAllowFileAccess(true);
        web.addJavascriptInterface(new KenozBridge(), "KenozAndroid");
        web.setWebViewClient(new WebViewClient());
        web.setWebChromeClient(new WebChromeClient());
        setContentView(web);
        web.loadUrl("file:///android_asset/index.html");
    }
}