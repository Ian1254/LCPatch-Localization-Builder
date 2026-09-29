#!/usr/bin/env python3
"""Resolve the latest releases and build a versioned LCPatch ZIP."""
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

GH_API = "https://api.github.com/repos"
BASE_REPO = "ghcruise/LimbusCompany-IOS-Localization"
TEXT_REPO = "LocalizeLimbusCompany/LocalizeLimbusCompany"
ROOT = Path(__file__).resolve().parents[1]


def request(url):
    headers = {"User-Agent": "LCPatch-localization-builder", "Accept": "application/vnd.github+json"}
    if token := os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    return urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=90)


def release(repo):
    with request(f"{GH_API}/{repo}/releases/latest") as response:
        return json.load(response)


def asset(release_data, name):
    found = [a for a in release_data["assets"] if a["name"] == name]
    if len(found) != 1:
        raise ValueError(f"Expected one {name} asset in {release_data['html_url']}")
    return found[0]


def download(item, path):
    digest = hashlib.sha256()
    size = 0
    with request(item["browser_download_url"]) as response, path.open("wb") as output:
        while chunk := response.read(1024 * 1024):
            digest.update(chunk)
            output.write(chunk)
            size += len(chunk)
            if size > 128 * 1024 * 1024:
                raise ValueError(f"Asset too large: {item['name']}")
    if size != item["size"]:
        raise ValueError(f"Asset size mismatch: {item['name']}")
    expected = item.get("digest")
    if expected and expected != "sha256:" + digest.hexdigest():
        raise ValueError(f"Asset digest mismatch: {item['name']}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true", help="resolve versions without downloading assets")
    p.add_argument("--github-output", type=Path)
    p.add_argument("--expected-game-version")
    p.add_argument("--expected-llc-version")
    p.add_argument("--dist", type=Path, default=ROOT / "dist")
    args = p.parse_args()
    base, text = release(BASE_REPO), release(TEXT_REPO)
    base_tag, text_tag = base["tag_name"], text["tag_name"]
    match = re.fullmatch(r"v(\d+\.\d+\.\d+)", base_tag)
    if not match or not re.fullmatch(r"\d{10}", text_tag):
        raise ValueError(f"Unexpected release versions: {base_tag}, {text_tag}")
    game_version = match.group(1)
    if args.expected_game_version and args.expected_game_version != game_version:
        raise ValueError("Game version changed between check and build")
    if args.expected_llc_version and args.expected_llc_version != text_tag:
        raise ValueError("Translation version changed between check and build")
    versions = {"game_version": game_version, "llc_version": text_tag,
                "tag": f"v{game_version}-{text_tag}"}
    if args.github_output:
        with args.github_output.open("a") as output:
            for key, value in versions.items():
                output.write(f"{key}={value}\n")
    print(json.dumps(versions))
    if args.check:
        return
    args.dist.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        base_path = Path(directory) / "localize_jp.zip"
        text_path = Path(directory) / "LimbusLocalize.zip"
        download(asset(base, "localize_jp.zip"), base_path)
        download(asset(text, f"LimbusLocalize_{text_tag}.zip"), text_path)
        output_path = args.dist / f"LCPatch_{game_version}_LLC_{text_tag}.zip"
        report_path = args.dist / "merge-report.json"
        subprocess.run([sys.executable, str(ROOT / "build.py"),
                        "--base", str(base_path), "--llc", str(text_path),
                        "--output", str(output_path), "--report", str(report_path),
                        "--game-version", game_version, "--llc-version", text_tag], check=True)
        report = json.loads(report_path.read_text())
        report["sources"] = {"baseline_release": base["html_url"],
                             "translation_release": text["html_url"]}
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        (args.dist / "checksums.sha256").write_text(
            f"{hashlib.sha256(output_path.read_bytes()).hexdigest()}  {output_path.name}\n"
            f"{hashlib.sha256(report_path.read_bytes()).hexdigest()}  {report_path.name}\n"
        )


if __name__ == "__main__":
    main()
