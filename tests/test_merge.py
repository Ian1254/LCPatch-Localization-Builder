import contextlib
import io
import json
import sys
import tempfile
import unittest
import zipfile
from collections import Counter
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build


class PackTests(unittest.TestCase):
    def test_speaker_fills_missing_and_preserves_explicit_names(self):
        rows = [{'model': 'a', 'content': '話'},
                {'model': 'a', 'content': '話', 'teller': '特殊稱呼', 'title': '特別職稱'}]
        build.fill_speakers(rows, {'a': ('中文', '嚮導')}, Counter())
        self.assertEqual((rows[0]['teller'], rows[0]['title']), ('中文', '嚮導'))
        self.assertEqual((rows[1]['teller'], rows[1]['title']), ('特殊稱呼', '特別職稱'))

    def run_pack(self, directory, extra=None):
        directory = Path(directory)
        source = directory / 'input.zip'
        resources = {
            'ScenarioModelCodes-AutoCreated.json': {'dataList': [{'id': 'a', 'name': '中文', 'nickName': '嚮導'}]},
            'kr_settings-ui-donttranslate.json': {'dataList': []},
            'StoryData/S1039I.json': {'dataList': [{'id': -1, 'model': 'a', 'content': '原文', 'voice': 'v'}, {'id': -1, 'model': 'a', 'content': '第二句'}]},
            'RPGSystem/rpg-dialogue-text-data-floor-7-c2.json': {'list': [{'dialogueKey': 'D1', 'index': 0}]},
            'Info/version.json': {'version': '2026100303'},
            'empty.json': {},
        }
        resources.update(extra or {})
        with zipfile.ZipFile(source, 'w') as z:
            for name, data in resources.items():
                z.writestr(build.LLC_PREFIX + name, json.dumps(data))
        output, report = directory / 'output.zip', directory / 'report.json'
        with patch.object(sys, 'argv', ['build.py', '--llc', str(source), '--output', str(output), '--report', str(report), '--llc-version', '2026100303']), contextlib.redirect_stdout(io.StringIO()):
            build.main()
        return output, json.loads(report.read_text())

    def test_direct_source_preserves_structure_and_old_unmatched_files(self):
        with tempfile.TemporaryDirectory() as d:
            output, report = self.run_pack(d)
            with zipfile.ZipFile(output) as z:
                data = json.loads(z.read('Localize/jp/StoryData/JP_S1039I.json'))
                self.assertEqual([r['id'] for r in data['dataList']], [-1, -1])
                self.assertEqual(data['dataList'][0]['voice'], 'v')
                self.assertEqual(data['dataList'][0]['content'], '原文')
                self.assertEqual(data['dataList'][0]['teller'], '中文')
                self.assertEqual(json.loads(z.read('Localize/jp/RPGSystem/JP_rpg-dialogue-text-data-floor-7-c2.json')), {'list': [{'dialogueKey': 'D1', 'index': 0}]})
                self.assertEqual(json.loads(z.read('Localize/jp/JP_empty.json')), {})
                self.assertFalse(any('/Info/' in n for n in z.namelist()))
            self.assertEqual(report['output_files'], 5)
            self.assertEqual(report['excluded_files'][0]['path'], 'Info/version.json')

    def test_unsafe_path_blocks_pack(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'Unsafe ZIP'):
                self.run_pack(d, {'../escape.json': {}})
            self.assertFalse((Path(d) / 'output.zip').exists())

    def test_output_name_collision_blocks_pack(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, 'Duplicate output'):
                self.run_pack(d, {'JP_empty.json': {}})

    def test_unknown_speaker_is_preserved(self):
        row = {'model': 'unknown', 'content': '話'}
        stats = Counter()
        build.fill_speakers(row, {}, stats)
        self.assertNotIn('teller', row)
        self.assertEqual(stats['speaker_model_unresolved'], 1)
