#!/usr/bin/env bash
# Creates a NEW PRIVATE repository. Never overwrites an existing repository.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
root="$(pwd -P)"
target="${1:-graiola/garmin-connect-mcp}"
[[ "$target" =~ ^[A-Za-z0-9-]+/[A-Za-z0-9._-]+$ ]] || { echo 'Expected owner/repository.' >&2; exit 1; }
for command in gh git python3; do
  command -v "$command" >/dev/null || { echo "Install $command locally first." >&2; exit 1; }
done
gh auth status --hostname github.com >/dev/null 2>&1 || {
  echo 'Authenticate locally: gh auth login --hostname github.com --git-protocol https --web --scopes workflow' >&2
  exit 1
}
login="$(gh api user --jq .login)"
[[ "${target%%/*}" == "$login" ]] || { echo "Authenticated as $login, but target owner differs. No changes made." >&2; exit 1; }
if gh repo view "$target" >/dev/null 2>&1; then
  echo "Repository $target already exists. Refusing to modify it automatically." >&2
  exit 1
fi
existing_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
[[ -z "$existing_root" || "$existing_root" == "$root" ]] || { echo 'Refusing to use a parent repository.' >&2; exit 1; }
[[ -d .git ]] || git init --initial-branch=main
if git remote get-url origin >/dev/null 2>&1; then
  echo 'An origin remote already exists; review it manually. Nothing was pushed.' >&2
  exit 1
fi
# Explicit allowlist: never stage the entire working directory indiscriminately.
git add -- pyproject.toml README.md LICENSE SECURITY.md AGENTS.md .gitignore .dockerignore .env.example Dockerfile requirements-tested.txt src tests scripts docs .github
python3 scripts/check_staged_secrets.py
if ! git diff --cached --quiet; then
  if git var GIT_AUTHOR_IDENT >/dev/null 2>&1; then
    git commit -m 'feat: add private read-only Garmin Personal API MCP connector'
  else
    git -c user.name='Connector bootstrap' -c user.email='connector@localhost' commit -m 'feat: add private read-only Garmin Personal API MCP connector'
  fi
fi
gh auth setup-git --hostname github.com
gh repo create "$target" --private --source=. --remote=origin --push \
  --description 'Private read-only MCP connector for the official Garmin Connect Personal API'
visibility="$(gh repo view "$target" --json isPrivate --jq .isPrivate)"
[[ "$visibility" == true ]] || { echo 'Unexpected repository visibility; inspect GitHub immediately.' >&2; exit 1; }
echo 'Created and pushed PRIVATE repository:'
gh repo view "$target" --json url --jq .url
