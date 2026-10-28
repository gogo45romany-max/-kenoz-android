.class public Lcom/kenoz/app/UiRunnable;
.super Ljava/lang/Object;
.implements Ljava/lang/Runnable;
.source "MainActivity.java"

# Runs one UI-thread action for the JavaScript bridge:
#   code 1 -> copy text (+ toast)
#   code 2 -> share text/subject
#   code 3 -> light system bars
#   code 4 -> dark system bars

.field private act:Lcom/kenoz/app/MainActivity;

.field private code:I

.field private extra:Ljava/lang/String;

.field private text:Ljava/lang/String;

.method public constructor <init>(Lcom/kenoz/app/MainActivity;ILjava/lang/String;Ljava/lang/String;)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Lcom/kenoz/app/UiRunnable;->act:Lcom/kenoz/app/MainActivity;
    iput p2, p0, Lcom/kenoz/app/UiRunnable;->code:I
    iput-object p3, p0, Lcom/kenoz/app/UiRunnable;->text:Ljava/lang/String;
    iput-object p4, p0, Lcom/kenoz/app/UiRunnable;->extra:Ljava/lang/String;
    return-void
.end method

.method public run()V
    .locals 6
    iget-object v0, p0, Lcom/kenoz/app/UiRunnable;->act:Lcom/kenoz/app/MainActivity;
    if-nez v0, :done

    iget v1, p0, Lcom/kenoz/app/UiRunnable;->code:I
    const/4 v2, 0x1
    if-ne v1, v2, :not_copy

    # ---------------- copy ----------------
    :try_start_copy
    const-string v1, "clipboard"
    invoke-virtual {v0, v1}, Lcom/kenoz/app/MainActivity;->getSystemService(Ljava/lang/String;)Ljava/lang/Object;
    move-result-object v1
    check-cast v1, Landroid/content/ClipboardManager;
    if-nez v1, :done

    const-string v2, "كنوز"
    iget-object v3, p0, Lcom/kenoz/app/UiRunnable;->text:Ljava/lang/String;
    invoke-static {v2, v3}, Landroid/content/ClipData;->newPlainText(Ljava/lang/CharSequence;Ljava/lang/CharSequence;)Landroid/content/ClipData;
    move-result-object v2
    invoke-virtual {v1, v2}, Landroid/content/ClipboardManager;->setPrimaryClip(Landroid/content/ClipData;)V

    const-string v1, "تم نسخ النص"
    const/4 v2, 0x0
    invoke-static {v0, v1, v2}, Landroid/widget/Toast;->makeText(Landroid/content/Context;Ljava/lang/CharSequence;I)Landroid/widget/Toast;
    move-result-object v1
    invoke-virtual {v1}, Landroid/widget/Toast;->show()V
    :try_end_copy
    .catch Ljava/lang/Exception; {:try_start_copy .. :try_end_copy} :catch_copy
    return-void

    :catch_copy
    return-void

    # ---------------- share ----------------
    :not_copy
    iget v1, p0, Lcom/kenoz/app/UiRunnable;->code:I
    const/4 v2, 0x2
    if-ne v1, v2, :not_share

    :try_start_share
    new-instance v1, Landroid/content/Intent;
    const-string v2, "android.intent.action.SEND"
    invoke-direct {v1, v2}, Landroid/content/Intent;-><init>(Ljava/lang/String;)V
    const-string v2, "text/plain"
    invoke-virtual {v1, v2}, Landroid/content/Intent;->setType(Ljava/lang/String;)Landroid/content/Intent;
    const-string v2, "android.intent.extra.SUBJECT"
    iget-object v3, p0, Lcom/kenoz/app/UiRunnable;->extra:Ljava/lang/String;
    invoke-virtual {v1, v2, v3}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;
    const-string v2, "android.intent.extra.TEXT"
    iget-object v3, p0, Lcom/kenoz/app/UiRunnable;->text:Ljava/lang/String;
    invoke-virtual {v1, v2, v3}, Landroid/content/Intent;->putExtra(Ljava/lang/String;Ljava/lang/String;)Landroid/content/Intent;
    const-string v2, "مشاركة"
    invoke-static {v1, v2}, Landroid/content/Intent;->createChooser(Landroid/content/Intent;Ljava/lang/CharSequence;)Landroid/content/Intent;
    move-result-object v1
    invoke-virtual {v0, v1}, Lcom/kenoz/app/MainActivity;->startActivity(Landroid/content/Intent;)V
    :try_end_share
    .catch Ljava/lang/Exception; {:try_start_share .. :try_end_share} :catch_share
    return-void

    :catch_share
    return-void

    # ---------------- system bar colours ----------------
    :not_share
    invoke-virtual {v0}, Lcom/kenoz/app/MainActivity;->getWindow()Landroid/view/Window;
    move-result-object v2
    if-nez v2, :done

    const v3, 0xff0f2b46
    invoke-virtual {v2, v3}, Landroid/view/Window;->setStatusBarColor(I)V

    const/4 v4, 0x4
    if-ne v1, v4, :light_bars
    const v3, 0xff0b1420

    :light_bars
    invoke-virtual {v2, v3}, Landroid/view/Window;->setNavigationBarColor(I)V

    :done
    return-void
.end method
