"""install_cron() must build a crontab line that survives paths with spaces or %.

Each test builds the line, applies cron's own %-handling to the command field
(unescaped % -> end of command, backslash-% -> literal %), then runs what is
left through /bin/sh exactly as cron would, and checks the job really ran.
"""
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import build_cron_line  # noqa: E402


def cron_command(line: str) -> str:
    """Return the shell command cron would run for a 5-field crontab line."""
    command = line.split(None, 5)[5]
    out, escaped = [], False
    for ch in command:
        if escaped:
            if ch != "%":
                out.append("\\")
            out.append(ch)
            escaped = False
        elif ch == "\\":
            escaped = True
        elif ch == "%":
            break  # cron ends the command here; the rest becomes stdin
        else:
            out.append(ch)
    if escaped:
        out.append("\\")
    return "".join(out)


class CronLineTest(unittest.TestCase):
    def _run_job(self, dirname: str) -> Path:
        base = Path(tempfile.mkdtemp())
        workdir = base / dirname
        workdir.mkdir()
        script = workdir / "main.py"
        script.write_text(
            "import os\n"
            "open('ran.txt', 'w').write(os.getcwd())\n"
            "print('job ran')\n"
        )
        line = build_cron_line(script, sys.executable)
        proc = subprocess.run(
            ["/bin/sh", "-c", cron_command(line)],
            capture_output=True, text=True, env={"PATH": "/usr/bin:/bin"},
        )
        self.assertEqual(proc.returncode, 0, f"line={line!r} stderr={proc.stderr!r}")
        return workdir

    def test_plain_path_line_is_unchanged(self):
        # No special characters: the line must match what older versions
        # installed, so `--cron` still detects an existing entry.
        script = Path("/opt/agent-II/main.py")
        self.assertEqual(
            build_cron_line(script, "/usr/bin/python3"),
            "0 8 * * 1 cd /opt/agent-II && /usr/bin/python3 /opt/agent-II/main.py"
            " >> /opt/agent-II/grant_agent.log 2>&1",
        )

    def test_path_with_space_runs(self):
        workdir = self._run_job("My Projects")
        self.assertTrue((workdir / "ran.txt").exists())
        self.assertIn("job ran", (workdir / "grant_agent.log").read_text())

    def test_path_with_percent_runs(self):
        workdir = self._run_job("grants 100% done")
        self.assertTrue((workdir / "ran.txt").exists())
        self.assertIn("job ran", (workdir / "grant_agent.log").read_text())


if __name__ == "__main__":
    unittest.main()
