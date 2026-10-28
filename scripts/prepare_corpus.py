#!/usr/bin/env python3
"""Prepare the unified KENOZ corpus into small offline-searchable JSONL chunks."""
from __future__ import annotations
import argparse
import json
import re
import shutil
from pathlib import Path, PurePosixPath

SOURCE_RE = re.compile(r"^\s*SOURCE(?:\s+PATH)?:\s*(.+?)\s*$")
SECTION_RE = re.compile(r"^\s*SECTION\s+([A-D])\s*[—-]\s*(.*?)\s*$", re.I)
DIVIDER_RE = re.compile(r"^\s*(?:[=#*_\-]\s*){12,}$")
TITLE_RE = re.compile(r"(?m)^\s*TITLE:\s*(.+?)\s*$")
COLUMN_TITLE_RE = re.compile(r"(?m)^\s*\[COLUMN\s+2\]\s*(.+?)\s*$")

SECTION_LABELS = {
    "A": "المصادر المستخرجة من XLS وORSO",
    "B": "النصوص المقروءة من ملفات التطبيق",
    "C": "الأصول النصية الإضافية",
    "D": "ملخص الاستخراج ومعلومات المصدر",
}
CATEGORY_LABELS = {
    "all": "كل المحتوى", "bible": "الكتاب المقدس", "agpeya": "الأجبية",
    "kholagy": "الخولاجي والقداس", "katamars": "القطمارس",
    "synaxarium": "السنكسار", "psalmody": "الإبصلمودية والتسبحة",
    "dallal": "الدلال والشواهد", "prayers": "صلوات وطقوس أخرى",
    "hymns": "الألحان", "excel": "مصادر XLS", "orso": "مصادر ORSO",
    "html": "ملفات HTML", "other": "مصادر أخرى", "meta": "معلومات المجموعة",
}

def category_for(path: str, section: str) -> str:
    p = path.lower().replace("\\", "/")
    if any(k in p for k in ("agypa", "agpeya", "agpeia", "agpe")):
        return "agpeya"
    if any(k in p for k in ("kholagy", "kholagi", "kholog", "liturgy", "mass_prayer")):
        return "kholagy"
    if any(k in p for k in ("katamar", "daily_katamars", "katamars", "katamer")):
        return "katamars"
    if any(k in p for k in ("sanksar", "synaxarium", "synaxar", "seneksar")):
        return "synaxarium"
    if any(k in p for k in ("absalmody", "psalmody", "tasbeha", "almody", "doxtologi")):
        return "psalmody"
    if "dallal" in p or "shawahed" in p or "shawahid" in p:
        return "dallal"
    if any(k in p for k in ("bible", "/bible", "svd/", "old_testament", "new_testament", "gospel", "psalms", "injeel", "engil")):
        return "bible"
    if any(k in p for k in ("hymn", "melody", "hazzat", "hazz", "chant")):
        return "hymns"
    if any(k in p for k in ("prostration", "metania", "sajda", "lakan", "lakkan", "prayer", "prayers", "agpeya")):
        return "prayers"
    ext = PurePosixPath(p).suffix
    if ext == ".xls":
        return "excel"
    if ext == ".orso":
        return "orso"
    if ext in (".htm", ".html"):
        return "html"
    return "other"

def source_kind(path: str) -> str:
    ext = PurePosixPath(path.lower()).suffix
    return {".xls": "XLS", ".orso": "ORSO", ".html": "HTML", ".htm": "HTML",
            ".xml": "XML", ".sql": "SQL", ".json": "JSON"}.get(ext, "TEXT")

def trim_source_edges(lines: list[str]) -> str:
    start, end = 0, len(lines)
    while start < end and (not lines[start].strip() or DIVIDER_RE.match(lines[start])):
        start += 1
    while end > start and (not lines[end-1].strip() or DIVIDER_RE.match(lines[end-1])):
        end -= 1
    return "\n".join(lines[start:end]).strip()

def title_for(path: str, body: str) -> str:
    m = TITLE_RE.search(body)
    if m and m.group(1).strip():
        return m.group(1).strip().lstrip("\ufeff")
    m = COLUMN_TITLE_RE.search(body)
    if m and m.group(1).strip():
        return m.group(1).strip().lstrip("# \ufeff")
    name = PurePosixPath(path.replace("\\", "/")).name or path
    name = re.sub(r"\.(xls|orso|html?|xml|sql|json|txt)$", "", name, flags=re.I)
    name = name.replace("_", " ").replace("-", " ").strip()
    return name or "نص كنسي"

