#!/usr/bin/env python3
"""Convert LLC resources directly into a LCPatch language pack."""
import argparse
import collections
import hashlib
import json
import zipfile
from pathlib import Path, PurePosixPath

LLC_PREFIX = "LimbusCompany_Data/Lang/LLC_zh-CN/"
OUTPUT_PREFIX = "Localize/jp/"


def load_json(raw, name):
    try:
        value = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeError, ValueError) as exc:
        raise ValueError(f"Invalid JSON: {name}") from exc
    if not isinstance(value, (dict, list)):
        raise ValueError(f"Unexpected JSON root: {name}")
    return value


def fill_speakers(value, names, stats):
    if isinstance(value, list):
        for child in value:
            fill_speakers(child, names, stats)
    elif isinstance(value, dict):
        model = value.get("model")
        if isinstance(model, str) and model and "content" in value:
            match = names.get(model)
            if match:
                for field, index in (("teller", 0), ("title", 1)):
                    # Preserve explicit LLC speaker names and narrative titles.
                    if field not in value:
                        value[field] = match[index]
                        stats[f"speaker_{field}_localized"] += 1
            elif "teller" not in value or "title" not in value:
                stats["speaker_model_unresolved"] += 1
        for child in value.values():
            if isinstance(child, (dict, list)):
                fill_speakers(child, names, stats)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--llc", required=True, type=Path)
    p.add_argument("--output", required=True, type=Path)
    p.add_argument("--report", required=True, type=Path)
    p.add_argument("--llc-version", required=True)
    args = p.parse_args()
    stats = collections.Counter()
    with zipfile.ZipFile(args.llc) as llc:
        if llc.testzip():
            raise ValueError("ZIP checksum failure")
        source = {}
        for member in llc.infolist():
            if not member.filename.startswith(LLC_PREFIX) or not member.filename.lower().endswith('.json'):
                continue
            relative = member.filename[len(LLC_PREFIX):]
            if '\\' in relative or any(part in ('', '.', '..') for part in relative.split('/')):
                raise ValueError(f"Unsafe ZIP member path: {relative}")
            if relative in source:
                raise ValueError(f"Duplicate ZIP member: {relative}")
            source[relative] = member.filename
        required = {'ScenarioModelCodes-AutoCreated.json', 'kr_settings-ui-donttranslate.json'}
        if not required.issubset(source):
            raise ValueError("Required scenario or settings resource missing")
        resources = {name: load_json(llc.read(path), path) for name, path in source.items()}
        scenarios = resources['ScenarioModelCodes-AutoCreated.json']
        if not isinstance(scenarios, dict) or not isinstance(scenarios.get('dataList'), list):
            raise ValueError("Missing scenario dataList array")
        names = {}
        for row in scenarios['dataList']:
            if not isinstance(row, dict) or not isinstance(row.get('id'), str):
                continue
            pair = (row.get('name', ''), row.get('nickName', ''))
            if not all(isinstance(v, str) for v in pair):
                raise ValueError("Invalid scenario speaker names")
            if row['id'] in names and names[row['id']] != pair:
                raise ValueError(f"Conflicting scenario model: {row['id']}")
            names[row['id']] = pair
        excluded = []
        targets = {}
        # Validate and prepare all resources before writing a deliverable.
        for relative, data in sorted(resources.items()):
            if relative.startswith('Info/'):
                excluded.append({'path': relative, 'reason': 'LLC package metadata'})
                continue
            path = PurePosixPath(relative)
            basename = path.name
            if basename.startswith(('JP_', 'KR_', 'EN_')):
                basename = basename[3:]
            target = OUTPUT_PREFIX + str(path.with_name('JP_' + basename))
            if target in targets:
                raise ValueError(f"Duplicate output resource: {target}")
            if path.parts[0] == 'StoryData':
                fill_speakers(data, names, stats)
            targets[target] = data
        if not targets:
            raise ValueError("No output files")
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as output:
            for target, data in targets.items():
                entry = zipfile.ZipInfo(target, date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = zipfile.ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                output.writestr(entry, json.dumps(data, ensure_ascii=False, indent=2) + '\n', compresslevel=9)
        report = {
            'llc_version': args.llc_version, 'mode': 'llc-only',
            'llc_sha256': hashlib.sha256(args.llc.read_bytes()).hexdigest(),
            'output_sha256': hashlib.sha256(args.output.read_bytes()).hexdigest(),
            'llc_files': len(source), 'output_files': len(targets),
            'stats': dict(sorted(stats.items())), 'excluded_files': excluded,
        }
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
