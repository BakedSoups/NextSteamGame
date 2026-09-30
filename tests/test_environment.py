from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backend.environment import load_project_env


class ProjectEnvironmentTests(unittest.TestCase):
    def test_shell_values_and_first_file_value_take_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("EXISTING=file\nEMPTY=file\nDUPLICATE=first\nDUPLICATE=second\n")
            with patch.dict(os.environ, {"EXISTING": "shell", "EMPTY": ""}, clear=True):
                load_project_env(path)
                self.assertEqual(dict(os.environ), {
                    "EXISTING": "shell", "EMPTY": "", "DUPLICATE": "first",
                })

    def test_literal_values_and_legacy_quote_handling(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "# comment\n\ninvalid line\n=value\n NAME = 'Steam Game' \n"
                'URL="https://example.com/?a=b"\nLITERAL=$NAME # literal text\n'
            )
            with patch.dict(os.environ, {}, clear=True):
                load_project_env(path)
                self.assertEqual(dict(os.environ), {
                    "NAME": "Steam Game", "URL": "https://example.com/?a=b",
                    "LITERAL": "$NAME # literal text",
                })

    def test_missing_file_is_optional(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(os.environ, {"EXISTING": "shell"}, clear=True):
                load_project_env(Path(directory) / "missing")
                self.assertEqual(dict(os.environ), {"EXISTING": "shell"})
