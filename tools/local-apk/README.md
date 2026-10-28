# بناء APK بدون Android SDK

هذا المجلد يجعل من الممكن إنتاج `KENOZ-1.0.0.apk` في بيئة لا تحتوي على Android SDK
ولا Gradle ولا JDK كامل (مثل بيئة العمل التي جُمّع فيها التطبيق أول مرة، حيث كان
الوصول مقتصرًا على PyPI وnpm وGitHub API).

> **المسار الرسمي للبناء هو `.github/workflows/build-apk.yml`** (Gradle + Java 17 +
> SDK 35)، ويبني من المصدر الرسمي `app/src/main/java/...`. هذا المجلد بديل تقني فقط.

## الاستخدام

```bash
tools/local-apk/build.sh            # dist/KENOZ-1.0.0.apk
tools/local-apk/build.sh /tmp/out   # مجلد إخراج مخصص
```

المتطلبات: `bash`, `python3`, `node` >= 18, `npm`, `pip`, `curl`.
البناء **قابل للتكرار بايتًا ببايت**: نفس المدخلات تعطي نفس الـ sha256.

## ما الذي يفعله

| المرحلة | الأداة | الناتج |
|---|---|---|
| 1 | `aapt2` (npm: aaptjs3) | ترجمة `res/` ثم ربط `AndroidManifest.xml` + `assets/` → `base.apk` |
| 2 | `smali` + `dexlib2` (npm: apktool-jar) داخل `java/SmaliDriver.java` | `smali/**` → `classes.dex` |
| 3 | `verify_smali.py` | فحص 100 مرجع (صنف/دالة/حقل) مقابل `android.jar` + حدود السجلات + رأس الـ dex |
| 4 | `BaksmaliDriver` | فك الـ dex مرة أخرى (تحقق من البنية) |
| 5 | python | إضافة `classes.dex` غير مضغوط ومحاذى إلى 4 بايت |
| 6 | `sign_v2.mjs` | كتابة كتلة **APK Signature Scheme v2** بمفتاح `keystore/kenoz.p12` |
| 7 | `verify_apk.mjs` | التحقق من البصمات المتسلسلة (١ ميجابايت/قطعة، بادئة `0xa5`/`0x5a`) ومن التوقيع و SPKI |

### لماذا توقيع خاص؟

حزمة `apk_sign_ts` على npm تكتب المفتاح العام بصيغة PKCS#1 بينما أندرويد يقرأ
`X509EncodedKeySpec` (SubjectPublicKeyInfo) فقط، فتكون الحزمة ناتجة عن توقيع
غير مقبول على الجهاز. لذلك يكتب `sign_v2.mjs` الكتلة مباشرة وفق المواصفة،
وبنية التحقق (`verify_apk.mjs`) مستمدة من `ApkSignatureSchemeV2Verifier` في AOSP:
تقطيع **كل مقطع على حدة** (المدخلات، الدليل المركزي، EOCD بعد تعديل إزاحة الدليل).

لا يوجد توقيع v1؛ ذلك مقبول لأن `minSdkVersion=24` (أندرويد يشترط v2 فقط منذ 7.0،
ويشترط v2+ لأي تطبيق `targetSdk` 30 أو أحدث).

### smali الموجود هنا

`smali/com/kenoz/app/` ترجمة يدوية لمنطق `MainActivity.java`:

- `MainActivity` — WebView، إعدادات، `loadUrl("file:///android_asset/index.html")`،
  زر الرجوع عبر `evaluateJavascript` + `ValueCallback`.
- `KenozBridge` — الجسر `window.KenozAndroid`: `readAsset`, `getPref`, `setPref`,
  `copy`, `share`, `versionName`, `setTheme` (كلها معلّمة بـ `@JavascriptInterface`).
- `BackCallback` — مستقبل نتيجة `window.kenozBack()`.
- `UiRunnable` — تنفيذ عمليات الواجهة على الخيط الرئيسي (نسخ، مشاركة، ألوان شريط النظام).

`java/` يحتوي أدوات البناء (تجميع/فك smali)، و`classes/` نسختها المترجمة مسبقًا
(حتى لا يحتاج السكربت إلى مُترجم Java).

## تحقق يدوي

```bash
python3 tools/local-apk/verify_smali.py tools/local-apk/smali "$WORK/classes.dex" "$WORK/tools/android.jar"
node tools/local-apk/verify_apk.mjs dist/KENOZ-1.0.0.apk
$AAPT2 dump badging dist/KENOZ-1.0.0.apk
```
