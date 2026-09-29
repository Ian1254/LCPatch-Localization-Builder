#!/usr/bin/env python3
"""Merge a same-version JP mobile language pack with LLC translations.

The baseline ZIP must contain LocalizeTemp_jp/JP_*.json. The LLC ZIP must
contain LimbusCompany_Data/Lang/LLC_zh-CN/*.json. Unknown matches are reported
and never guessed. The output uses Localize/jp/JP_*.json for LCPatch import.
"""
import argparse
import collections
import hashlib
import json
import re
import zipfile
from pathlib import Path

BASE_PREFIX = "LocalizeTemp_jp/"
LLC_PREFIX = "LimbusCompany_Data/Lang/LLC_zh-CN/"
OUTPUT_PREFIX = "Localize/jp/"
TEXT_FIELDS = {
    "content", "desc", "description", "title", "name", "teller", "nickName",
    "dlg", "dialog", "summary", "place", "flavor", "displayName", "simpleDesc",
    "songWriter", "behaveDesc", "eventDesc", "successDesc", "failureDesc",
    "prevDesc", "text", "subDesc", "nameWithTitle", "clue", "statText",
    "panicName", "panicDescription", "lowMoraleDescription", "relatedChapterText",
    "speaker", "message", "messageDesc", "abName", "story", "shortName",
    "longName", "chaptertitle", "parttitle", "chapter", "company", "area",
    "teacher", "specialName", "skinItemTitle", "skinItemDesc", "abnormalityName",
    "openCondition", "openConditionNumber", "rawDesc", "variation", "variation2",
    "add", "min", "askLevelUp",
}
TEXT_LIST_FIELDS = {"result", "texts"}
DELTA_SUFFIX = re.compile(r"(?:[-_](?:a\d+c\d+p\d+|walpu\d+|\d+))$", re.I)


def load_json(raw, name):
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError(f"Invalid JSON: {name}") from exc
    if not isinstance(value, dict) or (value and not isinstance(value.get("dataList"), list)):
        raise ValueError(f"Missing dataList array: {name}")
    return value


def merge_value(base, source, stats):
    """Copy display strings only, keeping IDs, model codes and game metadata."""
    if isinstance(base, dict) and isinstance(source, dict):
        for key, value in source.items():
            if key in TEXT_FIELDS and isinstance(value, str) and isinstance(base.get(key), str):
                if base[key] != value:
                    base[key] = value
                    stats["text_fields_changed"] += 1
            elif key in TEXT_LIST_FIELDS and isinstance(value, list) and isinstance(base.get(key), list) and len(value) == len(base[key]) and all(isinstance(v, str) for v in value + base[key]):
                if base[key] != value:
                    base[key] = value
                    stats["text_lists_changed"] += 1
            elif key.startswith("goalDescription") and isinstance(value, str) and isinstance(base.get(key), str):
                if base[key] != value:
                    base[key] = value
                    stats["text_fields_changed"] += 1
            elif key in base and isinstance(value, (list, dict)):
                merge_value(base[key], value, stats)
    elif isinstance(base, list) and isinstance(source, list):
        if len(base) == len(source) and all(
            not isinstance(a, dict) or not isinstance(b, dict)
            or a.get("id") == b.get("id") for a, b in zip(base, source)
        ):
            for a, b in zip(base, source):
                merge_value(a, b, stats)
        elif source:
            stats["nested_shape_mismatch"] += 1


def merge_rows(base, source, stats):
    if not base or not source:
        stats["empty_files_preserved"] += 1
        return False
    rows = base["dataList"]
    source_rows = source["dataList"]
    if len(rows) == len(source_rows) and all(
        isinstance(a, dict) and isinstance(b, dict) and a.get("id") == b.get("id")
        for a, b in zip(rows, source_rows)
    ):
        for a, b in zip(rows, source_rows):
            merge_value(a, b, stats)
            stats["rows_matched"] += 1
        stats["positional_files"] += 1
        return True
    counts = collections.Counter(r["id"] for r in source_rows if isinstance(r, dict) and "id" in r)
    indexed = {r["id"]: r for r in source_rows if isinstance(r, dict) and "id" in r and counts[r["id"]] == 1}
    stats["ambiguous_source_rows_skipped"] += sum(v for v in counts.values() if v > 1)
    for row in rows:
        if not isinstance(row, dict) or "id" not in row:
            continue
        translated = indexed.pop(row["id"], None)
        if translated is None:
            stats["base_rows_preserved"] += 1
            continue
        merge_value(row, translated, stats)
        stats["rows_matched"] += 1
    stats["source_rows_unmatched"] += len(indexed)
    return True


