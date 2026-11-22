#!/usr/bin/env bash
# Deploy the stack on the host, and log what runs there.
#
# Usage, in the host's clone of this repository:
#   tools/deploy.sh                        the principal's main branch (origin/main)
#   tools/deploy.sh --test BRANCH REASON   a branch of the bot's fork, for a test
#
# The first form is the normal way. The second runs code that has not been
# reviewed and merged: ask the principal before using it, and never for code
# that writes to a device before its review (AGENTS.md). Both refuse when the
# clone has local changes or commits, and both append one line to
# "$EM_DATA_DIR/deploy.log" before starting the stack: time (UTC), user, mode,
# commit, branch, reason. A line in the log means the code was checked out, not
# that the stack started. Return to main by running the script without arguments.
set -euo pipefail

FORK=${EM_DEPLOY_FORK:-https://github.com/uellue-bot/energymanager.git}
usage="usage: $0 [--test BRANCH REASON]"

fail() {
    echo "$1" >&2
    exit "${2:-1}"
}

mode=main ref=main reason=-
if [ "$#" -gt 0 ]; then
    if [ "$1" != "--test" ] || [ "$#" -ne 3 ] || [ -z "$2" ] || [ -z "$3" ]; then
        fail "$usage" 2
    fi
    mode=test ref=$2 reason=$3
    case $ref$reason in
        *[[:cntrl:]]*) fail "BRANCH and REASON must not contain tabs, newlines or other control characters." 2 ;;
    esac
    case $ref in
        -*) fail "BRANCH must be a branch name, not an option: $ref" 2 ;;
    esac
    git check-ref-format --branch "$ref" > /dev/null 2>&1 || fail "BRANCH is not a valid branch name: $ref" 2
fi

cd "$(git -C "$(dirname "$0")" rev-parse --show-toplevel)"

# The data folder as Compose reads it from .env: CR and one pair of quotes removed.
[ -f .env ] || fail ".env is missing; see the README."
data_dir=$(sed -n 's/^EM_DATA_DIR=//p' .env | tail -n 1 | tr -d '\r')
data_dir=${data_dir#[\"\']}
data_dir=${data_dir%[\"\']}
[ -n "$data_dir" ] || fail "EM_DATA_DIR is not set in .env."
if [ -n "${EM_DATA_DIR:-}" ] && [ "$EM_DATA_DIR" != "$data_dir" ]; then
    fail "EM_DATA_DIR in the environment ($EM_DATA_DIR) differs from .env ($data_dir); Compose would use the environment. Unset it."
fi
[ -d "$data_dir" ] && [ -w "$data_dir" ] || fail "The data folder $data_dir does not exist or is not writable."

if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
    git status --short --untracked-files=no >&2
    fail "The clone has local changes; commit them elsewhere or discard them first. Nothing was deployed."
fi

if [ "$mode" = main ]; then
    git fetch --quiet origin main
    if git rev-parse --verify --quiet refs/heads/main > /dev/null \
            && ! git merge-base --is-ancestor refs/heads/main origin/main; then
        fail "The local main has commits that origin/main does not have; nothing was deployed. Inspect with: git log origin/main..main"
    fi
    git switch --quiet -C main origin/main
    [ "$(git rev-parse HEAD)" = "$(git rev-parse origin/main)" ] || fail "The checkout is not origin/main; nothing was started."
else
    git fetch --quiet -- "$FORK" "refs/heads/$ref"
    git switch --quiet --detach FETCH_HEAD
fi
commit=$(git rev-parse --short HEAD)

# Logged before the start, so the log names the code on disk even if the start fails.
printf '%s\t%s\t%s\t%s\t%s\t%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(id -un)" \
    "$mode" "$commit" "$ref" "$reason" >> "$data_dir/deploy.log"
docker compose up -d --build
echo "Deployed $mode $commit ($ref); logged in $data_dir/deploy.log"
