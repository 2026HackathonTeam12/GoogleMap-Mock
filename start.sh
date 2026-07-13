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

python3 manage.py migrate
python3 manage.py runserver
