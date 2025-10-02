#!/usr/bin/env bash
set -euo pipefail
# Uso: scripts/pr-merge-quick.sh [PR_NUMBER] [BASE] [ACTION] [MERGE_MODE]
# Ex.: scripts/pr-merge-quick.sh 3 master prefer-codex merge
# MERGE_MODE: merge | squash | rebase | none (default: merge)

REPO_SLUG="danzeroum/BuildToFlipV6-"
PR_NUMBER="${1:-}"
BASE="${2:-master}"
ACTION="${3:-prefer-codex}"     # prefer-codex | prefer-base
MERGE_MODE="${4:-merge}"        # merge | squash | rebase | none

need(){ command -v "$1" >/dev/null 2>&1 || { echo "Falta '$1' no PATH"; exit 1; }; }
need git; need gh
[ -d .git ] || { echo "Rode dentro da pasta do repositório"; exit 1; }

if [ -z "$PR_NUMBER" ]; then
  PR_NUMBER="$(gh pr list -R "$REPO_SLUG" --state open --json number,createdAt -q 'sort_by(.createdAt) | (last.number)')"
  [ -n "$PR_NUMBER" ] || { echo "Nenhuma PR aberta em $REPO_SLUG"; exit 1; }
fi

echo "➜ Repo: $REPO_SLUG | PR: #$PR_NUMBER | Base: $BASE | Ação: $ACTION"
gh pr checkout -R "$REPO_SLUG" "$PR_NUMBER"

git fetch origin
if [ "$ACTION" = "prefer-codex" ]; then
  git merge --no-edit -X ours  "origin/$BASE" || true
else
  git merge --no-edit -X theirs "origin/$BASE" || true
fi

[ -f .git/index.lock ] && rm -f .git/index.lock || true
FILES="$(git diff --name-only --diff-filter=U || true)"
if [ -n "${FILES:-}" ]; then
  echo "➜ Resolvendo conflitos em lote…"
  if [ "$ACTION" = "prefer-codex" ]; then
    echo "$FILES" | xargs -I{} git checkout --ours  -- "{}"
    MSG="merge: prefer Codex (ours) in conflicts [auto]"
  else
    echo "$FILES" | xargs -I{} git checkout --theirs -- "{}"
    MSG="merge: prefer base (theirs) in conflicts [auto]"
  fi
  git add -A
  git commit -m "$MSG"
fi

git push
echo "✅ PR #$PR_NUMBER atualizada (base=$BASE | ação=$ACTION)."

if [ "$MERGE_MODE" != "none" ]; then
  case "$MERGE_MODE" in
    merge)  gh pr merge -R "$REPO_SLUG" "$PR_NUMBER" --merge  ;;
    squash) gh pr merge -R "$REPO_SLUG" "$PR_NUMBER" --squash ;;
    rebase) gh pr merge -R "$REPO_SLUG" "$PR_NUMBER" --rebase ;;
    *) echo "Modo de merge inválido: $MERGE_MODE"; exit 1 ;;
  esac
  echo "🎉 PR #$PR_NUMBER mesclada com modo: $MERGE_MODE"
fi
