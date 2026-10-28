#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KENOZ content builder.

Reads the unified extracted corpus (KENOZ_All_Extracted_Texts_Unified.zip) and
produces the offline JSON library used by the KENOZ Android app / web preview:

    <out>/catalog.json                  -> list of sections
    <out>/<section>/index.json          -> groups + documents of a section
    <out>/<section>/<doc>.json          -> document body

Run:
    python3 tools/build_kenoz_content.py \
        --zip KENOZ_All_Extracted_Texts_Unified.zip \
        --out app/src/main/assets/content
"""

import argparse
import html as html_mod
import json
import os
import re
import shutil
import sys
import zipfile
from collections import OrderedDict, defaultdict

# --------------------------------------------------------------------------
# generic helpers
# --------------------------------------------------------------------------

AR_DIACRITICS = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED\u0640]")
WS = re.compile(r"[ \t\u00a0]+")
MANY_NL = re.compile(r"\n{3,}")
NUL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def strip_bom(s):
    return s.replace("\ufeff", "")


def clean_text(s):
    s = strip_bom(s or "")
    s = NUL.sub("", s)
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = WS.sub(" ", s)
    s = "\n".join(line.strip() for line in s.split("\n"))
    s = MANY_NL.sub("\n\n", s)
    return s.strip()


def norm_ar(s):
    """Normalisation used for search and for forgiving title matching."""
    s = strip_bom(s or "")
    s = AR_DIACRITICS.sub("", s)
    s = re.sub(r"[أإآٱ]", "ا", s)
    s = s.replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def is_coptic_line(s):
    """Latin-script Coptic transliteration such as: |wc ePsoic 'en ou\\wc ..."""
    if not s:
        return False
    latin = len(re.findall(r"[A-Za-z]", s))
    arabic = len(re.findall(r"[\u0600-\u06FF]", s))
    if latin < 4 or latin < arabic:
        return False
    marks = len(re.findall(r"[\\|`^]", s))
    return marks >= 1 or latin > 4 * max(arabic, 1)


def is_arabic(s):
    return bool(re.search(r"[\u0600-\u06FF]", s or ""))


# --------------------------------------------------------------------------
# source parsers
# --------------------------------------------------------------------------

ROW_RE = re.compile(r"^\s*\[ROW\s+(\d+)\]\s*$")
COL_RE = re.compile(r"^\s*\[COLUMN\s+(\d+)\]\s?(.*)$")
SEP = re.compile(r"^[#=]{10,}$")
ORSO_BREAK = re.compile(r"^\+{3,}$")
ORSO_PARA = re.compile(r"^\+$")


def parse_xls(body):
    """Return list of rows; every row is an OrderedDict {column:int -> text}."""
    rows = []
    cur = None
    last_col = None
    for line in body:
        if SEP.match(line) or line.startswith("SOURCE"):
            continue
        m = COL_RE.match(line)
        if m:
            if cur is None:
                cur = OrderedDict()
            col = int(m.group(1))
            val = m.group(2)
            if col in cur and cur[col]:
                cur[col] = (cur[col] + "\n" + val).strip()
            else:
                cur[col] = val.strip()
            last_col = col
            continue
        if ROW_RE.match(line):
            if cur:
                rows.append(cur)
            cur = OrderedDict()
            last_col = None
            continue
        if not line.strip():
            continue
        if cur is not None and last_col is not None:
            cur[last_col] = (cur[last_col] + "\n" + line).strip()
    if cur:
        rows.append(cur)
    return rows


def parse_orso(body):
    """Return (doc_title, [{'t': title, 'p': [paragraph, ...]}...]) for an ORSO body."""
    doc_title = ""
    sections = []
    cur_title = ""
    paras = []

    def push_section():
        nonlocal cur_title, paras
        if paras or cur_title:
            sections.append({"t": cur_title, "p": list(paras)})
        cur_title = ""
        paras = []

    started = False
    for raw in body:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("TITLE:") and not started:
            doc_title = clean_text(line[6:])
            cur_title = doc_title
            continue
        if SEP.match(line):
            continue
        if set(line) == {"+", " "} or (line and set(line) <= set("+ ")):
            if len(line) >= 3:
                push_section()
                started = True
            continue
        started = True
        line = clean_text(line.lstrip("+").strip())
        if not line:
            continue
        if not paras and not cur_title:
            cur_title = line
            continue
        paras.append(line)
    push_section()
    if not doc_title:
        doc_title = sections[0]["t"] if sections and sections[0]["t"] else ""
    return doc_title, sections


