"""Report new issues and comments in a GitHub repository by number and author only.

Never prints titles or text: the content is read with tools/gh_thread.py, which
labels it by author (.claude/hooks/guard_github_text.py). One line per new
item; meant for the Monitor tool.

Usage: python3 tools/gh_watch.py [--repo OWNER/NAME] [--interval SECONDS]
"""

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone


def new_items(repo: str, since: str, me: str) -> list:
    def api(path):
        out = subprocess.run(["gh", "api", "--paginate", "--slurp", path], capture_output=True, text=True)
        if out.returncode:
            return []
        return [x for page in json.loads(out.stdout) for x in page]
    lines = []
    for c in api(f"repos/{repo}/issues/comments?since={since}&per_page=100"):
        if c["user"]["login"] != me and c["created_at"] >= since:
            lines.append(f"new comment on #{c['issue_url'].rsplit('/', 1)[-1]} by {c['user']['login']} at {c['created_at']}")
    for i in api(f"repos/{repo}/issues?state=all&since={since}&per_page=100"):
        if i["user"]["login"] != me and i["created_at"] >= since:
            kind = "pull request" if "pull_request" in i else "issue"
            lines.append(f"new {kind} #{i['number']} by {i['user']['login']} at {i['created_at']}")
    return lines


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--repo", default="uellue-bot/energymanager")
    p.add_argument("--me", default="uellue-bot", help="the agent's own account, not reported")
    p.add_argument("--interval", type=int, default=300)
    args = p.parse_args(argv)
    since = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    while True:
        time.sleep(args.interval)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        for line in new_items(args.repo, since, args.me):
            print(line + " (read it with tools/gh_thread.py)", flush=True)
        since = now


if __name__ == "__main__":
    sys.exit(main())
