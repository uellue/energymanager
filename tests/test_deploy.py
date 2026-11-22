"""Tests for tools/deploy.sh, in throwaway repositories with a fake docker.

Source: debrief 2026-11-22, proposal 26 (the host runs main; a branch only as a
logged test).
"""

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "tools" / "deploy.sh"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True).stdout.strip()


class Deploy(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        ident = ["-c", "user.name=t", "-c", "user.email=t@example.org"]
        # The principal's repository with one commit on main, and a fork with a branch.
        self.upstream = self.tmp / "upstream"
        self.upstream.mkdir()
        git(self.upstream, "init", "-q", "-b", "main")
        (self.upstream / "tools").mkdir()
        shutil.copy(SCRIPT, self.upstream / "tools" / "deploy.sh")
        (self.upstream / ".gitignore").write_text(".env\n")
        git(self.upstream, "add", ".")
        git(self.upstream, *ident, "commit", "-q", "-m", "one")
        self.fork = self.tmp / "fork"
        git(self.tmp, "clone", "-q", str(self.upstream), str(self.fork))
        git(self.fork, "switch", "-q", "-c", "feature")
        (self.fork / "feature.txt").write_text("x\n")
        git(self.fork, "add", ".")
        git(self.fork, *ident, "commit", "-q", "-m", "feature")
        # The host's clone, its data folder and a docker that only records its call.
        self.host = self.tmp / "host"
        git(self.tmp, "clone", "-q", str(self.upstream), str(self.host))
        self.data = self.tmp / "data"
        self.data.mkdir()
        (self.host / ".env").write_text(f"EM_DATA_DIR={self.data}\n")
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir()
        docker = bin_dir / "docker"
        docker.write_text(f'#!/bin/sh\necho "$@" >> "{self.tmp}/docker-calls"\n')
        docker.chmod(docker.stat().st_mode | stat.S_IEXEC)
        self.env = {**os.environ, "PATH": f"{bin_dir}:{os.environ['PATH']}", "EM_DEPLOY_FORK": str(self.fork)}

    def run_deploy(self, *args):
        return subprocess.run(["bash", str(self.host / "tools" / "deploy.sh"), *args],
                              capture_output=True, text=True, env=self.env)

    def log(self):
        return (self.data / "deploy.log").read_text().splitlines()

    def test_main_fast_forwards_starts_and_logs(self):
        (self.upstream / "new.txt").write_text("y\n")
        git(self.upstream, "add", ".")
        git(self.upstream, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "two")
        result = self.run_deploy()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(self.host, "rev-parse", "HEAD"), git(self.upstream, "rev-parse", "HEAD"))
        self.assertEqual((self.tmp / "docker-calls").read_text(), "compose up -d --build\n")
        fields = self.log()[0].split("\t")
        self.assertEqual(fields[2:], ["main", git(self.host, "rev-parse", "--short", "HEAD"), "main", "-"])

    def test_test_branch_is_logged_with_reason_and_main_returns(self):
        result = self.run_deploy("--test", "feature", "try the new chart")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(git(self.host, "rev-parse", "HEAD"), git(self.fork, "rev-parse", "HEAD"))
        self.assertEqual(self.log()[0].split("\t")[2:], ["test", git(self.fork, "rev-parse", "--short", "HEAD"),
                                                         "feature", "try the new chart"])
        self.assertEqual(self.run_deploy().returncode, 0)
        self.assertEqual(git(self.host, "rev-parse", "HEAD"), git(self.upstream, "rev-parse", "HEAD"))
        self.assertEqual(git(self.host, "branch", "--show-current"), "main")

    def test_test_needs_a_branch_and_a_reason(self):
        for args in (["--test"], ["--test", "feature"], ["--test", "feature", ""], ["feature"]):
            with self.subTest(args=args):
                self.assertEqual(self.run_deploy(*args).returncode, 2)
        self.assertFalse((self.tmp / "docker-calls").exists())

    def test_local_changes_are_refused(self):
        (self.host / "tools" / "deploy.sh").write_text((SCRIPT.read_text()) + "\n# edited\n")
        result = self.run_deploy()
        self.assertEqual(result.returncode, 1)
        self.assertIn("local changes", result.stderr)
        self.assertFalse((self.tmp / "docker-calls").exists())
        self.assertFalse((self.data / "deploy.log").exists())

    def test_missing_data_dir_is_refused(self):
        head = git(self.host, "rev-parse", "HEAD")
        for env, message in (("OTHER=1\n", "EM_DATA_DIR"), (f"EM_DATA_DIR={self.tmp}/nowhere\n", "data folder")):
            with self.subTest(env=env):
                (self.host / ".env").write_text(env)
                result = self.run_deploy("--test", "feature", "try")
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
        self.assertEqual(git(self.host, "rev-parse", "HEAD"), head)
        self.assertFalse((self.tmp / "docker-calls").exists())

    def test_quoted_data_dir_with_crlf_as_compose_reads_it(self):
        """review: quotes and a CRLF line ending stayed in the path."""
        (self.host / ".env").write_text(f'EM_DATA_DIR="{self.data}"\r\n')
        self.assertEqual(self.run_deploy().returncode, 0)
        self.assertEqual(len(self.log()), 1)

    def test_branch_must_be_a_plain_branch_name(self):
        """review: a refspec could overwrite the local main, an option reached git."""
        self.run_deploy("--test", "feature", "first")
        for branch in ("+feature:refs/heads/main", "--upload-pack=touch x", "feature..x", "a\tb"):
            with self.subTest(branch=branch):
                self.assertEqual(self.run_deploy("--test", branch, "sneaky").returncode, 2)
        self.assertEqual(git(self.host, "rev-parse", "refs/heads/main"), git(self.upstream, "rev-parse", "HEAD"))
        self.assertEqual(len(self.log()), 1)

    def test_reason_without_control_characters(self):
        """review: a tab or newline in the reason broke the log's lines."""
        self.assertEqual(self.run_deploy("--test", "feature", "a\tb\nc").returncode, 2)
        self.assertFalse((self.data / "deploy.log").exists())

    def test_local_commit_on_main_is_refused(self):
        """review: --ff-only accepted a main that is ahead of origin/main."""
        (self.host / "local.txt").write_text("z\n")
        git(self.host, "add", "local.txt")
        git(self.host, "-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "-q", "-m", "local")
        result = self.run_deploy()
        self.assertEqual(result.returncode, 1)
        self.assertIn("origin/main", result.stderr)
        self.assertFalse((self.tmp / "docker-calls").exists())

    def test_unknown_branch_fails_before_anything_runs(self):
        head = git(self.host, "rev-parse", "HEAD")
        self.assertNotEqual(self.run_deploy("--test", "no-such-branch", "try").returncode, 0)
        self.assertEqual(git(self.host, "rev-parse", "HEAD"), head)
        self.assertFalse((self.tmp / "docker-calls").exists())
        self.assertFalse((self.data / "deploy.log").exists())


if __name__ == "__main__":
    unittest.main()
