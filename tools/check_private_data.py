"""Refuse a commit whose added lines contain private data of the site.

Checks for private IPv4 addresses, coordinates and token-like secrets
(requirements 2.9). Run by the hooks in .githooks/: on the staged changes
(pre-commit) and on the commit message (commit-msg, with --files). Uses the
standard library only.
"""

import os
import re
import subprocess
import sys

PRIVATE_IP = re.compile(
    r"(?<![\d.])"
    r"(?:10\.\d{1,3}|172\.(?:1[6-9]|2\d|3[01])|192\.168)\.\d{1,3}\.\d{1,3}"
    r"(?!\d|\.\d)"
)
NUMBER = r"-?\d{1,3}\.\d{3,}"
# The key may carry a prefix or suffix, as in EM_LATITUDE or home_lat.
COORDINATE_KEY = re.compile(
    r"(?i)(?:^|[^a-z])(?:lat|latitude|lon|lng|longitude)(?![a-z])[\w-]*[\"']?\s*[:=]\s*[\"']?"
    + NUMBER
)
COORDINATE_PAIR = re.compile(r"(?<![\d.])(" + NUMBER + r")\s*[,/]\s*(" + NUMBER + r")(?![\d.])")
JWT = re.compile(r"\beyJ[\w-]{8,}\.[\w-]{8,}\.[\w-]{8,}")
BEARER = re.compile(r"(?i)\bbearer\s+[\w.~+/-]{16,}")
# A value is not a secret if it refers to one (${VAR}, <placeholder>), or is a
# path, URL or call. Keys naming a file, URL, path or name hold no secret either.
SECRET_ASSIGNMENT = re.compile(
    r"(?i)[\w-]*(?:token|secret|password|passwd|api[_-]?key)(?![\w-]*(?:_file|_url|_endpoint|_name|_path)\b)"
    r"[\w-]*[\"']?\s*[:=]\s*[\"']?(?![$<])([^\s\"']+)"
)
PASSWORD_KEY = re.compile(r"(?i)passw")
# The shape of the RCT inverter's and battery's serial numbers (4 digits, a
# letter, 9 digits), as Home Assistant's device registry shows them. A serial
# can be enough to claim a device in a vendor's cloud.
DEVICE_SERIAL = re.compile(r"(?<!\w)\d{4}[A-Za-z]\d{9}(?!\w)")


def is_secret_value(match):
    value = match.group(1)
    if "/" in value or "(" in value:
        return False
    minimum = 8 if PASSWORD_KEY.search(match.group(0)) else 16
    return len(value) >= minimum


def find_kinds(text):
    """Return the kinds of private data found in one line of text."""
    kinds = []
    if PRIVATE_IP.search(text):
        kinds.append("private IP address")
    if COORDINATE_KEY.search(text) or any(
        abs(float(m.group(1))) <= 90 and abs(float(m.group(2))) <= 180
        for m in COORDINATE_PAIR.finditer(text)
    ):
        kinds.append("coordinates")
    if (JWT.search(text) or BEARER.search(text)
            or any(is_secret_value(m) for m in SECRET_ASSIGNMENT.finditer(text))):
        kinds.append("token")
    if DEVICE_SERIAL.search(text):
        kinds.append("device serial number")
    return kinds


def git(*args):
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    ).stdout


def staged_added_lines():
    """Yield (path, line number, text) for each line added in the staged changes.

    Each file is diffed on its own, so the path never has to be read back from a
    diff header (which quotes some names and depends on the user's git config).
    """
    paths = git("diff", "--cached", "--name-only", "-z", "--diff-filter=ACMR").split("\0")
    for path in filter(None, paths):
        diff = git("diff", "--cached", "-U0", "--no-color", "--no-ext-diff",
                   "--no-textconv", "--", f":(top,literal){path}")
        lineno, in_hunk = 0, False
        for line in diff.splitlines():
            if line.startswith("@@"):
                lineno, in_hunk = int(re.match(r"@@ -\S+ \+(\d+)", line).group(1)), True
            elif in_hunk and line.startswith("+"):
                yield path, lineno, line[1:]
                lineno += 1


def file_lines(paths):
    """Yield (path, line number, text) for every line of the given files.

    Directories, such as symlinks to them, are skipped.
    """
    for path in paths:
        if os.path.isdir(path):
            continue
        with open(path, encoding="utf-8", errors="replace") as f:
            for lineno, text in enumerate(f, start=1):
                yield path, lineno, text.rstrip("\n")


def main(argv):
    if argv[:1] == ["--files"]:
        if len(argv) < 2:
            print("usage: check_private_data.py [--files FILE...]", file=sys.stderr)
            return 2
        lines = file_lines(argv[1:])
    else:
        lines = staged_added_lines()
    try:
        findings = [
            f"{path}:{lineno}: {kind}"
            for path, lineno, text in lines
            for kind in find_kinds(text)
        ]
    except (subprocess.CalledProcessError, OSError) as e:
        reason = e.stderr.strip() if isinstance(e, subprocess.CalledProcessError) else e
        print(f"check_private_data: cannot check: {reason}", file=sys.stderr)
        return 2
    if not findings:
        return 0
    print("Private data found (the values are not shown):", file=sys.stderr)
    for finding in findings:
        print(f"  {finding}", file=sys.stderr)
    print(
        "Move the value to a local file that git ignores, such as .env.\n"
        "If a finding is not private (e.g. a version number), commit anyway with:\n"
        "  git commit --no-verify",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
