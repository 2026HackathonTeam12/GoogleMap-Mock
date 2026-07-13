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

Google Maps JavaScript API를 사용하려면 실행 전에 브라우저용 API 키를 환경변수로 지정합니다.

```bash
export GOOGLE_MAPS_API_KEY="your-google-maps-browser-key"
python manage.py runserver
```

키가 없으면 개발 확인용 OpenStreetMap 지도로 표시됩니다.

## Endpoints

- `GET /` - service status
- `GET /api/places/` - place list used by the map
- `GET /health/` - health check
- `GET /admin/` - Django admin