def html_to_text(raw):
    """Very small HTML to text converter (word/html exports with heavy styles)."""
    s = raw
    s = re.sub(r"(?is)<!--.*?-->", "\n", s)
    s = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", "\n", s)
    s = re.sub(r"(?is)<head[^>]*>.*?</head>", "\n", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</(p|div|tr|li|h[1-6]|table)>", "\n", s)
    s = re.sub(r"(?is)<[^>]+>", "", s)
    s = html_mod.unescape(s)
    s = s.replace("\xa0", " ")
    lines = []
    for line in s.split("\n"):
        t = WS.sub(" ", line).strip()
        if t and t != "Untitled Document":
            lines.append(t)
    return lines


# --------------------------------------------------------------------------
# builder
# --------------------------------------------------------------------------

class Library:
    def __init__(self, out):
        self.out = out
        self.sections = OrderedDict()   # id -> dict
        self.counter = defaultdict(int)
        self.words = OrderedDict()

    def section(self, sid, title, icon, desc, accent=None):
        if sid not in self.sections:
            self.sections[sid] = {
                "id": sid,
                "title": title,
                "icon": icon,
                "desc": desc,
                "accent": accent or "#c8a64b",
                "groups": OrderedDict(),
                "count": 0,
            }
        return self.sections[sid]

    def group(self, sid, gid, title, note=""):
        sec = self.sections[sid]
        if gid not in sec["groups"]:
            sec["groups"][gid] = {"id": gid, "title": title, "note": note, "docs": []}
        return sec["groups"][gid]

    def add_doc(self, sid, gid, title, subtitle, body, *, kind="text", toc=None, sort=None):
        sec = self.sections[sid]
        if gid not in sec["groups"]:
            raise KeyError(f"unknown group {sid}/{gid}")
        self.counter[sid] += 1
        doc_id = f"{sid[:2]}{self.counter[sid]:05d}"
        doc = {"t": title.strip() or "بدون عنوان", "s": (subtitle or "").strip()}
        if kind == "bible":
            doc["chs"] = body
        elif kind == "sections":
            doc["sec"] = body
            if toc:
                doc["toc"] = toc
        else:
            doc["b"] = body
            if toc:
                doc["toc"] = toc
        filename = f"{doc_id}.json"
        sec["groups"][gid]["docs"].append(
            {
                "id": doc_id,
                "t": doc["t"],
                "s": doc["s"],
                "f": filename,
                "k": kind,
                "_sort": sort if sort is not None else len(sec["groups"][gid]["docs"]),
            }
        )
        sec["count"] += 1
        self.pending.append((sid, filename, doc))
        return doc_id

    def flush(self):
        if not os.path.isdir(self.out):
            os.makedirs(self.out)
        total_chars = 0
        catalog = []
        for sid, sec in self.sections.items():
            sdir = os.path.join(self.out, sid)
            os.makedirs(sdir, exist_ok=True)
            groups = []
            for g in sec["groups"].values():
                docs = sorted(g["docs"], key=lambda d: d["_sort"])
                for d in docs:
                    d.pop("_sort", None)
                groups.append(
                    {"id": g["id"], "title": g["title"], "note": g["note"], "docs": docs}
                )
            index = {"id": sid, "title": sec["title"], "groups": groups}
            with open(os.path.join(sdir, "index.json"), "w", encoding="utf-8") as f:
                json.dump(index, f, ensure_ascii=False, separators=(",", ":"))
            catalog.append(
                {
                    "id": sid,
                    "title": sec["title"],
                    "icon": sec["icon"],
                    "desc": sec["desc"],
                    "accent": sec["accent"],
                    "count": sec["count"],
                    "index": f"{sid}/index.json",
                }
            )
        for sid, filename, doc in self.pending:
            path = os.path.join(self.out, sid, filename)
            data = json.dumps(doc, ensure_ascii=False, separators=(",", ":"))
            total_chars += len(data)
            with open(path, "w", encoding="utf-8") as f:
                f.write(data)
        cat = {
            "app": "KENOZ",
            "version": 1,
            "generated": "2026-10-28",
            "sections": catalog,
            "docs": sum(s["count"] for s in self.sections.values()),
        }
        with open(os.path.join(self.out, "catalog.json"), "w", encoding="utf-8") as f:
            json.dump(cat, f, ensure_ascii=False, separators=(",", ":"))
        return cat, total_chars


# --------------------------------------------------------------------------
# lookup tables
# --------------------------------------------------------------------------

COP_MONTHS = [
    "توت", "بابه", "هاتور", "كيهك", "طوبة", "أمشير", "برمهات",
    "برمودة", "بشنس", "بؤونة", "أبيب", "مسرى", "النسئ",
]

BOOKS_OLD = {
    "01-Takwen": "التكوين",
    "02-Khrog": "الخروج",
    "03-Laween": "اللاويين",
    "04-Addad": "العدد",
    "05-Tasnya": "التثنية",
    "06-Yasho3": "يشوع",
    "07-Kodah": "القضاة",
    "08-Ra3os": "راعوث",
    "09-Samuel1": "صموئيل الأول",
    "10-Samuel2": "صموئيل الثاني",
    "11-Mlokk1": "الملوك الأول",
    "12-Mlokk2": "الملوك الثاني",
    "13-AkhbarAyam1": "أخبار الأيام الأول",
    "14-AkhbarAyam2": "أخبار الأيام الثاني",
    "15-Ezra": "عزرا",
    "16-Na7amya": "نحميا",
    "17-Tobya": "طوبيا",
    "18-Yahodet": "يهوديت",
    "19-Aster": "أستير",
    "20-Ayob": "أيوب",
    "21-Psalms": "المزامير",
    "22-Amsal": "الأمثال",
    "23-Gam3a": "الجامعة",
    "24-NashedElAnshad": "نشيد الأنشاد",
    "25-7ekma": "الحكمة",
    "26-Yasho3EbnSira5": "يشوع بن سيراخ",
    "27-Ash3ya": "أشعياء",
    "28-Armya": "إرميا",
    "29-MarasyArmya": "مراثي إرميا",
    "30-Baroo5": "باروخ",
    "31-Ezkial": "حزقيال",
    "32-Daniel": "دانيال",
    "33-Hosa3": "هوشع",
    "34-Uoyel": "يوئيل",
    "35-Amous": "عاموس",
    "36-Obadiah": "عوبديا",
    "37-Younan": "يونان",
    "38-Mikha": "ميخا",
    "39-Na7oum": "ناحوم",
    "40-Habakouk": "حبقوق",
    "41-Saphnia": "صفنيا",
    "42-Heggi": "حجي",
    "43-Zakaria": "زكريا",
    "44-Malakhy": "ملاخي",
    "45-Makabyeen1": "المكابيين الأول",
    "46-Makabyeen2": "المكابيين الثاني",
}

BOOKS_NEW = {
    "47-Matta": "إنجيل متى",
    "48-Morkos": "إنجيل مرقس",
    "49-Loka": "إنجيل لوقا",
    "50-Yo7ana": "إنجيل يوحنا",
    "51-A3mal": "أعمال الرسل",
    "52-Romia": "رسالة رومية",
    "53-Koronsos1": "كورنثوس الأولى",
    "54-Koronsos2": "كورنثوس الثانية",
    "55-Ghalatia": "غلاطية",
    "56-Afasos": "أفسس",
    "57-Philipy": "فيلبي",
    "58-Kolosy": "كولوسي",
    "59-Tsaloneky1": "تسالونيكي الأولى",
    "60-Tsaloneky2": "تسالونيكي الثانية",
    "61-Timosawes1": "تيموثاوس الأولى",
    "62-Timosawes2": "تيموثاوس الثانية",
    "63-Titues": "تيطس",
    "64-Philimon": "فليمون",
    "65-Abranyen": "العبرانيين",
    "66-Yaquob": "يعقوب",
    "67-Botros1": "بطرس الأولى",
    "68-Botros2": "بطرس الثانية",
    "69-You7ana1": "يوحنا الأولى",
    "70-You7ana2": "يوحنا الثانية",
    "71-You7ana3": "يوحنا الثالثة",
    "72-Yahouza": "يهوذا",
    "73-RoyaYou7ana": "الرؤيا",
}

KHOLAGY_FOLDER_TITLES = {
    "baker": ("k_baker", "خولاجي باكر"),
    "normal": ("k_normal", "خولاجي القداس"),
    "monasbat": ("k_monasbat", "خولاجي المناسبات"),
    "basely": ("k_basely", "الخولاجي الباسيلي"),
    "gergory": ("k_gergory", "الخولاجي الغريغوري"),
}

KHOLAGY_ROOT_GROUPS = [
    ("basel", "ترتيب الخولاجي الباسيلي"),
    ("basil", "ترتيب الخولاجي الباسيلي"),
    ("gergory", "ترتيب الخولاجي الغريغوري"),
    ("hamal", "ترتيب الخولاجي (حمل)"),
    ("mon_", "ترتيب المناسبات"),
    ("st_mary", "ترتيب مدائح العذراء"),
]


# --------------------------------------------------------------------------
# main extraction
# --------------------------------------------------------------------------

def load_corpus(zip_path):
    with zipfile.ZipFile(zip_path) as z:
        name = [n for n in z.namelist() if n.lower().endswith(".txt")][0]
        with z.open(name) as f:
            raw = f.read()
    text = raw.decode("utf-8", "replace")
    return text.split("\n")


def iter_blocks(lines):
    """Yield (path, body_lines) tuples until the raw duplicate Section C."""
    path = None
    body = []
    in_section_c = False
    for line in lines:
        if line.startswith("SECTION C"):
            in_section_c = True
        if in_section_c:
            continue
        if line.startswith("SOURCE: ") or line.startswith("SOURCE PATH: "):
            if path:
                yield path, body
            path = line.split(":", 1)[1].strip()
            body = []
            continue
        if line.startswith("SECTION "):
            continue
        if path is not None:
            body.append(line)
    if path:
        yield path, body


STOPWORDS = set("""في من على الى إلى عن ان أن انه أنه هذا هذه ذلك تلك ثم قد كان كانت يكون تكون
هو هي هم هن نحن انت أنت انتم أنتم الذي التي الذين اللذين ما لا لم لن كل بعض غير بين عند
منذ حتى إذا اذا كما لكن بل ولا وهو وهي قال قالت يقول انه أنه كذلك أيضا أيضاً جدا جداً يوم
اي أي أى به بها له لها لهم فيه فيها عليه عليها منه منها اليه إليه عليها ومع هذا""".split())


def doc_words(body, kind):
    parts = []
    if kind == "bible":
        for ch in body:
            parts.extend(ch.get("v", []))
    else:
        for item in body:
            if isinstance(item, list) and len(item) == 2:
                parts.append(str(item[1]))
            elif isinstance(item, dict):
                for b in item.get("b", []):
                    parts.append(str(b[1]))
    tokens = set()
    for text in parts:
        for w in re.split(r"[^\w\u0600-\u06FF]+", norm_ar(text)):
            if len(w) >= 3 and w not in STOPWORDS and not w.isdigit():
                tokens.add(w)
    return " ".join(sorted(tokens))


KHOLAGY_ROLES = {2: "h", 3: "m", 4: "p", 5: "t", 6: "c", 7: "c", 12: "e"}


def pick_title(rows, cols=(2, 3, 4)):
    for row in rows[:4]:
        for col in cols:
            val = clean_text(row.get(col, ""))
            if not val or re.match(r"^\d+(\.0)?$", val):
                continue
            if 0 < len(val) < 200:
                return val
    return ""


def is_junk_line(line):
    t = line.strip()
    if not t or SEP.match(t):
        return True
    if "{" in t and "}" in t:
        return True
    if "mso-" in t or t.startswith(".") or t.startswith("@page"):
        return True
    if re.fullmatch(r"[\W_]+", t):
        return True
    if t.lower() in ("untitled document", "normal", "body"):
        return True
    return False


def build(zip_path, out_dir):
    lines = load_corpus(zip_path)
    lib = Library(out_dir)
    lib.pending = []

    lib.section("bible", "الكتاب المقدس", "book", "73 سفرًا — العهد القديم والجديد", "#c8a64b")
    lib.group("bible", "old", "العهد القديم", "46 سفرًا بحسب الترتيب القبطي")
    lib.group("bible", "new", "العهد الجديد", "27 سفرًا")

    lib.section("agpeya", "الأجبية", "clock", "صلوات الساعات السبع وصلوات أخرى", "#5b8fb9")
    lib.group("agpeya", "prayers", "صلوات الأجبية", "صلاة باكر حتى صلاة النوم")

    lib.section("kholagy", "الخولاجي", "church", "الخولاجي الباسيلي والغريغوري وترتيب الطقوس", "#b07d4a")
    for key, (gid, title) in KHOLAGY_FOLDER_TITLES.items():
        lib.group("kholagy", gid, title)
    lib.group("kholagy", "k_order_basel", "ترتيب الخولاجي الباسيلي")
    lib.group("kholagy", "k_order_gergory", "ترتيب الخولاجي الغريغوري")
    lib.group("kholagy", "k_order_hamal", "ترتيب الخولاجي (حمل)")
    lib.group("kholagy", "k_order_mon", "ترتيب المناسبات")
    lib.group("kholagy", "k_order_mary", "ترتيب مدائح العذراء")

    lib.section("katamars", "القطمارس", "calendar", "قراءات الأيام والآحاد والصوم الكبير", "#7a9e5f")
    lib.group("katamars", "days", "قطمارس أيام الشهر", "قراءات كل يوم بحسب الشهر القبطي")
    lib.group("katamars", "sundays", "قطمارس الآحاد", "قراءات آحاد الشهر")
    lib.group("katamars", "lent", "الصوم الكبير", "قراءات أيام الصوم الكبير")
    lib.group("katamars", "lent_t", "تفسير قطمارس الصوم الكبير", "شرح القراءات")
    lib.group("katamars", "fifty", "الخمسون المقدسة", "قطمارس الخمسين يومًا")
    lib.group("katamars", "younan", "صوم يونان", "قراءات صوم نينوى")
    lib.group("katamars", "helpers", "ملفات مساعدة", "مزامير وملخصات")

    lib.section("synaxarium", "السنكسار", "star", "سير القديسين والشهداء بحسب أيام السنة القبطية", "#a05a7a")
    for i, m in enumerate(COP_MONTHS, start=1):
        lib.group("synaxarium", f"m{i}", f"شهر {m}")
    lib.group("synaxarium", "special", "المناسبات الخاصة")

    lib.section("psalmody", "التسبحة السنوية", "music", "الهوسات والإبصاليات والذكصولوجيات", "#5f7fb0")
    for gid, gtitle in [
        ("h", "الهوسات"),
        ("o", "الإبصاليات"),
        ("d", "الذكصولوجيات"),
        ("m", "المدائح"),
        ("p", "الطرحات واللبش"),
        ("x", "قطع أخرى"),
    ]:
        lib.group("psalmody", gid, gtitle)

    lib.section("absalmody", "الإبصلمودية", "harp", "إبصلمودية كيهك والهوسات", "#8a6fb0")
    for gid, gtitle in [
        ("h", "الهوسات"),
        ("o", "الإبصاليات"),
        ("d", "الذكصولوجيات"),
        ("m", "المدائح"),
        ("p", "الطرحات واللبش"),
        ("x", "قطع أخرى"),
    ]:
        lib.group("absalmody", gid, gtitle)

    lib.section("sagda", "صلوات السجود", "pray", "صلاة السجدة وصلوات العنصرة", "#c07a5a")
    lib.group("sagda", "intro", "مقدمة صلاة السجدة")
    lib.group("sagda", "sagda", "صلوات السجود")

    lib.section("dallal", "الدلال", "guide", "دلال الطقوس والألحان", "#6f8fa0")
    lib.group("dallal", "dallal", "الدلال")

    lib.section("shawahed", "الشواهد", "search", "شواهد نبوية وموضوعية", "#a08a4a")
    lib.group("shawahed", "shawahed", "الشواهد")

    lib.section("mdaya7", "المدائح", "song", "مدائح القديسين والمناسبات", "#b07090")
    lib.group("mdaya7", "mdaya7", "المدائح")

    lib.section("rites", "الطقوس والصلوات", "cross", "اللقان والطقس السنوي والقنديل", "#7f6a55")
    lib.group("rites", "rites", "طقوس وصلوات")

    lib.section("verses", "آيات مختارة", "heart", "آيات وعبارات للتعزية والتأمل", "#c8a64b")
    lib.group("verses", "verses", "آيات وعبارات")

    seen = set()
    bible_books = defaultdict(list)   # folder -> [(chapter, rows)]
    kholagy_docs = {}                 # code -> (doc_id, title)
    kholagy_index_rows = []           # (path, [(code,title)])

    for path, body in iter_blocks(lines):
        if path in seen:
            continue
        seen.add(path)

        # ---------------- Bible ----------------
        m = re.match(r"assets/mybible/(old|new)/([^/]+)/(\d+)\.(xls|txt)$", path)
        if m:
            testament, book, chapter = m.group(1), m.group(2), int(m.group(3))
            verses = []
            if m.group(4) == "xls":
                cells = []
                for row in parse_xls(body):
                    c = clean_text(row.get(3) or "")
                    if c:
                        cells.append(c)
            else:
                cells = [clean_text(x) for x in body if clean_text(x)]
            for cell in cells:
                if not cell or SEP.match(cell):
                    continue
                vm = re.match(r"^(\d+)\s*[\.\-]?\s*(.*)$", cell, re.S)
                if vm and (not verses or int(vm.group(1)) == verses[-1]["n"] + 1
                           or int(vm.group(1)) <= 200):
                    verses.append({"n": int(vm.group(1)), "t": vm.group(2).strip()})
                elif verses:
                    verses[-1]["t"] = (verses[-1]["t"] + " " + cell).strip()
            if verses:
                bible_books[(testament, book)].append((chapter, verses))
            continue

        # ---------------- kholagy ----------------
        if path.startswith("assets/kholagy/"):
            rel = path[len("assets/kholagy/"):]
            parts = rel.split("/")
            if len(parts) == 1:
                rows = parse_xls(body)
                entries = []
                for row in rows:
                    code = row.get(1, "")
                    title = clean_text(row.get(2, ""))
                    cm = re.match(r"^(\d+)(\.0)?$", (code or "").strip())
                    if cm and title:
                        entries.append((cm.group(1), title))
                if entries:
                    kholagy_index_rows.append((rel, entries))
                continue
            folder = parts[0]
            fname = parts[-1]
            rows = parse_xls(body)
            if not rows:
                continue
            gid, gtitle = KHOLAGY_FOLDER_TITLES.get(folder, ("k_monasbat", "خولاجي المناسبات"))
            title = pick_title(rows) or fname.rsplit(".", 1)[0]
            blocks = xls_to_blocks(rows, skip_cols={1}, roles=KHOLAGY_ROLES, title=title)
            if not blocks:
                continue
            sort_key = (int(re.sub(r"\D", "", fname) or 0), fname)
            did = lib.add_doc("kholagy", gid, title, gtitle, blocks, sort=sort_key)
            for row in rows:
                cm = re.match(r"^(\d+)(\.0)?$", (row.get(1, "") or "").strip())
                if cm:
                    kholagy_docs.setdefault(cm.group(1), (did, title))
            continue

        # ---------------- katamars ----------------
        if path.startswith("assets/katamars/"):
            rel = path[len("assets/katamars/"):]
            parts = rel.split("/")
            KATA_ROLES = {2: "h", 3: "m", 4: "p", 5: "p", 6: "c"}
            if parts[0] in ("KatamarsAyamExcel", "KatamarsA7adExcel") and len(parts) == 3:
                month = int(parts[1]) if parts[1].isdigit() else 0
                day = int(re.sub(r"\D", "", parts[2]) or 0)
                gid = "days" if parts[0] == "KatamarsAyamExcel" else "sundays"
                mname = COP_MONTHS[month - 1] if 1 <= month <= 13 else f"شهر {month}"
                title = f"{mname} — اليوم {day}" if gid == "days" else f"{mname} — الأحد {day}"
                blocks = xls_to_blocks(parse_xls(body), skip_cols={1}, roles=KATA_ROLES)
                if not blocks:
                    continue
                lib.add_doc("katamars", gid, title, "قراءات اليوم", blocks, sort=(month, day))
                continue
            if parts[0] == "KatamarsA7adExcel" and len(parts) == 2:
                day = int(re.sub(r"\D", "", parts[1]) or 0)
                blocks = xls_to_blocks(parse_xls(body), skip_cols={1}, roles=KATA_ROLES)
                if blocks:
                    lib.add_doc("katamars", "sundays", f"الأحد {day}", "قطمارس الآحاد",
                                blocks, sort=(0, day))
                continue
            if parts[0] in ("soomKeber", "younan", "Katamaras7maseen"):
                day = int(re.sub(r"\D", "", parts[-1]) or 0)
                gid = {"soomKeber": "lent", "younan": "younan",
                       "Katamaras7maseen": "fifty"}[parts[0]]
                blocks = xls_to_blocks(parse_xls(body), skip_cols={1}, roles=KATA_ROLES)
                if not blocks:
                    continue
                prefix = {"soomKeber": "اليوم", "younan": "يوم", "Katamaras7maseen": "اليوم"}[parts[0]]
                lib.add_doc("katamars", gid, f"{prefix} {day}", "", blocks, sort=(0, day))
                continue
            if parts[0] == "KatamrasSoomKeberTafser":
                title, secs = parse_orso(body)
                if not secs:
                    continue
                title = title or f"تفسير اليوم {parts[-1].split('.')[0]}"
                lib.add_doc("katamars", "lent_t", title, "تفسير الصوم الكبير",
                            orso_to_blocks(secs, drop_title=True, title=title),
                            sort=(0, int(re.sub(r"\D", "", parts[-1]) or 0)))
                continue
            if len(parts) == 1:
                title, secs = parse_orso(body)
                if not secs:
                    continue
                lib.add_doc("katamars", "helpers", title or parts[0], "ملف مساعد",
                            orso_to_blocks(secs, drop_title=True, title=title))
                continue
            continue

        # ---------------- synaxarium ----------------
        if path.startswith("assets/sanksar2/"):
            rel = path[len("assets/sanksar2/"):]
            parts = rel.split("/")
            title, secs = parse_orso(body)
            if not secs:
                continue
            title = re.sub(r"\s+", " ", title).strip() or rel
            if parts[0].isdigit():
                month = int(parts[0])
                gid = f"m{month}" if 1 <= month <= 13 else "special"
            else:
                gid = "special"
            sort = (0, int(re.sub(r"\D", "", parts[-1]) or 0), rel)
            lib.add_doc("synaxarium", gid, title, "",
                        orso_to_blocks(secs, drop_title=True, title=title), sort=sort)
            continue

        # ---------------- absalmody / psalmody ----------------
        if path.startswith("assets/absalmody/") or path.startswith("assets/psalmodySanawy/"):
            sec = "absalmody" if "absalmody" in path else "psalmody"
            fname = path.rsplit("/", 1)[-1]
            num = int(re.sub(r"\D", "", fname) or 0)
            rows = parse_xls(body)
            title = pick_title(rows)
            if not title:
                continue
            gid = classify_hymn(title)
            roles = {2: "h", 3: "m", 5: "p", 6: "t", 7: "c"} if sec == "absalmody" else None
            blocks = xls_to_blocks(rows, skip_cols={1}, roles=roles, title=title)
            lib.add_doc(sec, gid, title, "", blocks, sort=num)
            continue

        if path.startswith("assets/sagda/"):
            fname = path.rsplit("/", 1)[-1]
            num = int(re.sub(r"\D", "", fname) or 0)
            rows = parse_xls(body)
            title = pick_title(rows) or f"سجدة {num}"
            blocks = xls_to_blocks(rows, skip_cols={1}, roles={2: "h", 3: "m", 4: "p"},
                                   title=title)
            lib.add_doc("sagda", "sagda", title, f"سجدة {num}", blocks, sort=num)
            continue

        # ---------------- shawahed ----------------
        if path.startswith("assets/shawahed/"):
            fname = path.rsplit("/", 1)[-1]
            num = int(re.sub(r"\D", "", fname) or 0)
            rows = parse_xls(body)
            title = ""
            for row in rows:
                t = clean_text(row.get(3, ""))
                if t and not re.match(r"^\d+(\.0)?$", t):
                    title = t
                    break
            title = title or f"شواهد {num}"
            blocks = xls_to_blocks(rows, skip_cols={1, 2},
                                   roles={3: "h", 4: "m", 5: "m", 6: "m", 7: "m"}, title=title)
            lib.add_doc("shawahed", "shawahed", title, f"شواهد {num}", blocks, sort=num)
            continue

        # ---------------- dallal ----------------
        if path.startswith("assets/dallal/"):
            title, secs = parse_orso(body)
            if not secs:
                continue
            title = title or path.rsplit("/", 1)[-1]
            lib.add_doc("dallal", "dallal", title, "دلال",
                        orso_to_blocks(secs, drop_title=True, title=title))
            continue

        # ---------------- mdaya7 ----------------
        if path.startswith("assets/mdaya7/"):
            text_lines = [ln for ln in html_to_text("\n".join(body)) if not is_junk_line(ln)]
            if not text_lines:
                continue
            title = text_lines[0][:140]
            blocks = [["p", ln] for ln in text_lines[1:] if ln != title]
            lib.add_doc("mdaya7", "mdaya7", title, "", blocks)
            continue

        # ---------------- misc rites ----------------
        if path == "assets/agypa.orso":
            title, secs = parse_orso(body)
            if not secs:
                continue
            blocks = orso_to_blocks(secs)
            toc = []
            for s in secs:
                t = s.get("t")
                if t and (not toc or toc[-1] != t):
                    toc.append(t)
            lib.add_doc("agpeya", "prayers", "الأجبية", "صلوات الساعات وصلوات أخرى",
                        blocks, toc=toc)
            continue

        if path in ("assets/lakan.orso", "assets/kism.orso", "assets/kandil.orso",
                    "assets/taks.orso", "assets/sagda.orso"):
            title, secs = parse_orso(body)
            if not secs:
                continue
            if path.endswith("sagda.orso"):
                sec, gid = "sagda", "intro"
            else:
                sec, gid = "rites", "rites"
            lib.add_doc(sec, gid, title or path, "",
                        orso_to_blocks(secs, drop_title=False, title=title))
            continue

        # ---------------- selected verses ----------------
        if path == "assets/random.xls":
            rows = parse_xls(body)
            quotes = []
            for row in rows:
                t = clean_text(row.get(1, ""))
                if t:
                    quotes.append(t)
            chunk = 80
            for i in range(0, len(quotes), chunk):
                part = quotes[i:i + chunk]
                blocks = [["q", q] for q in part]
                lib.add_doc("verses", "verses", f"آيات مختارة {i // chunk + 1}",
                            f"{i + 1} - {i + len(part)}", blocks, sort=i // chunk)
            continue

    # ---------- Bible assembly ----------
    for (testament, book), chapters in sorted(bible_books.items()):
        name = (BOOKS_OLD if testament == "old" else BOOKS_NEW).get(book, book)
        chapters.sort(key=lambda c: c[0])
        chs = [{"n": n, "v": [v["t"] for v in verses]} for n, verses in chapters]
        gid = "old" if testament == "old" else "new"
        lib.add_doc("bible", gid, name, f"{len(chs)} إصحاحًا", chs, kind="bible",
                    sort=(0, list((BOOKS_OLD if testament == "old" else BOOKS_NEW)).index(book)))

    # ---------- kholagy order indexes ----------
    def order_group(name):
        n = name.lower()
        if n.startswith(("basel", "basil")):
            return "k_order_basel"
        if n.startswith("gergory"):
            return "k_order_gergory"
        if n.startswith("hamal"):
            return "k_order_hamal"
        if n.startswith("st_mary"):
            return "k_order_mary"
        return "k_order_mon"

    pretty = {
        "29": "٢٩ من الشهر", "basic": "الطقس الأساسي", "milad": "الميلاد",
        "ghetas": "الغطاس", "khetan": "الختان", "baramon_milad": "برامون الميلاد",
        "baramon_ghetas": "برامون الغطاس", "nayrouz": "النيروز", "kyama": "القيامة",
        "shaaneen": "الشعانين", "sabt_laazer": "سبت لعازر", "sabt_el_farah": "سبت الفرح",
        "salib": "الصليب", "tagali": "التجلي", "helol": "الحلول", "soud": "الصعود",
        "rosol": "الرسل", "3id_rosol": "عيد الرسل", "kana_elgalil": "عرس قانا الجليل",
        "bashara": "البشارة", "el_aahd": "العهد", "Kiak": "كيهك", "Kabir": "الصوم الكبير",
        "Khatam": "الختام", "Masr": "المصريين", "Younah": "يونان", "sanawy": "سنوي",
        "Mary": "العذراء", "5etan": "الختان", "Hakal": "الهيكل", "after_ghetas": "بعد الغطاس",
        "days2_Fatar": "أيام الفطر", "week": "الأسبوع", "Sun": "الأحد", "Sat": "السبت",
        "others": "أخرى", "refaa": "الرفاع", "before_helol": "قبل الحلول",
        "before_soud": "قبل الصعود", "Masr_before_helol": "قبل الحلول",
    }

    def pretty_name(fname):
        base = fname.rsplit(".", 1)[0]
        parts = re.split(r"[_\-]", base)
        words = []
        for p in parts:
            if p in ("basely", "basily", "gergory", "hamal", "mon", "st", "mary"):
                continue
            words.append(pretty.get(p, p))
        txt = " - ".join(w for w in words if w)
        return txt or base

    for rel, entries in kholagy_index_rows:
        gid = order_group(rel)
        title = pretty_name(rel)
        blocks = [["h", "ترتيب الخولاجي"]]
        for code, t in entries:
            target = kholagy_docs.get(code)
            if target:
                blocks.append(["l", t, target[0]])
            else:
                blocks.append(["p", t])
        lib.add_doc("kholagy", gid, title, f"{len(entries)} قطعة", blocks,
                    sort=rel)

    cat, chars = lib.flush()
    return cat, chars


# --------------------------------------------------------------------------
# row/orso -> block conversion
# --------------------------------------------------------------------------

def xls_to_blocks(rows, skip_cols=(), roles=None, title=""):
    """Convert spreadsheet rows into a list of [type, text] blocks.

    roles maps column number -> block type ('h' heading, 'm' meta/rubric,
    'p' paragraph, 't' transliteration, 'c' coptic, 'e' english).
    """
    roles = roles or {}
    blocks = []
    seen_texts = []
    ntitle = norm_ar(title)

    def push(kind, text):
        if not text:
            return
        if ntitle and norm_ar(text) == ntitle:
            return
        if blocks and blocks[-1][0] == kind and blocks[-1][1] == text:
            return
        if kind == "br" and (not blocks or blocks[-1][0] == "br"):
            return
        blocks.append([kind, text])

    for row in rows:
        arabic_seen = 0
        for col in sorted(row):
            if col in skip_cols:
                continue
            val = clean_text(row[col])
            if not val or re.match(r"^\d+(\.0)?$", val):
                continue
            kind = roles.get(col)
            if kind is None:
                if is_coptic_line(val):
                    kind = "c"
                elif is_arabic(val):
                    kind = "p"
                else:
                    kind = "e"
            if kind == "c" and not is_coptic_line(val) and not re.search(r"[A-Za-z]", val):
                kind = "p"
            push(kind, val)
        push("br", "")
    while blocks and blocks[-1][0] == "br":
        blocks.pop()
    return blocks


def orso_to_blocks(sections, drop_title=False, title=""):
    blocks = []
    title_set = {norm_ar(sec.get("t", "")) for sec in sections if sec.get("t")}
    ntitle = norm_ar(title)

    def push(kind, text):
        if not text:
            return
        n = norm_ar(text)
        if ntitle and n == ntitle:
            return
        if kind == "p" and n in title_set:
            return
        if kind == "p" and (len(n) < 2 or not re.search(r"[\w\u0600-\u06FF]", n)):
            return
        if blocks and blocks[-1][0] == kind and blocks[-1][1] == text:
            return
        if kind == "br" and (not blocks or blocks[-1][0] == "br"):
            return
        blocks.append([kind, text])

    for i, sec in enumerate(sections):
        t = clean_text(sec.get("t", ""))
        if t and not (drop_title and i == 0):
            push("h", t)
        for p in sec.get("p", []):
            p = clean_text(p)
            if not p or set(p) <= set("+ "):
                continue
            if p.startswith("**"):
                push("h", p.lstrip("* ").strip())
            elif p.startswith("+") and len(p) < 120:
                push("h", p.lstrip("+ ").strip())
            elif is_coptic_line(p):
                push("c", p)
            else:
                push("p", p)
        push("br", "")
    while blocks and blocks[-1][0] == "br":
        blocks.pop()
    return blocks


def classify_hymn(title):
    t = norm_ar(title)
    if "ذكصولوجي" in t:
        return "d"
    if "ابصال" in t or "ابصالي" in t:
        return "o"
    if "هوس" in t:
        return "h"
    if "مديح" in t or "تمجيد" in t:
        return "m"
    if "طرح" in t or "لبش" in t:
        return "p"
    return "x"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--zip", default="KENOZ_All_Extracted_Texts_Unified.zip")
    ap.add_argument("--out", default="app/src/main/assets/content")
    ap.add_argument("--clean", action="store_true")
    args = ap.parse_args()

    if args.clean and os.path.isdir(args.out):
        shutil.rmtree(args.out)

    cat, chars = build(args.zip, args.out)
    size = 0
    files = 0
    for root, _dirs, names in os.walk(args.out):
        for n in names:
            size += os.path.getsize(os.path.join(root, n))
            files += 1
    print("sections:", len(cat["sections"]))
    for s in cat["sections"]:
        print(f"  {s['id']:12s} {s['count']:5d} docs  {s['title']}")
    print("documents:", cat["docs"], "files:", files)
    print("bytes:", size, f"({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
