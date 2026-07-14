#!/usr/bin/env bash
set -e

if [ -f .env ]; then
  set -a
  . ./.env
  set +a
else
  echo ".env 파일이 없습니다. README.md의 실행 방법을 참고해 생성해주세요." >&2
  exit 1
fi

PYTHON="${VENV_PYTHON:-.venv/bin/python}"
if [ ! -x "$PYTHON" ]; then
  echo "가상환경을 찾을 수 없습니다. README.md의 Quick start로 .venv를 먼저 생성해주세요." >&2
  exit 1
fi

"$PYTHON" manage.py migrate
"$PYTHON" manage.py runserver
