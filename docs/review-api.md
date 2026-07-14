# Review API / OAuth 명세

## OAuth Flow

이 서버는 OAuth 로그인 서버와 리뷰 API 서버를 모두 처리합니다. 외부 서버를 분리하지 않습니다.

사용 흐름:

1. 클라이언트가 `/oauth/authorize/`를 팝업으로 엽니다.
2. 점주가 팝업에서 로그인합니다.
3. 서버가 `redirect_uri`로 `code`, `client_id`, `state`를 전달합니다.
4. 클라이언트가 `/oauth/token/`에서 `code`를 access token과 refresh token으로 교환합니다.
5. 리뷰 API 호출 시 `Authorization: Bearer {access_token}` 헤더를 보냅니다.
6. access token이 만료되면 refresh token으로 새 access token을 발급받습니다.
7. 로그아웃 시 `/oauth/revoke/`로 token을 폐기합니다.

Access token은 짧게 유지하고, refresh token으로 갱신합니다.

## OAuth Endpoints

### 로그인 팝업 열기

`GET /oauth/authorize/`

Query:

| 이름 | 필수 | 설명 |
| --- | --- | --- |
| `response_type` | Y | `code` |
| `client_id` | Y | 점주 OAuth client ID |
| `redirect_uri` | Y | code를 받을 callback URL |
| `state` | N | CSRF 방지용 임의 문자열 |
| `scope` | N | `owner:reviews` |

성공 시:

```text
{redirect_uri}?code=oac_xxx&client_id=oci_xxx&state=state-value
```

### Token 발급

`POST /oauth/token/`

Authorization code 교환:

```json
{
  "grant_type": "authorization_code",
  "client_id": "oci_xxx",
  "client_secret": "ocs_xxx",
  "code": "oac_xxx",
  "redirect_uri": "http://localhost:8000/oauth/callback/",
  "state": "state-value"
}
```

Refresh token 교환:

```json
{
  "grant_type": "refresh_token",
  "client_id": "oci_xxx",
  "client_secret": "ocs_xxx",
  "refresh_token": "ort_xxx"
}
```

`client_id`와 `client_secret`은 `/owner/account/`에서 확인합니다. 서버 간(confidential client) 연동에서는 두 값 모두 `/oauth/token/` 요청에 포함해야 합니다.

응답:

```json
{
  "access_token": "oat_xxx",
  "refresh_token": "ort_xxx",
  "token_type": "Bearer",
  "expires_in": 900,
  "refresh_expires_in": 2592000,
  "scope": "owner:reviews",
  "place_id": "google-place-id",
  "place_name": "가게명"
}
```

### Token 폐기

`POST /oauth/revoke/`

```json
{
  "token": "oat_xxx 또는 ort_xxx",
  "client_id": "oci_xxx",
  "client_secret": "ocs_xxx"
}
```

점주 웹 로그아웃(`/owner/logout/`) 시에도 해당 점주의 활성 OAuth token은 폐기됩니다.

### 테스트 페이지

`GET /oauth/test/`

OAuth 팝업 로그인, callback 수신, token 교환, refresh, revoke, token 남은 시간, 내 가게 리뷰 조회를 브라우저에서 확인할 수 있습니다.

`GET /oauth/redirect-viewer/`

페이지 진입 시 OAuth 로그인 팝업을 자동으로 열고, authorize URL, redirect URI, callback으로 전달받은 `code`, `client_id`, `state`, token 교환 결과, token 남은 시간, bearer token으로 조회한 내 가게 리뷰까지 단계별로 표시합니다. 각 단계의 HTTP 요청 정보와 응답 JSON도 함께 표시합니다.

## 리뷰 API

### 리뷰 목록 조회

공개 조회:

`GET /api/reviews/?place_id={place_id}`

점주 token 기반 조회:

`GET /api/reviews/`

Header:

```http
Authorization: Bearer oat_xxx
```

### 리뷰 작성

`POST /api/reviews/`

```json
{
  "place_id": "google-place-id",
  "place_name": "가게명",
  "author_name": "방문자",
  "rating": 5,
  "content": "좋았습니다.",
  "delete_password": "1234"
}
```

### 리뷰 삭제

`DELETE /api/reviews/{review_id}/`

```json
{
  "delete_password": "1234"
}
```

## 점주 답글 API

아래 API는 점주 로그인 세션 또는 bearer token이 필요합니다. bearer token을 쓰는 경우 token의 `place_id`와 리뷰의 `place_id`가 같아야 합니다.

### 답글 작성

`POST /api/reviews/{review_id}/reply/`

```json
{
  "content": "방문해 주셔서 감사합니다."
}
```

### 답글 수정

`PATCH /api/reviews/{review_id}/reply/{reply_id}/`

```json
{
  "content": "수정된 답글입니다."
}
```

### 답글 삭제

`DELETE /api/reviews/{review_id}/reply/{reply_id}/`

## OpenAPI / Swagger

- OpenAPI JSON: `GET /api/openapi.json`
- 정적 OpenAPI 파일: `docs/review-openapi.json`
- Swagger UI: `GET /api/docs/`
- OAuth 테스트 UI: `GET /oauth/test/`
- OAuth redirect 값 확인 UI: `GET /oauth/redirect-viewer/`
