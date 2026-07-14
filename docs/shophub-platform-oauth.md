# ShopHub Platform OAuth 연동 스펙 (MockMap 구현안)

ShopHub가 Google OAuth와 같은 UX로 MockMap을 연동하기 위한 **플랫폼 OAuth client** 스펙입니다.

- **OAuth 로그인/동의 UI**: MockMap이 제공 (`/oauth/authorize/`)
- **ShopHub BE**: redirect, callback, token 교환, 리뷰 sync
- **ShopHub FE**: [연동] 버튼 → BE `GET /api/integrations/MOCK_MAP/oauth/start` 만 호출
- **사용자**: MockMap 점주 계정으로 로그인 (client_id/secret 직접 입력 없음)

---

## 1. 배경

### 현재 (Owner OAuth Client)

- `client_id` / `client_secret`이 **점주(가게)마다** `OwnerProfile`에 발급됨
- `/oauth/authorize/`의 `client_id`로 **특정 점주**가 authorize 요청 시작 시점에 고정됨
- ShopHub는 연동 전 `PUT .../oauth/credentials`로 점주 credentials를 저장해야 함

### 목표 (Platform OAuth Client)

- ShopHub용 **플랫폼 client 1쌍** (env / DB)
- authorize URL의 `client_id` = ShopHub platform ID (고정)
- **로그인한 MockMap 점주**의 `place_id`가 token 응답에 포함됨
- ShopHub BE만 `client_secret` 보관

---

## 2. 역할 분담

```text
[ShopHub FE]  연동 클릭
      ↓
[ShopHub BE]  GET /api/integrations/MOCK_MAP/oauth/start?storeId=
      ↓ 302
[MockMap]     GET /oauth/authorize/?client_id=SHOPHUB&redirect_uri=...&state=...
      ↓ 점주 로그인 (OAuth page)
[MockMap]     302 redirect_uri?code=oac_...&state=...
      ↓
[ShopHub BE]  GET /api/integrations/MOCK_MAP/oauth/callback
              POST /oauth/token/ (authorization_code + platform secret)
      ↓ place_id 저장 + 리뷰 sync
[ShopHub FE]  /integrations/oauth/callback?success=true
```

---

## 3. 데이터 모델 (MockMap)

### 3.1 신규: `PlatformOAuthClient`

점주 client와 분리된 **서드파티 앱** 등록용.

| 필드 | 타입 | 설명 |
|------|------|------|
| `name` | string | 예: `ShopHub` |
| `client_id` | string, unique | 예: `oci_shophub` (또는 `oci_` + random) |
| `client_secret` | string | hashed 저장 권장 |
| `redirect_uris` | text/json | 허용 callback URL 목록 |
| `scopes` | string | 기본 `owner:reviews` |
| `is_active` | bool | 비활성 시 authorize 거부 |
| `created_at` | datetime | |

### 3.2 기존 모델 유지

- `OwnerProfile.client_id/secret` — 점주 직접 API 연동·레거시용 **유지**
- `OwnerAuthorizationCode`, `OwnerAccessToken` — platform flow에서도 **owner FK**는 로그인한 점주

### 3.3 (선택) AuthorizationCode에 platform FK

```python
class OwnerAuthorizationCode(models.Model):
    owner = models.ForeignKey(OwnerProfile, ...)
    platform_client = models.ForeignKey(PlatformOAuthClient, null=True, blank=True, ...)
    ...
```

token 교환 시 platform client + owner 조합 검증에 사용.

---

## 4. 환경 설정 (MockMap)

`.env` 또는 Django settings:

```bash
# ShopHub platform OAuth (개발)
SHOPHUB_OAUTH_CLIENT_ID=oci_shophub_dev
SHOPHUB_OAUTH_CLIENT_SECRET=ocs_...   # migrate/seed 시 1회 생성
SHOPHUB_OAUTH_REDIRECT_URIS=http://localhost:8080/api/integrations/MOCK_MAP/oauth/callback
```

프로덕션 redirect URI 추가:

```text
https://api.shophub.example/api/integrations/MOCK_MAP/oauth/callback
```

---

## 5. `/oauth/authorize/` 변경

### 5.1 Request (변경 없음, ShopHub BE가 호출)

```http
GET /oauth/authorize/?response_type=code
  &client_id=oci_shophub_dev
  &redirect_uri=http://localhost:8080/api/integrations/MOCK_MAP/oauth/callback
  &state={uuid}
  &scope=owner:reviews
```

