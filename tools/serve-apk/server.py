#!/usr/bin/env python3
"""KENOZ — tiny download server for the built APK.

Serves a one-page Arabic download page plus the APK itself with
`Content-Disposition: attachment`, so clicking the file name starts the
download immediately. Supports HTTP Range requests (resumable downloads)
and HEAD, and accepts any Host / Origin (it is meant to run behind a proxy).

Usage:
    python3 tools/serve-apk/server.py [--port 8080] [--apk PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import html
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

APK_NAME = "KENOZ-1.0.0.apk"
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
CANDIDATES = [
    os.path.join(REPO, APK_NAME),              # committed copy at the repo root
    os.path.join(REPO, "dist", APK_NAME),      # tools/local-apk/build.sh output
    os.path.join(os.path.expanduser("~"), APK_NAME),
]

PAGE = """<!doctype html>
<html lang="ar" dir="rtl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>تحميل كنوز — {name}</title>
<style>
  :root {{ --navy:#0f2b46; --navy2:#0b1420; --gold:#c8a64b; --paper:#f6f3ea; }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; min-height:100vh; font-family:"Segoe UI",Tahoma,"Noto Kufi Arabic",sans-serif;
         background:radial-gradient(circle at 50% 0%,#16405f 0%,var(--navy) 45%,var(--navy2) 100%);
         color:var(--paper); display:flex; align-items:center; justify-content:center; padding:28px 18px; }}
  .card {{ width:100%; max-width:520px; background:rgba(255,255,255,.045);
           border:1px solid rgba(200,166,75,.35); border-radius:22px; padding:30px 26px 26px;
           box-shadow:0 24px 60px rgba(0,0,0,.45); text-align:center; backdrop-filter:blur(6px); }}
  .cross {{ width:56px; height:56px; margin:0 auto 14px; display:grid; place-items:center;
            border-radius:16px; background:rgba(200,166,75,.12); border:1px solid rgba(200,166,75,.45); }}
  .cross svg {{ width:30px; height:30px; stroke:var(--gold); stroke-width:3.2; fill:none; }}
  h1 {{ margin:0 0 4px; font-size:25px; letter-spacing:.5px; }}
  .sub {{ margin:0 0 22px; color:#b9c7d4; font-size:14px; }}
  a.dl {{ display:block; text-decoration:none; background:linear-gradient(180deg,#d7b55e,#b8933a);
          color:#231a06; font-weight:800; font-size:17px; padding:16px 18px; border-radius:14px;
          box-shadow:0 10px 24px rgba(200,166,75,.28); transition:transform .12s ease, filter .12s ease; }}
  a.dl:hover {{ filter:brightness(1.06); transform:translateY(-1px); }}
  a.dl:active {{ transform:translateY(0); }}
  .name {{ margin:18px 0 6px; font-size:15px; }}
  .name a {{ color:#ffe9a8; font-weight:700; text-decoration:none; border-bottom:1px dashed rgba(255,233,168,.5); }}
  .meta {{ margin:0; color:#9fb0c0; font-size:12.5px; line-height:1.85; word-break:break-all; }}
  .meta code {{ color:#d9e3ec; font-size:11.5px; background:rgba(255,255,255,.06);
                padding:2px 6px; border-radius:6px; }}
  ol {{ text-align:right; margin:22px 0 0; padding-inline-start:20px; color:#cfdae4; font-size:13.5px; line-height:2; }}
  ol li::marker {{ color:var(--gold); }}
  .note {{ margin-top:18px; font-size:12px; color:#94a6b6; }}
</style>
</head>
<body>
  <div class="card">
    <div class="cross"><svg viewBox="0 0 24 24"><path d="M12 3v18M6.5 9h11"/></svg></div>
    <h1>كنوز</h1>
    <p class="sub">مكتبة الكنيسة القبطية الأرثوذكسية — تعمل دون إنترنت</p>

    <a class="dl" href="/{name}" download="{name}" target="_blank" rel="noopener">تحميل {name} ({size_mb} م.ب)</a>

    <p class="name">أو اضغط على اسم الملف: <a href="/{name}" download="{name}" target="_blank" rel="noopener">{name}</a></p>
    <p class="meta">
      الإصدار 1.0.0 — أندرويد 7.0+ — بدون صلاحيات<br>
      SHA-256: <code>{sha}</code>
    </p>

    <ol>
      <li>اضغط زر التحميل، وانتظر حتى ينتهي الملف.</li>
      <li>افتح الملف من «التنزيلات» على الهاتف.</li>
      <li>اسمح بـ«تثبيت من مصدر غير معروف» عند الطلب.</li>
      <li>لو ظهر تحذير Play Protect اختر «تثبيت على أي حال».</li>
    </ol>
    <p class="note">المحتوى: 3106 مستندًا في 13 قسمًا — الكتاب المقدس، الأجبية، الخولاجي، القطمارس، السنكسار، التسبحة، الإبصلمودية وغيرها.</p>
  </div>
</body>
</html>
"""


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Handler(BaseHTTPRequestHandler):
    server_version = "KenozAPK/1.0"
    protocol_version = "HTTP/1.1"
    apk_path = CANDIDATES[0]
    apk_size = 0
    apk_sha = ""
    page = b""

    # ---------------------------------------------------------------- helpers
    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "*")
        self.send_header("Access-Control-Expose-Headers", "Content-Disposition, Content-Length, Accept-Ranges")

    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    # ------------------------------------------------------------------ verbs
    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET(head_only=True)

    def do_GET(self, head_only: bool = False) -> None:  # noqa: N802
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html", "/download", "/ar"):
            self._send(200, self.page, "text/html; charset=utf-8",
                       {"Cache-Control": "no-store"})
            return
        if path in ("/healthz", "/health"):
            self._send(200, b"ok", "text/plain; charset=utf-8")
            return
        if path in (f"/{APK_NAME}", "/apk", "/download.apk", "/KENOZ.apk"):
            self._serve_apk(head_only)
            return
        self._send(404, "404 — الصفحة غير موجودة".encode(), "text/plain; charset=utf-8")

    # -------------------------------------------------------------------- apk
    def _serve_apk(self, head_only: bool = False) -> None:
        path = self.apk_path
        try:
            total = os.path.getsize(path)
        except OSError:
            self._send(404, b"APK not built yet", "text/plain; charset=utf-8")
            return

        start, end = 0, total - 1
        status = 200
        rng = self.headers.get("Range")
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)$", rng.strip())
            if m:
                a, b = m.group(1), m.group(2)
                if a:
                    start = int(a)
                    if b:
                        end = min(int(b), total - 1)
                elif b:  # suffix range: last N bytes
                    start = max(0, total - int(b))
                if start > end or start >= total:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{total}")
                    self.send_header("Content-Length", "0")
                    self._cors()
                    self.end_headers()
                    return
                status = 206

        length = end - start + 1
        self.send_response(status)
        self.send_header("Content-Type", "application/vnd.android.package-archive")
        self.send_header("Content-Length", str(length))
        self.send_header("Content-Disposition",
                         f'attachment; filename="{APK_NAME}"; '
                         f"filename*=UTF-8''{APK_NAME}")
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{total}") if status == 206 else None
        self.send_header("Cache-Control", "public, max-age=3600")
        self._cors()
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-APK-SHA256", self.apk_sha)
        self.end_headers()
        if head_only:
            return

        with open(path, "rb") as f:
            f.seek(start)
            remaining = length
            while remaining > 0:
                chunk = f.read(min(262144, remaining))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                remaining -= len(chunk)

    def log_message(self, fmt: str, *args) -> None:  # quieter logs
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8080)))
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--apk", default=os.environ.get("KENOZ_APK", ""))
    args = ap.parse_args()

    apk = args.apk
    if not apk:
        apk = next((c for c in CANDIDATES if os.path.isfile(c)), "")
    if not apk or not os.path.isfile(apk):
        sys.exit("APK not found in: " + ", ".join(CANDIDATES) +
                 "\nBuild it with tools/local-apk/build.sh")

    Handler.apk_path = apk
    Handler.apk_size = os.path.getsize(apk)
    Handler.apk_sha = sha256_of(apk)
    Handler.page = PAGE.format(
        name=APK_NAME,
        sha=html.escape(Handler.apk_sha),
        size_mb=f"{Handler.apk_size / 1048576:.1f}",
    ).encode("utf-8")

    srv = ThreadingHTTPServer((args.host, args.port), Handler)
    srv.daemon_threads = True
    print(f"KENOZ APK server on http://{args.host}:{args.port}  ->  {apk} "
          f"({Handler.apk_size} bytes, sha256 {Handler.apk_sha})", flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
