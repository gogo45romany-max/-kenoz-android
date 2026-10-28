.class public Lcom/kenoz/app/BackCallback;
.super Ljava/lang/Object;
.implements Landroid/webkit/ValueCallback;
.source "MainActivity.java"

.field private act:Lcom/kenoz/app/MainActivity;

.method public constructor <init>(Lcom/kenoz/app/MainActivity;)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Lcom/kenoz/app/BackCallback;->act:Lcom/kenoz/app/MainActivity;
    return-void
.end method

.method public onReceiveValue(Ljava/lang/Object;)V
    .locals 3
    iget-object v0, p0, Lcom/kenoz/app/BackCallback;->act:Lcom/kenoz/app/MainActivity;
    if-nez v0, :done

    const-string v1, "true"
    invoke-virtual {v1, p1}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v1

    if-eqz v1, :not_handled
    invoke-virtual {v0}, Lcom/kenoz/app/MainActivity;->resetBack()V
    return-void

    :not_handled
    invoke-virtual {v0}, Lcom/kenoz/app/MainActivity;->resetBack()V
    invoke-virtual {v0}, Lcom/kenoz/app/MainActivity;->finish()V
    return-void

    :done
    return-void
.end method
