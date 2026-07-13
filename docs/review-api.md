# Review API 명세

## 인증

점주 API는 OAuth `client_credentials` 방식으로 인증합니다. OAuth 서버와 리소스 서버는 모두 이 Django 서버에서 처리합니다.

점주 자격증명은 `/owner/account/`에서 확인합니다.

- `client_id`: 점주 계정의 공개 식별자
- `client_secret`: 점주 계정의 비밀키
- Access token 만료: 1시간
- 보호 API 헤더: `Authorization: Bearer {access_token}`

### Access Token 발급

`POST /oauth/token/`

요청:

```json
{
  "grant_type": "client_credentials",
  "client_id": "oci_xxx",
  "client_secret": "ocs_xxx"
}
```

응답:

```json
{
  "access_token": "oat_xxx",
  "token_type": "Bearer",
  "expires_in": 3600,
  "scope": "owner:reviews",
  "place_id": "google-place-id",
  "place_name": "가게명"
}
```

## 리뷰 API

### 리뷰 목록 조회

`GET /api/reviews/?place_id={place_id}`

공개 조회입니다. `place_id`를 넘기면 해당 장소 리뷰를 반환합니다.

`GET /api/reviews/`

점주 bearer token만 넘기면 token의 `place_id`를 사용해 점주 업장 리뷰를 반환합니다.

### 리뷰 작성

`POST /api/reviews/`

요청:

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

요청:

```json
{
  "delete_password": "1234"
}
```

## 점주 답글 API

아래 API는 점주 로그인 세션 또는 bearer token이 필요합니다. bearer token을 쓰는 경우 token의 점주 업장에 속한 리뷰만 처리할 수 있습니다.

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

성공 시 삭제된 답글이 제거된 리뷰 객체를 반환합니다.

## OpenAPI / Swagger

- OpenAPI JSON: `GET /api/openapi.json`
- 정적 OpenAPI 파일: `docs/review-openapi.json`
- Swagger UI: `GET /api/docs/`
