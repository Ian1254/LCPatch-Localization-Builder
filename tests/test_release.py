import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import auto_build


class ReleaseTests(unittest.TestCase):
    def test_check_only_queries_translation(self):
        with patch.object(auto_build, 'release', return_value={'tag_name': '2026100303'}) as release, \
             patch.object(auto_build, 'download') as download, \
             patch.object(sys, 'argv', ['auto_build.py', '--check']), \
             contextlib.redirect_stdout(io.StringIO()) as output:
            auto_build.main()
        release.assert_called_once_with(auto_build.TEXT_REPO)
        download.assert_not_called()
        self.assertEqual(json.loads(output.getvalue()), {'llc_version': '2026100303', 'tag': 'LLC-2026100303'})

    def test_translation_change_between_check_and_build_blocks(self):
        with patch.object(auto_build, 'release', return_value={'tag_name': '2026100303'}), \
             patch.object(sys, 'argv', ['auto_build.py', '--expected-llc-version', '2026100302']):
            with self.assertRaisesRegex(ValueError, 'Translation version changed'):
                auto_build.main()
