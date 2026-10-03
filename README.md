# LCPatch localization pack builder

Converts the latest [LLC Chinese translation](https://github.com/LocalizeLimbusCompany/LocalizeLimbusCompany) directly into a LCPatch-compatible ZIP. LLC is the only resource source. No JP baseline is downloaded, and no game version is detected or paired.

## Automated releases

GitHub Actions checks the LLC latest Release three times daily (UTC 00:17, 08:17 and 16:17), and can run manually. Changes to builder code on main also trigger a check. Each new LLC resource version is published once as `LLC-<LLC-version>` with `LCPatch_LLC_<LLC-version>.zip`, `merge-report.json`, and `checksums.sha256`. A translation update between check and download, invalid JSON, unsafe paths, duplicate output names, conflicting speaker mappings, or invalid ZIP stops publication.

## Local build

Python 3 standard library is sufficient:

```sh
python3 scripts/auto_build.py
python3 -m unittest discover -s tests -v
```

To convert a downloaded resource pack:

```sh
python3 build.py --llc LimbusLocalize_2026100303.zip \
  --output dist/LCPatch_LLC_2026100303.zip \
  --report dist/merge-report.json --llc-version 2026100303
```

## Conversion rules

- Read JSON resources under `LimbusCompany_Data/Lang/LLC_zh-CN/` and output them under `Localize/jp/` with `JP_` filename prefixes. Preserve subdirectories and resource contents, including IDs, model codes, voice references, arrays, and empty resources. This is a format conversion, not a cross-source merge.
- Fill missing story dialogue `teller` and `title` fields from LLC's `ScenarioModelCodes-AutoCreated.json` using exact model IDs. Preserve explicit speaker names and narrative titles. Unresolved models remain unchanged and are counted in the report.
- Exclude `Info/` package metadata from game resources and list exclusions in the report. Game JSON files with other schemas, such as RPG resources using `list`, are retained.
- Retain the seven files that could not be paired with the previous JP baseline, including `StoryData/S1039I.json` and RPG dialogue structure data. There is no unmatched-file allowlist or baseline dependence.
- LCPatch performs PUA conversion and font selection. This ZIP does not replace the game's CDN manifest. Resources absent from LLC are not filled from another source, and files still untranslated in LLC remain as supplied. An on-device check is still needed to establish behavior of newly supplied resource structures.
- Releases use the LLC resource version, not an installed game compatibility claim. Existing LCPatch builds that only parse `v<game-version>-<LLC-version>` tags need the companion parser update or manual ZIP import.

## Attribution

This repository contains conversion code, not game or translation assets. Release output incorporates Project Moon resources and LLC material. Preserve source attribution and the applicable [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) conditions when sharing.