### 5.2 `validate_authorize_request` 로직 변경

```python
def resolve_oauth_client(client_id: str) -> tuple[ClientKind, OwnerProfile | PlatformOAuthClient]:
    # 1) PlatformOAuthClient 조회
    platform = PlatformOAuthClient.objects.filter(client_id=client_id, is_active=True).first()
    if platform:
        return ClientKind.PLATFORM, platform

    # 2) 기존 OwnerProfile client (하위 호환)
    try:
        return ClientKind.OWNER, OwnerProfile.objects.get(client_id=client_id)
    except OwnerProfile.DoesNotExist:
        raise InvalidClient
```

**Platform client인 경우:**

- `redirect_uri`가 `platform.redirect_uris`에 포함되는지 검증
- **owner는 아직 미정** — 로그인 후 결정

**Owner client인 경우 (기존):**

- 현재와 동일 (client_id = 특정 owner)

### 5.3 OAuth Page UI (`oauth_authorize.html`)

로그인된 세션이 있어도 **자동 승인하지 않습니다.**

| 상태 | 화면 |
|------|------|
| 미로그인 | 계정/비밀번호 로그인 후 코드 발급 |
| 이미 로그인 | 연결될 가게 표시 + **허용하고 계속** / **다른 계정으로 로그인** |
| 허용 POST (`action=approve`) | authorization code redirect |
| 계정 전환 POST (`action=switch`) | 로그인 폼 표시 |

| 가입 링크 | `/owner/signup/` |

Platform client일 때 표시 변경:

| 항목 | Owner client (기존) | Platform client (ShopHub) |
|------|---------------------|---------------------------|
| 요청 앱 | `profile.place_name` | `ShopHub` (platform.name) |
| 연동 가게 | (암시적) | 로그인 **후** place_name 표시 또는 로그인 폼 아래 안내 |
| 권한 | 리뷰 조회·답글 | 동일 |
| 가입 링크 | 없음 | `/owner/signup/?next=/oauth/authorize/?...` (query 유지) |

**로그인 성공 후 (platform flow):**

- `redirect_with_authorization_code(logged_in_owner_profile, params, platform_client=...)`
- code는 **로그인한 owner**에 바인딩

### 5.4 GET + 이미 MockMap 세션 로그인된 경우

- Platform/owner client 모두 **즉시 code redirect 하지 않음**
- 동의 화면(`mode=consent`)을 보여 주고, `action=approve` POST 시에만 code 발급
- `action=switch` 시 로그인 폼으로 전환해 다른 계정·비밀번호 재입력 가능

### 5.5 Redirect (성공)

```text
{redirect_uri}?code=oac_xxx&state={state}
```

`client_id` query param은 **선택** (ShopHub BE는 code + state만 사용해도 됨). 하위 호환 위해 유지 가능.

---

## 6. `/oauth/token/` 변경

### 6.1 Authorization code 교환

**Request (ShopHub BE → MockMap):**

```json
POST /oauth/token/
Content-Type: application/json

{
  "grant_type": "authorization_code",
  "client_id": "oci_shophub_dev",
  "client_secret": "ocs_...",
  "code": "oac_xxx",
  "redirect_uri": "http://localhost:8080/api/integrations/MOCK_MAP/oauth/callback",
  "state": "{uuid}"
}
```

**검증 (platform client):**

1. `client_id` → `PlatformOAuthClient` 조회
2. `client_secret` 일치
3. `code` → `OwnerAuthorizationCode` (used/expired/redirect_uri/state 검증)
4. code.owner = token 발급 대상 owner
5. (선택) code.platform_client == 요청 platform client

**Response (기존과 동일 — ShopHub BE 파싱 호환):**

```json
{
  "access_token": "oat_xxx",
  "refresh_token": "ort_xxx",
  "token_type": "Bearer",
  "expires_in": 900,
  "refresh_expires_in": 2592000,
  "scope": "owner:reviews",
  "client_id": "oci_shophub_dev",
  "place_id": "ChIJ...",
  "place_name": "스타벅스 강남점"
}
```

`place_id` / `place_name`은 **로그인한 점주(OwnerProfile)** 에서 가져옴.

### 6.2 Refresh token

- `grant_type=refresh_token` + platform `client_id`/`client_secret`
- refresh token이 platform flow로 발급된 경우 platform secret으로 갱신
- 응답에 `place_id` 포함 (기존 `build_token_response` 유지)

