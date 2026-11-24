import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from grant_agent.config import load_dotenv


class LoadDotenvTest(unittest.TestCase):
    def _write(self, text: str) -> Path:
        d = tempfile.mkdtemp()
        p = Path(d) / ".env"
        p.write_text(text, encoding="utf-8")
        return p

    def test_reads_keys_from_env_file(self):
        p = self._write(
            "# comment\n"
            "ANTHROPIC_API_KEY=sk-test\n"
            "export ALERT_EMAIL=\"a@b.c\"\n"
            "COMPOSIO_API_KEY='ck'\n"
            "\n"
            "garbage line\n"
        )
        with mock.patch.dict(os.environ, {}, clear=True):
            load_dotenv(p)
            self.assertEqual(os.environ["ANTHROPIC_API_KEY"], "sk-test")
            self.assertEqual(os.environ["ALERT_EMAIL"], "a@b.c")
            self.assertEqual(os.environ["COMPOSIO_API_KEY"], "ck")

    def test_existing_environment_wins(self):
        p = self._write("ANTHROPIC_API_KEY=from-file\n")
        with mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "from-shell"}, clear=True):
            load_dotenv(p)
            self.assertEqual(os.environ["ANTHROPIC_API_KEY"], "from-shell")

    def test_missing_file_is_a_no_op(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            load_dotenv(Path(tempfile.mkdtemp()) / ".env")
            self.assertNotIn("ANTHROPIC_API_KEY", os.environ)

    def test_config_import_picks_up_repo_env_file(self):
        """Simulates the cron run: no keys exported, keys only in <repo>/.env."""
        import importlib
        import grant_agent.config as config

        repo_env = Path(config.__file__).resolve().parent.parent / ".env"
        if repo_env.exists():
            self.skipTest("a real .env exists; not overwriting it")
        repo_env.write_text("ANTHROPIC_API_KEY=sk-cron\nALERT_EMAIL=x@y.z\n", encoding="utf-8")
        try:
            with mock.patch.dict(os.environ, {}, clear=True):
                importlib.reload(config)
                self.assertEqual(config.ANTHROPIC_API_KEY, "sk-cron")
                self.assertEqual(config.ALERT_EMAIL, "x@y.z")
        finally:
            repo_env.unlink()
            importlib.reload(config)


if __name__ == "__main__":
    unittest.main()