def fill_speakers(value, names, base_names, stats):
    if isinstance(value, list):
        for child in value:
            fill_speakers(child, names, base_names, stats)
    elif isinstance(value, dict):
        model = value.get("model")
        if isinstance(model, str) and model and "content" in value:
            match = names.get(model)
            original = base_names.get(model)
            if match:
                for field, index in (("teller", 0), ("title", 1)):
                    if field not in value or (original and value[field] == original[index]):
                        if value.get(field) != match[index]:
                            value[field] = match[index]
                            stats[f"speaker_{field}_localized"] += 1
            elif "teller" not in value or "title" not in value:
                stats["speaker_model_unresolved"] += 1
        for child in value.values():
            if isinstance(child, (dict, list)):
                fill_speakers(child, names, base_names, stats)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--base", required=True, type=Path)
    p.add_argument("--llc", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--game-version", required=True)
    p.add_argument("--llc-version", required=True)
    args = p.parse_args()
    stats = collections.Counter()
    with zipfile.ZipFile(args.base) as baseline, zipfile.ZipFile(args.llc) as llc:
        if baseline.testzip() or llc.testzip():
            raise ValueError("ZIP checksum failure")
        base = {n[len(BASE_PREFIX):]: n for n in baseline.namelist()
                if n.startswith(BASE_PREFIX) and n.lower().endswith(".json")}
        source = {n[len(LLC_PREFIX):]: n for n in llc.namelist()
                  if n.startswith(LLC_PREFIX) and n.lower().endswith(".json")}
        if not base or not source:
            raise ValueError("Unexpected ZIP layout")
        if any(part in ("", ".", "..") for path in (*base, *source) for part in path.split("/")):
            raise ValueError("Unsafe ZIP member path")
        required = {"ScenarioModelCodes-AutoCreated.json", "kr_settings-ui-donttranslate.json"}
        if not required.issubset(source) or not {"JP_" + n for n in required}.issubset(base):
            raise ValueError("Required scenario or settings resource missing")
        scenarios = load_json(llc.read(source["ScenarioModelCodes-AutoCreated.json"]), "scenario")
        names = {r["id"]: (r.get("name", ""), r.get("nickName", ""))
                 for r in scenarios["dataList"] if isinstance(r, dict) and isinstance(r.get("id"), str)}
        baseline_scenarios = load_json(baseline.read(base["JP_ScenarioModelCodes-AutoCreated.json"]), "baseline scenario")
        base_names = {r["id"]: (r.get("name", ""), r.get("nickName", ""))
                      for r in baseline_scenarios["dataList"] if isinstance(r, dict) and isinstance(r.get("id"), str)}
        used = set()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
            for relative, original in sorted(base.items()):
                subfolder, basename = relative.rsplit("/", 1) if "/" in relative else ("", relative)
                if not basename.startswith("JP_"):
                    raise ValueError(f"Unexpected baseline name: {relative}")
                stem = basename[3:-5]
                candidate = "/".join(filter(None, (subfolder, stem + ".json")))
                translated = source.get(candidate)
                if translated is None:
                    fallback = DELTA_SUFFIX.sub("", stem)
                    candidate = "/".join(filter(None, (subfolder, fallback + ".json")))
                    translated = source.get(candidate)
                data = load_json(baseline.read(original), original)
                if translated:
                    incoming = load_json(llc.read(translated), translated)
                    if merge_rows(data, incoming, stats):
                        used.add(candidate)
                        stats["files_with_translation"] += 1
                else:
                    stats["files_from_baseline_only"] += 1
                if subfolder == "StoryData":
                    fill_speakers(data, names, base_names, stats)
                target = OUTPUT_PREFIX + relative
                entry = zipfile.ZipInfo(target, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                output.writestr(entry, json.dumps(data, ensure_ascii=False, indent=2) + "\n", compresslevel=9)
            if not output.namelist():
                raise ValueError("No output files")
        unmatched = sorted(set(source) - used)
        unexpected = [name for name in unmatched if name != "Info/version.json"]
        if unexpected or stats["ambiguous_source_rows_skipped"]:
            args.output.unlink(missing_ok=True)
            raise ValueError(
                f"Unmatched translation files: {unexpected}; "
                f"ambiguous source rows: {stats['ambiguous_source_rows_skipped']}"
            )
        report = {
            "game_version": args.game_version, "llc_version": args.llc_version,
            "base_sha256": hashlib.sha256(args.base.read_bytes()).hexdigest(),
            "llc_sha256": hashlib.sha256(args.llc.read_bytes()).hexdigest(),
            "output_sha256": hashlib.sha256(args.output.read_bytes()).hexdigest(),
            "baseline_files": len(base), "llc_files": len(source),
            "stats": dict(sorted(stats.items())), "llc_files_unmatched": unmatched,
        }
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"output": str(args.output), "report": str(args.report),
                          "stats": report["stats"], "unmatched_files": len(unmatched)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