### 6.3 Revoke

- 기존 `/oauth/revoke/` + platform client credentials 지원

---

## 7. Redirect URI Allowlist

Platform client는 **고정 allowlist**만 허용.

개발:

```text
http://localhost:8080/api/integrations/MOCK_MAP/oauth/callback
```

`is_allowed_redirect_uri`를 platform client일 때 allowlist 기반으로 분기.

Owner client (기존)는 localhost/상대경로 규칙 유지.

---

## 8. ShopHub BE 연동 계약 (MockMap 구현 후)

ShopHub BE `.env`:

```bash
MOCK_MAP_API_BASE_URL=http://localhost:8000
MOCK_MAP_OAUTH_CLIENT_ID=oci_shophub_dev
MOCK_MAP_OAUTH_CLIENT_SECRET=ocs_...
MOCK_MAP_OAUTH_REDIRECT_URI=http://localhost:8080/api/integrations/MOCK_MAP/oauth/callback
```

BE 변경 요약:

| 항목 | 변경 |
|------|------|
| `MockMapOwnerOAuthService.buildAuthorizationUrl` | store credentials 대신 **env platform client_id** |
| `completeAuthorization` | env platform **client_secret**으로 token 교환 |
| `PUT .../oauth/credentials` | **deprecated** (optional 유지 가능) |
| OAuth callback 직후 | `syncMockMapReviews(storeId)` 자동 호출 |
| `StoreMockMapConnectionEntity` | platform flow: owner client_id 필드 nullable 또는 platform flag |

FE 변경:

- `MockMapConnectForm` **제거**
- [연동] → `startOAuth("MOCK_MAP", storeId)` 만

---

## 9. 하위 호환

| Flow | 지원 |
|------|------|
| Owner client (기존 `/owner/account/` credentials) | ✅ 유지 |
| Platform client (ShopHub) | ✅ 신규 |
| `/oauth/test/`, redirect-viewer | platform client 테스트 추가 |

---

## 10. OAuth Page UX 체크리스트 (MockMap)

- [ ] Platform client 요청 시 앱 이름 "ShopHub" 표시
- [ ] "MockMap 계정이 없으신가요? 가입하기" → signup + authorize query 복귀
- [ ] 로그인 실패 / owner profile 없음 → 명확한 에러
- [ ] (선택) 동의 문구: "{place_name} 리뷰를 ShopHub에서 조회·답글합니다"
- [ ] 모바일 대응 (기존 owner-page 스타일 재사용)

---

## 11. 테스트 케이스 (MockMap)

```python
def test_platform_authorize_requires_login():
    # client_id=platform, 미로그인 → login form 200

def test_platform_authorize_redirects_after_owner_login():
    # POST login → redirect_uri?code=

def test_platform_token_exchange_returns_place_id():
    # code + platform secret → place_id in JSON

def test_platform_token_rejects_wrong_secret():
    # 401 invalid_client

def test_platform_rejects_disallowed_redirect_uri():
    # 400 redirect_uri is not allowed

def test_owner_client_flow_still_works():
    # 기존 owner client_id regression
```

---

## 12. 구현 순서 제안

1. `PlatformOAuthClient` 모델 + migration + dev seed (`oci_shophub_dev`)
2. `validate_authorize_request` / `oauth_token` platform 분기
3. `oauth_authorize.html` platform UI (앱명, 가입 링크)
4. redirect URI allowlist
5. 테스트 + `/oauth/test/` platform 탭
6. ShopHub BE: env platform client만 사용하도록 refactor
7. ShopHub FE: credentials 폼 제거

---

## 13. OpenAPI (`api-spec.yml`) 업데이트

- `PlatformOAuthClient` 설명 추가
- `/oauth/authorize/`에 platform vs owner client 구분
- `/oauth/token/` grant_type: `authorization_code`, `refresh_token` 명시 (client_credentials-only 설명 수정)

---

## 14. 한 줄 요약

**MockMap이 ShopHub용 platform OAuth client + authorize 로그인 페이지를 제공하면, ShopHub는 Google OAuth처럼 버튼 하나 → MockMap 로그인 → 리뷰 자동 연동이 가능하다.**

ShopHub BE callback URL (개발):  
`http://localhost:8080/api/integrations/MOCK_MAP/oauth/callback`