def preview_for(body: str, limit: int = 240) -> str:
    parts = []
    for line in body.splitlines():
        line = line.strip()
        if not line or DIVIDER_RE.match(line) or line.startswith("TITLE:"):
            continue
        parts.append(line)
        if sum(len(x) for x in parts) >= limit:
            break
    return " ".join(parts)[:limit]

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--chunk-bytes", type=int, default=1_800_000)
    args = parser.parse_args()
    if not args.input.is_file():
        raise SystemExit(f"Input corpus not found: {args.input}")
    if args.output.exists():
        shutil.rmtree(args.output)
    args.output.mkdir(parents=True, exist_ok=True)

    documents: list[dict] = []
    chunks: list[dict] = []
    meta_lines: list[str] = []
    current_source = None
    current_section = "معلومات المجموعة"
    current_section_code = ""
    current_lines: list[str] = []
    chunk_buffer: list[str] = []
    chunk_size = 0
    chunk_index = 0
    total_body_chars = 0

    def write_chunk() -> None:
        nonlocal chunk_buffer, chunk_size, chunk_index
        if not chunk_buffer:
            return
        chunk_index += 1
        filename = f"chunk-{chunk_index:04d}.jsonl"
        dest = args.output / filename
        payload = "".join(chunk_buffer)
        dest.write_text(payload, encoding="utf-8", newline="\n")
        chunks.append({"file": filename, "bytes": dest.stat().st_size,
                       "records": sum(1 for _ in chunk_buffer)})
        chunk_buffer = []
        chunk_size = 0

    def add_document(path: str, section: str, section_code: str, body: str) -> None:
        nonlocal chunk_size, total_body_chars
        body = body.strip()
        if not body and path not in ("KENOZ master notes",):
            return
        number = len(documents) + 1
        doc_id = f"{number:06d}"
        category = category_for(path, section)
        title = title_for(path, body)
        kind = source_kind(path)
        chunk_file = f"chunk-{chunk_index + 1:04d}.jsonl"
        record = {"id": doc_id, "title": title, "path": path, "section": section,
                  "category": category, "kind": kind, "text": body}
        serialized = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        bytes_len = len(serialized.encode("utf-8"))
        if chunk_buffer and chunk_size + bytes_len > args.chunk_bytes:
            write_chunk()
            chunk_file = f"chunk-{chunk_index + 1:04d}.jsonl"
        record["chunk"] = chunk_file
        serialized = json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n"
        bytes_len = len(serialized.encode("utf-8"))
        chunk_buffer.append(serialized)
        chunk_size += bytes_len
        total_body_chars += len(body)
        documents.append({
            "id": doc_id, "title": title, "path": path, "section": section,
            "sectionCode": section_code, "category": category,
            "categoryLabel": CATEGORY_LABELS.get(category, "مصدر آخر"),
            "kind": kind, "chunk": chunk_file, "chars": len(body),
            "preview": preview_for(body)
        })

    def flush_source() -> None:
        nonlocal current_source, current_lines
        if current_source is not None:
            body = trim_source_edges(current_lines)
            add_document(current_source, current_section, current_section_code, body)
        current_source = None
        current_lines = []

    def flush_meta() -> None:
        nonlocal meta_lines
        useful = [x for x in meta_lines if x.strip() and not DIVIDER_RE.match(x)]
        if useful:
            body = "\n".join(useful).strip()
            add_document("KENOZ master notes", "معلومات المجموعة", "",
                         "ملاحظات ومقدمات من الملف الموحد:\n\n" + body)
        meta_lines = []

    with args.input.open("r", encoding="utf-8", errors="replace", newline=None) as src:
        for raw in src:
            line = raw.rstrip("\r\n")
            sec = SECTION_RE.match(line)
            if sec:
                flush_source()
                current_section_code = sec.group(1).upper()
                current_section = SECTION_LABELS.get(current_section_code, sec.group(2).strip())
                if line.strip():
                    meta_lines.append(line)
                continue
            found = SOURCE_RE.match(line)
            if found:
                if current_source is not None:
                    flush_source()
                if meta_lines:
                    flush_meta()
                current_source = found.group(1).strip()
                current_lines = []
                continue
            if current_source is not None:
                current_lines.append(line)
            else:
                if line.strip() and not DIVIDER_RE.match(line):
                    meta_lines.append(line)
    flush_source()
    flush_meta()
    write_chunk()

    if not documents or not chunks:
        raise SystemExit("No source documents were generated from the master corpus.")
    manifest = {
        "app": "KENOZ",
        "version": 1,
        "source": args.input.name,
        "offline": True,
        "documentCount": len(documents),
        "chunkCount": len(chunks),
        "textCharacters": total_body_chars,
        "categoryLabels": CATEGORY_LABELS,
        "categories": {key: sum(1 for d in documents if d["category"] == key)
                       for key in sorted(set(d["category"] for d in documents))},
        "chunks": chunks,
        "documents": documents,
    }
    (args.output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    report = [
        "KENOZ corpus preparation report",
        f"Input: {args.input.name}",
        f"Documents: {len(documents)}",
        f"Chunks: {len(chunks)}",
        f"Text characters: {total_body_chars}",
        f"Generated directory: {args.output}",
        "Content groups were retained as separate records; extraction-stage duplicates may remain.",
    ]
    (args.output / "REPORT.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))

if __name__ == "__main__":
    main()
