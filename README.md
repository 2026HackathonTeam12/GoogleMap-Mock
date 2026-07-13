# GoogleMap-Mock

Django 기반 Google Map mock 프로젝트입니다.

## Requirements

- Python 3.13+
- Django 6.0+
- MySQL 8+

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

MySQL 접속 정보는 환경변수로 지정합니다.

```bash
export MYSQL_DATABASE="mock_map"
export MYSQL_USER="root"
export MYSQL_PASSWORD="your-password"
export MYSQL_HOST="127.0.0.1"
export MYSQL_PORT="3306"
python manage.py migrate
python manage.py runserver
```

Google Maps JavaScript API와 Places Library를 사용하려면 실행 전에 브라우저용 API 키를 환경변수로 지정합니다.

```bash
export GOOGLE_MAPS_API_KEY="your-google-maps-browser-key"
python manage.py runserver
```

키가 없으면 개발 확인용 OpenStreetMap 지도로 표시됩니다. Google Maps의 실제 장소 클릭과 검색은 API 키가 있을 때만 동작합니다.

## Endpoints

- `GET /` - service status
- `GET /health/` - health check
- `GET /admin/` - Django admin
