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
    # Build browseable indexes and run a complete structural/text-quality audit.
    import hashlib
    import unicodedata
    from collections import defaultdict
    index_dir = args.output / "indexes"
    index_dir.mkdir(parents=True, exist_ok=True)
    doc_by_id = {d["id"]: d for d in documents}
    seen_ids: set[str] = set()
    duplicate_body_map: dict[str, list[str]] = defaultdict(list)
    duplicate_title_map: dict[str, list[str]] = defaultdict(list)
    flag_map: dict[str, list[str]] = defaultdict(list)
    quality_counts = {"emptyTexts": 0, "replacementCharacterDocuments": 0,
        "suspectedMojibakeDocuments": 0, "placeholderDocuments": 0,
        "shortTextDocuments": 0, "controlCharacterDocuments": 0}
    structural_errors: list[str] = []
    audited_chars = 0
    records_read = 0
    mojibake_markers = ("Ã", "Â", "â€", "ï»¿", "ðŸ", "â€™", "Ð", "Ñ")
    placeholder_markers = ("TODO", "FIXME", "LOREM IPSUM", "CONTENT MISSING",
        "ERROR DECODING", "[OBJECT OBJECT]", "PLACEHOLDER TEXT")
    def title_key(value: str) -> str:
        value = unicodedata.normalize("NFKC", str(value or "")).casefold()
        value = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", value)
        value = value.translate(str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي"}))
        return re.sub(r"\s+", " ", value).strip()
    for chunk_meta in chunks:
        chunk_path = args.output / chunk_meta["file"]
        local_count = 0
        with chunk_path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, 1):
                if not raw_line.strip():
                    continue
                try:
                    record = json.loads(raw_line)
                except json.JSONDecodeError as exc:
                    structural_errors.append(f"{chunk_meta['file']}:{line_number}: invalid JSON ({exc.msg})")
                    continue
                records_read += 1
                local_count += 1
                doc_id = str(record.get("id", ""))
                if not doc_id:
                    structural_errors.append(f"{chunk_meta['file']}:{line_number}: missing id")
                    continue
                if doc_id in seen_ids:
                    structural_errors.append(f"{chunk_meta['file']}:{line_number}: duplicate id {doc_id}")
                seen_ids.add(doc_id)
                meta = doc_by_id.get(doc_id)
                if meta is None:
                    structural_errors.append(f"{chunk_meta['file']}:{line_number}: id absent from manifest: {doc_id}")
                    continue
                if record.get("chunk") != chunk_meta["file"] or meta.get("chunk") != chunk_meta["file"]:
                    structural_errors.append(f"{doc_id}: chunk reference mismatch")
                body = str(record.get("text") or "")
                title = str(record.get("title") or meta.get("title") or "")
                path = str(record.get("path") or meta.get("path") or "")
                audited_chars += len(body)
                if not body.strip():
                    quality_counts["emptyTexts"] += 1
                    flag_map[doc_id].append("النص فارغ")
                if "\ufffd" in body or "\ufffd" in title or "\ufffd" in path:
                    quality_counts["replacementCharacterDocuments"] += 1
                    flag_map[doc_id].append("يوجد محرف بديل قد يشير إلى مشكلة ترميز")
                if any(marker in body for marker in mojibake_markers):
                    quality_counts["suspectedMojibakeDocuments"] += 1
                    flag_map[doc_id].append("توجد علامة محتملة على فساد الترميز")
                if "\x00" in body or any(ord(ch) < 32 and ch not in "\n\r\t" for ch in body):
                    quality_counts["controlCharacterDocuments"] += 1
                    flag_map[doc_id].append("توجد محارف تحكم غير معتادة")
                upper_body = body.upper()
                if any(marker in upper_body for marker in placeholder_markers):
                    quality_counts["placeholderDocuments"] += 1
                    flag_map[doc_id].append("توجد عبارة قد تكون مؤقتة أو غير مكتملة")
                if 0 < len(body.strip()) < 12:
                    quality_counts["shortTextDocuments"] += 1
                    flag_map[doc_id].append("النص قصير جدًا ويستحق التحقق من اكتماله")
                if len(title) > 180:
                    flag_map[doc_id].append("العنوان طويل بشكل غير معتاد")
                if not title.strip():
                    flag_map[doc_id].append("العنوان مفقود")
                normalized_body = re.sub(r"\s+", " ", unicodedata.normalize("NFC", body)).strip()
                if normalized_body:
                    digest = hashlib.sha256(normalized_body.encode("utf-8")).hexdigest()
                    duplicate_body_map[digest].append(doc_id)
                key = title_key(title)
                if key:
                    duplicate_title_map[key].append(doc_id)
        if local_count != chunk_meta["records"]:
            structural_errors.append(f"{chunk_meta['file']}: expected {chunk_meta['records']} records, read {local_count}")
    missing_ids = sorted(set(doc_by_id) - seen_ids)
    if missing_ids:
        structural_errors.append(f"{len(missing_ids)} manifest documents missing from chunks")
    if records_read != len(documents):
        structural_errors.append(f"record count mismatch: manifest={len(documents)}, chunks={records_read}")
    if structural_errors:
        raise SystemExit("Corpus structural validation failed:\n" + "\n".join(structural_errors[:30]))
    duplicate_body_groups = []
    for digest, ids in duplicate_body_map.items():
        if len(ids) > 1:
            ordered_ids = sorted(ids)
            duplicate_body_groups.append({"hash": digest, "count": len(ordered_ids),
                "ids": ordered_ids, "titles": [doc_by_id[i]["title"] for i in ordered_ids]})
            for doc_id in ordered_ids:
                others = [other for other in ordered_ids if other != doc_id]
                flag_map[doc_id].append("النص مطابق بالكامل لمصدر آخر: " + "، ".join(others[:5]) + ("…" if len(others) > 5 else ""))
    duplicate_body_groups.sort(key=lambda item: (-item["count"], item["titles"][0]))
    duplicate_title_groups = []
    for key, ids in duplicate_title_map.items():
        unique_ids = sorted(set(ids))
        if len(unique_ids) > 1:
            duplicate_title_groups.append({"normalizedTitle": key, "count": len(unique_ids),
                "ids": unique_ids, "titles": [doc_by_id[i]["title"] for i in unique_ids],
                "paths": [doc_by_id[i]["path"] for i in unique_ids]})
            for doc_id in unique_ids:
                flag_map[doc_id].append("العنوان يتكرر في أكثر من سجل؛ يلزم التأكد من اختلاف المحتوى")
    duplicate_title_groups.sort(key=lambda item: (-item["count"], item["normalizedTitle"]))
    title_index = sorted(
        [{"id": d["id"], "title": d["title"], "path": d["path"], "category": d["category"], "chunk": d["chunk"]} for d in documents],
        key=lambda item: (title_key(item["title"]), item["path"].casefold(), item["id"]))
    source_index = sorted(
        [{"id": d["id"], "title": d["title"], "path": d["path"], "category": d["category"], "chunk": d["chunk"]} for d in documents],
        key=lambda item: (item["path"].casefold(), title_key(item["title"]), item["id"]))
    category_map: dict[str, list[str]] = defaultdict(list)
    for d in documents:
        category_map[d["category"]].append(d["id"])
    category_index = {"categories": [
        {"id": category, "label": CATEGORY_LABELS.get(category, "مصدر آخر"), "count": len(ids), "ids": sorted(ids)}
        for category, ids in sorted(category_map.items(), key=lambda pair: CATEGORY_LABELS.get(pair[0], pair[0]))]}
    review_index = []
    for doc_id, flags in flag_map.items():
        if flags:
            meta = doc_by_id[doc_id]
            review_index.append({"id": doc_id, "title": meta["title"], "path": meta["path"],
                "category": meta["category"], "chunk": meta["chunk"], "flags": sorted(set(flags))})
    review_index.sort(key=lambda item: (title_key(item["title"]), item["path"].casefold()))
    quality_summary = {
        "documents": len(documents), "recordsRead": records_read, "chunks": len(chunks),
        "textCharacters": audited_chars, "emptyTexts": quality_counts["emptyTexts"],
        "duplicateBodyGroups": len(duplicate_body_groups),
        "documentsInDuplicateBodyGroups": sum(g["count"] for g in duplicate_body_groups),
        "duplicateTitleGroups": len(duplicate_title_groups), "documentsWithFlags": len(review_index),
        "replacementCharacterDocuments": quality_counts["replacementCharacterDocuments"],
        "suspectedMojibakeDocuments": quality_counts["suspectedMojibakeDocuments"],
        "placeholderDocuments": quality_counts["placeholderDocuments"],
        "shortTextDocuments": quality_counts["shortTextDocuments"],
        "controlCharacterDocuments": quality_counts["controlCharacterDocuments"],
        "structuralChecksPassed": True}
    checks = [
        {"name": "كل سجل في JSONL صالح", "passed": True, "checked": records_read},
        {"name": "كل سجل له معرّف فريد", "passed": len(seen_ids) == len(documents), "checked": len(seen_ids)},
        {"name": "كل سجل مرتبط بملف الجزء الصحيح", "passed": True, "checked": records_read},
        {"name": "كل سجلات الفهرس موجودة في أجزاء المحتوى", "passed": records_read == len(documents), "checked": records_read},
        {"name": "البحث عن النصوص الفارغة", "passed": quality_summary["emptyTexts"] == 0, "found": quality_summary["emptyTexts"]},
        {"name": "البحث عن محارف بديلة", "passed": quality_summary["replacementCharacterDocuments"] == 0, "found": quality_summary["replacementCharacterDocuments"]},
        {"name": "البحث عن علامات فساد الترميز المحتملة", "passed": quality_summary["suspectedMojibakeDocuments"] == 0, "found": quality_summary["suspectedMojibakeDocuments"]},
        {"name": "مراجعة النصوص المتطابقة بالكامل", "passed": len(duplicate_body_groups) == 0, "foundGroups": len(duplicate_body_groups)},
        {"name": "مراجعة العناوين المتكررة", "passed": len(duplicate_title_groups) == 0, "foundGroups": len(duplicate_title_groups)}]
    index_files = {"byTitle": "indexes/by-title.json", "bySource": "indexes/by-source.json",
        "byCategory": "indexes/by-category.json", "review": "indexes/review-index.json",
        "qualityReport": "indexes/quality-report.json"}
    for filename, payload in [
        ("by-title.json", title_index), ("by-source.json", source_index),
        ("by-category.json", category_index), ("review-index.json", review_index),
        ("quality-report.json", {"app": "KENOZ", "version": 1, "summary": quality_summary,
            "checks": checks, "duplicateBodyGroups": duplicate_body_groups,
            "duplicateTitleGroups": duplicate_title_groups, "reviewItems": review_index})]:
        (index_dir / filename).write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
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
        "qualitySummary": quality_summary,
        "indexFiles": index_files,
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
    report.extend([
        f"Automated audit records read: {quality_summary['recordsRead']}",
        f"Documents flagged for review: {quality_summary['documentsWithFlags']}",
        f"Exact duplicate-text groups: {quality_summary['duplicateBodyGroups']}",
        f"Duplicate-title groups: {quality_summary['duplicateTitleGroups']}",
        f"Possible encoding issues: {quality_summary['suspectedMojibakeDocuments']}",
        f"Replacement-character documents: {quality_summary['replacementCharacterDocuments']}",
        "Indexes: indexes/by-title.json, indexes/by-source.json, indexes/by-category.json",
        "Quality report: indexes/quality-report.json",
        "Automated flags are review leads, not proof of liturgical error.",
    ])
    (args.output / "REPORT.txt").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n".join(report))

if __name__ == "__main__":
    main()
