.class public Lcom/kenoz/app/MainActivity;
.super Landroid/app/Activity;
.source "MainActivity.java"

# Hand-maintained mirror of app/src/main/java/com/kenoz/app/MainActivity.java
# (used only by tools/build_apk_local.sh, which has no Android SDK available).

.field private backHandled:Z

.field private prefs:Landroid/content/SharedPreferences;

.field private web:Landroid/webkit/WebView;

.method public constructor <init>()V
    .locals 0
    invoke-direct {p0}, Landroid/app/Activity;-><init>()V
    return-void
.end method

.method protected onCreate(Landroid/os/Bundle;)V
    .locals 7
    invoke-super {p0, p1}, Landroid/app/Activity;->onCreate(Landroid/os/Bundle;)V

    # prefs = getSharedPreferences("kenoz", MODE_PRIVATE)
    const-string v0, "kenoz"
    const/4 v1, 0x0
    invoke-virtual {p0, v0, v1}, Landroid/app/Activity;->getSharedPreferences(Ljava/lang/String;I)Landroid/content/SharedPreferences;
    move-result-object v0
    iput-object v0, p0, Lcom/kenoz/app/MainActivity;->prefs:Landroid/content/SharedPreferences;

    # window = getWindow(); status/navigation bar -> navy
    invoke-virtual {p0}, Landroid/app/Activity;->getWindow()Landroid/view/Window;
    move-result-object v0
    const v2, 0xff0f2b46
    invoke-virtual {v0, v2}, Landroid/view/Window;->setStatusBarColor(I)V
    invoke-virtual {v0, v2}, Landroid/view/Window;->setNavigationBarColor(I)V

    # web = new WebView(this)
    new-instance v0, Landroid/webkit/WebView;
    invoke-direct {v0, p0}, Landroid/webkit/WebView;-><init>(Landroid/content/Context;)V
    iput-object v0, p0, Lcom/kenoz/app/MainActivity;->web:Landroid/webkit/WebView;
    invoke-virtual {v0, v2}, Landroid/webkit/WebView;->setBackgroundColor(I)V

    # settings
    invoke-virtual {v0}, Landroid/webkit/WebView;->getSettings()Landroid/webkit/WebSettings;
    move-result-object v2
    const/4 v3, 0x1
    invoke-virtual {v2, v3}, Landroid/webkit/WebSettings;->setJavaScriptEnabled(Z)V
    invoke-virtual {v2, v3}, Landroid/webkit/WebSettings;->setDomStorageEnabled(Z)V
    invoke-virtual {v2, v3}, Landroid/webkit/WebSettings;->setAllowFileAccess(Z)V
    invoke-virtual {v2, v3}, Landroid/webkit/WebSettings;->setAllowFileAccessFromFileURLs(Z)V
    invoke-virtual {v2, v3}, Landroid/webkit/WebSettings;->setLoadWithOverviewMode(Z)V
    invoke-virtual {v2, v3}, Landroid/webkit/WebSettings;->setUseWideViewPort(Z)V
    const/4 v4, 0x2
    invoke-virtual {v2, v4}, Landroid/webkit/WebSettings;->setCacheMode(I)V
    const/16 v4, 0x64
    invoke-virtual {v2, v4}, Landroid/webkit/WebSettings;->setTextZoom(I)V
    const/4 v4, 0x1
    invoke-virtual {v2, v4}, Landroid/webkit/WebSettings;->setMixedContentMode(I)V

    # web.addJavascriptInterface(new KenozBridge(this), "KenozAndroid")
    new-instance v2, Lcom/kenoz/app/KenozBridge;
    invoke-direct {v2, p0}, Lcom/kenoz/app/KenozBridge;-><init>(Lcom/kenoz/app/MainActivity;)V
    const-string v4, "KenozAndroid"
    invoke-virtual {v0, v2, v4}, Landroid/webkit/WebView;->addJavascriptInterface(Ljava/lang/Object;Ljava/lang/String;)V

    # setContentView(web)
    invoke-virtual {p0, v0}, Landroid/app/Activity;->setContentView(Landroid/view/View;)V

    # web.loadUrl("file:///android_asset/index.html")
    const-string v2, "file:///android_asset/index.html"
    invoke-virtual {v0, v2}, Landroid/webkit/WebView;->loadUrl(Ljava/lang/String;)V

    return-void
.end method

.method public onBackPressed()V
    .locals 4
    iget-object v0, p0, Lcom/kenoz/app/MainActivity;->web:Landroid/webkit/WebView;
    if-eqz v0, :finish

    iget-boolean v1, p0, Lcom/kenoz/app/MainActivity;->backHandled:Z
    if-eqz v1, :finish

    const/4 v1, 0x1
    iput-boolean v1, p0, Lcom/kenoz/app/MainActivity;->backHandled:Z

    new-instance v2, Lcom/kenoz/app/BackCallback;
    invoke-direct {v2, p0}, Lcom/kenoz/app/BackCallback;-><init>(Lcom/kenoz/app/MainActivity;)V

    const-string v3, "(function(){try{return !!(window.kenozBack && window.kenozBack());}catch(e){return false;}})()"
    invoke-virtual {v0, v3, v2}, Landroid/webkit/WebView;->evaluateJavascript(Ljava/lang/String;Landroid/webkit/ValueCallback;)V

    return-void

    :finish
    invoke-super {p0}, Landroid/app/Activity;->onBackPressed()V
    return-void
.end method

.method protected onDestroy()V
    .locals 2
    iget-object v0, p0, Lcom/kenoz/app/MainActivity;->web:Landroid/webkit/WebView;
    if-eqz v0, :after

    const-string v1, "KenozAndroid"
    invoke-virtual {v0, v1}, Landroid/webkit/WebView;->removeJavascriptInterface(Ljava/lang/String;)V
    invoke-virtual {v0}, Landroid/webkit/WebView;->destroy()V
    const/4 v0, 0x0
    iput-object v0, p0, Lcom/kenoz/app/MainActivity;->web:Landroid/webkit/WebView;

    :after
    invoke-super {p0}, Landroid/app/Activity;->onDestroy()V
    return-void
.end method

.method public getPrefs()Landroid/content/SharedPreferences;
    .locals 1
    iget-object v0, p0, Lcom/kenoz/app/MainActivity;->prefs:Landroid/content/SharedPreferences;
    return-object v0
.end method

.method public resetBack()V
    .locals 1
    const/4 v0, 0x0
    iput-boolean v0, p0, Lcom/kenoz/app/MainActivity;->backHandled:Z
    return-void
.end method
