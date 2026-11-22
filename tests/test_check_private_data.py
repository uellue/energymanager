"""Tests for tools/check_private_data.py (spec: private-data-check).

The examples are assembled at run time, so that this file itself passes the check.
"""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "tools" / "check_private_data.py"
sys.path.insert(0, str(SCRIPT.parent))
from check_private_data import find_kinds  # noqa: E402

IP = "192." + "168.1.20"
LAT, LON = "50." + "9123", "6." + "4012"
JWT = "eyJ" + "hbGciOiJIUzI1NiJ9" + ".eyJ" + "zdWIiOiIxMjM0In0" + ".abcdefghijklmnop"


class FindKinds(unittest.TestCase):
    def test_private_ip(self):
        self.assertEqual(find_kinds("host: " + IP), ["private IP address"])
        self.assertEqual(find_kinds("10." + "0.0.1 and 172." + "20.1.2"), ["private IP address"])

    def test_public_ip_and_versions_are_clean(self):
        for text in ["8.8.8.8", "version 10.1.2.3.4", "172." + "15.0.1", "2026.11.2"]:
            self.assertEqual(find_kinds(text), [], text)

    def test_coordinates_as_keys(self):
        self.assertEqual(find_kinds("latitude: " + LAT), ["coordinates"])
        self.assertEqual(find_kinds('"lon": ' + LON), ["coordinates"])

    def test_coordinates_as_pairs(self):
        self.assertEqual(find_kinds(LAT + ", " + LON), ["coordinates"])
        self.assertEqual(find_kinds("/estimate/" + LAT + "/" + LON + "/35/55/7.92"), ["coordinates"])

    def test_coarse_or_out_of_range_numbers_are_clean(self):
        self.assertEqual(find_kinds("/estimate/50.9/6.4/35/55"), [])
        self.assertEqual(find_kinds("123.456, 7.890"), [])

    def test_tokens(self):
        self.assertEqual(find_kinds("Authorization: Bearer " + JWT), ["token"])
        self.assertEqual(find_kinds("api_key = " + "a1b2c3d4e5f6g7h8i9"), ["token"])
        self.assertEqual(find_kinds("HA_TOKEN=" + "x" * 20), ["token"])

    def test_references_to_secrets_are_clean(self):
        for text in ["HA_TOKEN=${HOME_ASSISTANT_TOKEN}", "password: !secret db_password",
                     "token: <your long-lived token>", "HA_TOKEN=",
                     "token = self._load_token_from_file(path)",
                     "HA_TOKEN_FILE=/run/secrets/ha_token",
                     "token_url: https://idp.example.org/v1/oidc/token",
                     "secret_name: home_assistant_long_lived_token"]:
            self.assertEqual(find_kinds(text), [], text)

    def test_prefixed_coordinate_keys(self):
        for text in ["EM_LATITUDE=" + LAT, "home_lat: " + LAT, "latitude_deg = " + LAT]:
            self.assertEqual(find_kinds(text), ["coordinates"], text)
        self.assertEqual(find_kinds("long: 12." + "3456"), [])

    def test_short_password_and_bearer(self):
        self.assertEqual(find_kinds("MQTT_PASSWORD=" + "hunter2hunter"), ["token"])
        self.assertEqual(find_kinds("Authorization: Bearer " + "a8f3k2l9q0w8e7r6t5y4"), ["token"])


class Hook(unittest.TestCase):
    """Runs the script on staged changes in a throwaway repository."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        self.env = env | {"GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
        self.git("init", "-q")

    def tearDown(self):
        self.tmp.cleanup()

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, env=self.env, check=True)

    def stage(self, name, content):
        Path(self.repo, name).write_text(content, encoding="utf-8")
        self.git("add", name)

    def run_check(self):
        return subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=self.repo,
                              env=self.env, capture_output=True, text=True)

    def test_finding_names_file_line_and_override_without_value(self):
        self.stage("config.yaml", "name: pilot\nhost: " + IP + "\n")
        result = self.run_check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("config.yaml:2: private IP address", result.stderr)
        self.assertIn("git commit --no-verify", result.stderr)
        self.assertNotIn(IP, result.stderr + result.stdout)

    def test_only_added_lines_count(self):
        self.stage("a.txt", "latitude: " + LAT + "\n")
        self.git("-c", "user.name=t", "-c", "user.email=t@example.org",
                 "commit", "-q", "--no-verify", "-m", "x")
        self.stage("a.txt", "latitude: " + LAT + "\nclean line\n")
        self.assertEqual(self.run_check().returncode, 0)

    def test_user_diff_config_cannot_switch_it_off(self):
        self.git("config", "diff.noprefix", "true")
        self.git("config", "diff.mnemonicPrefix", "true")
        self.stage("config.yaml", "host: " + IP + "\n")
        self.assertEqual(self.run_check().returncode, 1)

    def test_line_starting_with_plus_signs_does_not_hide_the_rest(self):
        self.stage("notes.txt", "++ note\nhost: " + IP + "\n")
        self.assertIn("notes.txt:2: private IP address", self.run_check().stderr)

    def test_unusual_file_names(self):
        for name in ['a"b.yaml', "tab\tx.yaml", "my fïle.yaml"]:
            self.stage(name, "host: " + IP + "\n")
        stderr = self.run_check().stderr
        for name in ['a"b.yaml', "tab\tx.yaml", "my fïle.yaml"]:
            self.assertIn(f"  {name}:1: private IP address\n", stderr)

    def test_outside_a_repository_one_line_error(self):
        with tempfile.TemporaryDirectory() as empty:
            result = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=empty,
                                    env=self.env | {"GIT_CEILING_DIRECTORIES": empty},
                                    capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)

    def test_clean_change_is_silent(self):
        self.stage("README.md", "# Title\n")
        result = self.run_check()
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_files_mode(self):
        self.stage("b.env", "HA_TOKEN=" + JWT + "\n")
        result = subprocess.run([sys.executable, "-I", str(SCRIPT), "--files", "b.env"],
                                cwd=self.repo, capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("b.env:1: token", result.stderr)


if __name__ == "__main__":
    unittest.main()
