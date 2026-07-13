# GoogleMap-Mock

Django 기반 Google Map mock 프로젝트입니다.

## Requirements

- Python 3.13+
- Django 6.0+

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Endpoints

- `GET /` - service status
- `GET /health/` - health check
- `GET /admin/` - Django admin
