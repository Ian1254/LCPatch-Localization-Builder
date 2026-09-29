# LCPatch localization pack builder

Builds an LCPatch-compatible ZIP from the latest [LLC Chinese translation](https://github.com/LocalizeLimbusCompany/LocalizeLimbusCompany) and the [ghcruise mobile JP resource pack](https://github.com/ghcruise/LimbusCompany-IOS-Localization). The latter is a complete JP mobile language baseline; LLC is the source of translated display strings and `ScenarioModelCodes-AutoCreated.json` names.

## Automated releases

Create a GitHub repository containing these files and enable Actions. `.github/workflows/build.yml` checks both upstream Releases three times daily (UTC 00:17, 08:17 and 16:17), and can be run manually. It builds only a new `v<game-version>-<LLC-version>` combination. An invalid ZIP, an unmatched translation file, ambiguous duplicate IDs or inconsistent upstream versions stops publication. The previous Release remains available.

Each Release contains `LCPatch_<game-version>_LLC_<LLC-version>.zip`, `merge-report.json` and `checksums.sha256`. LCPatch has not yet been modified to fetch these Releases automatically. When integrating, require that the game's installed version matches the Release's game version.

## Local build

Python 3 standard library is sufficient:

```sh
python3 scripts/auto_build.py
python3 -m unittest discover -s tests -v
```

To use specific downloaded inputs:

```sh
python3 build.py --base localize_jp.zip --llc LimbusLocalize_2026092802.zip \
  --output dist/LCPatch_1.115.0_LLC_2026092802.zip \
  --report dist/merge-report.json --game-version 1.115.0 --llc-version 2026092802
```

The baseline ZIP must contain `LocalizeTemp_jp/JP_*.json`. The LLC ZIP must contain `LimbusCompany_Data/Lang/LLC_zh-CN/*.json`. Output is `Localize/jp/JP_*.json`, including nested `StoryData/`; LCPatch's current import path accepts it. LCPatch performs its own PUA conversion and font selection. This ZIP does not replace the game's CDN manifest.

## Merge rules and limits

- Join translated rows by `id`; when both ordered ID sequences match exactly, align by position to preserve legitimate duplicate IDs. Copy display text fields only. Keep baseline `id`, `model`, voice references and game metadata.
- For story dialogue, use the LLC `ScenarioModelCodes-AutoCreated.json` mapping to replace default baseline `teller`/`title` names. Preserve explicitly different names and titles. Unknown `model` codes remain unchanged and are counted in the report.
- Retain baseline files and rows that LLC has not translated, including incremental resource files. Fail publication if an unexpected LLC file has no matching slot or duplicate IDs cannot be aligned safely. `Info/version.json` is LLC metadata and is not a game slot.
- The ghcruise baseline already contains some Chinese text with mobile-font substitutions. Matching LLC strings are restored verbatim; baseline-only rows retain their existing wording. Thus this is not guaranteed to preserve original LLC wording in every row.
- The source Release tag is used for version pairing; a future upstream game update still needs an on-device test of LCPatch's file redirects and font hook.

This project does not contain game or translation assets in Git. Release output incorporates Project Moon resources and LLC/ghcruise material. Preserve source attribution and the applicable [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) conditions when sharing.
