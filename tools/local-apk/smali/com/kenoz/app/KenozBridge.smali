.class public Lcom/kenoz/app/KenozBridge;
.super Ljava/lang/Object;
.source "MainActivity.java"

# Exposed to JavaScript as window.KenozAndroid.

.field private act:Lcom/kenoz/app/MainActivity;

.method public constructor <init>(Lcom/kenoz/app/MainActivity;)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Lcom/kenoz/app/KenozBridge;->act:Lcom/kenoz/app/MainActivity;
    return-void
.end method

.method public readAsset(Ljava/lang/String;)Ljava/lang/String;
    .annotation runtime Landroid/webkit/JavascriptInterface;
    .end annotation

    .locals 4
    :try_start
    new-instance v0, Ljava/util/Scanner;
    iget-object v1, p0, Lcom/kenoz/app/KenozBridge;->act:Lcom/kenoz/app/MainActivity;
    invoke-virtual {v1}, Lcom/kenoz/app/MainActivity;->getAssets()Landroid/content/res/AssetManager;
    move-result-object v1
    invoke-virtual {v1, p1}, Landroid/content/res/AssetManager;->open(Ljava/lang/String;)Ljava/io/InputStream;
    move-result-object v1
    const-string v2, "UTF-8"
    invoke-direct {v0, v1, v2}, Ljava/util/Scanner;-><init>(Ljava/io/InputStream;Ljava/lang/String;)V

    const-string v2, "\\A"
    invoke-virtual {v0, v2}, Ljava/util/Scanner;->useDelimiter(Ljava/lang/String;)Ljava/util/Scanner;

    invoke-virtual {v0}, Ljava/util/Scanner;->next()Ljava/lang/String;
    move-result-object v1

    invoke-virtual {v0}, Ljava/util/Scanner;->close()V
    return-object v1
    :try_end
    .catch Ljava/lang/Exception; {:try_start .. :try_end} :catch_all

    :catch_all
    const-string v0, ""
    return-object v0
.end method

.method public getPref(Ljava/lang/String;)Ljava/lang/String;
    .annotation runtime Landroid/webkit/JavascriptInterface;
    .end annotation

    .locals 3
    iget-object v0, p0, Lcom/kenoz/app/KenozBridge;->act:Lcom/kenoz/app/MainActivity;
    invoke-virtual {v0}, Lcom/kenoz/app/MainActivity;->getPrefs()Landroid/content/SharedPreferences;
    move-result-object v0
    if-nez v0, :empty

    const-string v1, ""
    invoke-interface {v0, p1, v1}, Landroid/content/SharedPreferences;->getString(Ljava/lang/String;Ljava/lang/String;)Ljava/lang/String;
    move-result-object v1
    return-object v1

    :empty
    const-string v0, ""
    return-object v0
.end method

.method public setPref(Ljava/lang/String;Ljava/lang/String;)V
    .annotation runtime Landroid/webkit/JavascriptInterface;
    .end annotation

    .locals 2
    iget-object v0, p0, Lcom/kenoz/app/KenozBridge;->act:Lcom/kenoz/app/MainActivity;
    invoke-virtual {v0}, Lcom/kenoz/app/MainActivity;->getPrefs()Landroid/content/SharedPreferences;
    move-result-object v0
    if-nez v0, :done

    invoke-interface {v0}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v0
    invoke-interface {v0, p1, p2}, Landroid/content/SharedPreferences$Editor;->putString(Ljava/lang/String;Ljava/lang/String;)Landroid/content/SharedPreferences$Editor;
    move-result-object v0
    invoke-interface {v0}, Landroid/content/SharedPreferences$Editor;->apply()V

    :done
    return-void
.end method

.method public versionName()Ljava/lang/String;
    .annotation runtime Landroid/webkit/JavascriptInterface;
    .end annotation

    .locals 5
    :try_start
    iget-object v0, p0, Lcom/kenoz/app/KenozBridge;->act:Lcom/kenoz/app/MainActivity;
    invoke-virtual {v0}, Lcom/kenoz/app/MainActivity;->getPackageManager()Landroid/content/pm/PackageManager;
    move-result-object v1
    invoke-virtual {v0}, Lcom/kenoz/app/MainActivity;->getPackageName()Ljava/lang/String;
    move-result-object v2
    const/4 v3, 0x0
    invoke-virtual {v1, v2, v3}, Landroid/content/pm/PackageManager;->getPackageInfo(Ljava/lang/String;I)Landroid/content/pm/PackageInfo;
    move-result-object v1
    iget-object v1, v1, Landroid/content/pm/PackageInfo;->versionName:Ljava/lang/String;
    return-object v1
    :try_end
    .catch Landroid/content/pm/PackageManager$NameNotFoundException; {:try_start .. :try_end} :catch_missing

    :catch_missing
    const-string v0, "1.0.0"
    return-object v0
.end method

.method public copy(Ljava/lang/String;)V
    .annotation runtime Landroid/webkit/JavascriptInterface;
    .end annotation

    .locals 4
    iget-object v0, p0, Lcom/kenoz/app/KenozBridge;->act:Lcom/kenoz/app/MainActivity;
    new-instance v1, Lcom/kenoz/app/UiRunnable;
    const/4 v2, 0x1
    const/4 v3, 0x0
    invoke-direct {v1, v0, v2, p1, v3}, Lcom/kenoz/app/UiRunnable;-><init>(Lcom/kenoz/app/MainActivity;ILjava/lang/String;Ljava/lang/String;)V
    invoke-virtual {v0, v1}, Lcom/kenoz/app/MainActivity;->runOnUiThread(Ljava/lang/Runnable;)V
    return-void
.end method

.method public share(Ljava/lang/String;Ljava/lang/String;)V
    .annotation runtime Landroid/webkit/JavascriptInterface;
    .end annotation

    .locals 4
    iget-object v0, p0, Lcom/kenoz/app/KenozBridge;->act:Lcom/kenoz/app/MainActivity;
    new-instance v1, Lcom/kenoz/app/UiRunnable;
    const/4 v2, 0x2
    invoke-direct {v1, v0, v2, p1, p2}, Lcom/kenoz/app/UiRunnable;-><init>(Lcom/kenoz/app/MainActivity;ILjava/lang/String;Ljava/lang/String;)V
    invoke-virtual {v0, v1}, Lcom/kenoz/app/MainActivity;->runOnUiThread(Ljava/lang/Runnable;)V
    return-void
.end method

.method public setTheme(Z)V
    .annotation runtime Landroid/webkit/JavascriptInterface;
    .end annotation

    .locals 5
    iget-object v0, p0, Lcom/kenoz/app/KenozBridge;->act:Lcom/kenoz/app/MainActivity;
    const/4 v2, 0x3
    if-eqz p1, :use_code
    const/4 v2, 0x4

    :use_code
    new-instance v1, Lcom/kenoz/app/UiRunnable;
    const/4 v3, 0x0
    invoke-direct {v1, v0, v2, v3, v3}, Lcom/kenoz/app/UiRunnable;-><init>(Lcom/kenoz/app/MainActivity;ILjava/lang/String;Ljava/lang/String;)V
    invoke-virtual {v0, v1}, Lcom/kenoz/app/MainActivity;->runOnUiThread(Ljava/lang/Runnable;)V
    return-void
.end method
