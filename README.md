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

프로젝트 실행은 `.env`와 `start.sh`를 사용합니다. 두 파일은 로컬 환경 파일이므로 Git에는 포함하지 않습니다.

`.env` 파일을 생성합니다.

```bash
GOOGLE_MAPS_API_KEY="your-google-maps-browser-key"
MYSQL_DATABASE="googlemap"
MYSQL_USER="root"
MYSQL_PASSWORD="your-password"
MYSQL_HOST="127.0.0.1"
MYSQL_PORT="3306"
```

실행은 항상 `start.sh`로 시작합니다. `start.sh`는 `.env`를 로드한 뒤 마이그레이션과 개발 서버 실행을 수행합니다.

```bash
./start.sh
```

직접 명령을 실행할 때도 `.env`를 먼저 로드하면 됩니다.

```bash
set -a
. ./.env
set +a
python3 manage.py migrate
python3 manage.py runserver
```

Google Maps JavaScript API와 Places Library를 사용하려면 실행 전에 브라우저용 API 키를 환경변수로 지정합니다.

```bash
GOOGLE_MAPS_API_KEY="your-google-maps-browser-key"
```

키가 없으면 개발 확인용 OpenStreetMap 지도로 표시됩니다. Google Maps의 실제 장소 클릭과 검색은 API 키가 있을 때만 동작합니다.

## Reviews

- 사용자는 지도에서 장소를 선택한 뒤 상세 패널에서 리뷰를 작성할 수 있습니다.
- 점주는 `/owner/signup/`에서 계정을 만들면서 자신의 가게 위치 ID를 등록합니다. 가게명은 선택 항목입니다.
- 지도에서 가게를 선택한 뒤 상세 패널의 `점주로 등록하기`를 누르면 해당 가게 정보가 채워진 가입 화면으로 이동합니다.
- 점주 답글은 해당 가게를 가진 점주 로그인 세션 또는 OAuth bearer token으로만 작성할 수 있습니다.
- OAuth `client_id`와 `client_secret`은 `/owner/account/`에서 확인하고 재발급할 수 있습니다.
- OAuth token 교환(`/oauth/token/`)과 revoke(`/oauth/revoke/`)는 **client_id + client_secret** 검증이 필요합니다 (Google OAuth confidential client 방식).
- 점주 웹 로그인은 `/owner/login/`에서 시작하며 로그인 후 `/owner/account/`로 이동합니다.
- API 명세는 [docs/review-api.md](docs/review-api.md)에서 확인할 수 있습니다.
- OpenAPI 문서는 `GET /api/openapi.json` 또는 [docs/review-openapi.json](docs/review-openapi.json)에서 확인할 수 있습니다.
- Swagger UI는 `/api/docs/`에서 확인할 수 있고, 발급받은 bearer token으로 보호 API를 테스트합니다.
- `GET /oauth/authorize/`는 점주 로그인 팝업을 열고 authorization code를 callback으로 전달합니다.
- `POST /oauth/token/`은 authorization code 또는 refresh token으로 access token을 발급합니다.
- `GET /oauth/test/`에서 팝업 로그인, callback, token 교환, refresh, 내 가게 리뷰 조회를 확인할 수 있습니다.
- `GET /api/reviews/`는 `place_id` 쿼리 없이도 점주 bearer token만 보내면 해당 가게의 리뷰를 반환합니다.

## Endpoints

- `GET /` - map page
- `GET /health/` - health check
- `GET /admin/` - Django admin
- `GET /owner/signup/` - owner signup with place selection
- `GET /owner/account/` - owner OAuth credential page
- `GET /oauth/authorize/` - owner OAuth login and authorization code page
- `POST /oauth/token/` - issue owner OAuth access token with authorization code or refresh token
- `POST /oauth/revoke/` - revoke OAuth access or refresh token
- `GET /oauth/test/` - OAuth popup flow test page
- `GET /api/reviews/?place_id={place_id}` - review list
- `POST /api/reviews/` - create review
- `DELETE /api/reviews/{review_id}/` - delete review with password
- `POST /api/reviews/{review_id}/reply/` - owner reply
- `GET /api/openapi.json` - OpenAPI 3.0 review API schema
- `GET /api/docs/` - Swagger UI
