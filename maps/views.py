import base64
import binascii
import json

from django.conf import settings
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.views import redirect_to_login
from django.db import IntegrityError, transaction
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .models import OwnerAccessToken, OwnerProfile, Review, ReviewReply


def index(request):
    owner_profile = get_user_owner_profile(request.user)
    return render(
        request,
        'maps/index.html',
        {
            'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
            'is_owner': bool(owner_profile),
            'owner_place_id': owner_profile.place_id if owner_profile else '',
            'owner_place_name': owner_profile.place_name if owner_profile else '',
        },
    )


def health(request):
    return JsonResponse({'status': 'ok'})


@csrf_exempt
def review_collection(request):
    if request.method == 'GET':
        place_id = request.GET.get('place_id', '').strip()
        if not place_id:
            owner_profile = get_owner_profile_by_access_token(request)
            if not owner_profile:
                return JsonResponse({'error': 'place_id or valid OAuth bearer token is required'}, status=400)

            place_id = owner_profile.place_id

        reviews = Review.objects.filter(place_id=place_id).prefetch_related('replies__owner')
        return JsonResponse({
            'data': [serialize_review(review) for review in reviews],
            'place_id': place_id,
        })

    if request.method == 'POST':
        payload, error = read_json_body(request)
        if error:
            return JsonResponse({'error': error}, status=400)

        errors = validate_review_payload(payload)
        if errors:
            return JsonResponse({'errors': errors}, status=400)

        review = Review.objects.create(
            place_id=payload['place_id'].strip(),
            place_name=payload['place_name'].strip(),
            author_name=payload['author_name'].strip(),
            rating=int(payload['rating']),
            content=payload['content'].strip(),
        )
        review.set_delete_password(payload['delete_password'])
        review.save(update_fields=['delete_password_hash'])
        return JsonResponse({'data': serialize_review(review)}, status=201)

    return HttpResponseNotAllowed(['GET', 'POST'])


@csrf_exempt
def review_detail(request, review_id):
    if request.method != 'DELETE':
        return HttpResponseNotAllowed(['DELETE'])

    try:
        review = Review.objects.get(pk=review_id)
    except Review.DoesNotExist:
        return JsonResponse({'error': 'review not found'}, status=404)

    payload, error = read_json_body(request)
    if error:
        return JsonResponse({'error': error}, status=400)

    delete_password = str(payload.get('delete_password', ''))
    if not review.check_delete_password(delete_password):
        return JsonResponse({'error': 'delete password is incorrect'}, status=403)

    review.delete()
    return JsonResponse({'data': {'deleted': True}})


@csrf_exempt
def review_reply(request, review_id):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:
        review = Review.objects.get(pk=review_id)
    except Review.DoesNotExist:
        return JsonResponse({'error': 'review not found'}, status=404)

    owner_profile = get_reply_owner(request, review.place_id)
    if not owner_profile:
        if request.user.is_authenticated:
            return JsonResponse({'error': 'this owner account cannot reply to this place'}, status=403)

        return JsonResponse({'error': 'owner login or valid place API key is required'}, status=401)

    payload, error = read_json_body(request)
    if error:
        return JsonResponse({'error': error}, status=400)

    content, errors = validate_reply_payload(payload)
    if errors:
        return JsonResponse({'errors': errors}, status=400)

    reply = ReviewReply.objects.create(
        review=review,
        owner=owner_profile.user,
        content=content,
    )

    return JsonResponse({'data': serialize_review(reply.review)})


@csrf_exempt
def review_reply_detail(request, review_id, reply_id):
    if request.method not in ('PATCH', 'DELETE'):
        return HttpResponseNotAllowed(['PATCH', 'DELETE'])

    try:
        review = Review.objects.get(pk=review_id)
    except Review.DoesNotExist:
        return JsonResponse({'error': 'review not found'}, status=404)

    owner_profile = get_reply_owner(request, review.place_id)
    if not owner_profile:
        if request.user.is_authenticated:
            return JsonResponse({'error': 'this owner account cannot delete replies for this place'}, status=403)

        return JsonResponse({'error': 'owner login or valid place API key is required'}, status=401)

    try:
        reply = ReviewReply.objects.get(
            pk=reply_id,
            review=review,
            owner=owner_profile.user,
        )
    except ReviewReply.DoesNotExist:
        return JsonResponse({'error': 'reply not found'}, status=404)

    if request.method == 'PATCH':
        payload, error = read_json_body(request)
        if error:
            return JsonResponse({'error': error}, status=400)

        content, errors = validate_reply_payload(payload)
        if errors:
            return JsonResponse({'errors': errors}, status=400)

        reply.content = content
        reply.save(update_fields=['content', 'updated_at'])
        return JsonResponse({'data': serialize_review(review)})

    deleted, _ = ReviewReply.objects.filter(
        pk=reply_id,
        review=review,
        owner=owner_profile.user,
    ).delete()
    if not deleted:
        return JsonResponse({'error': 'reply not found'}, status=404)

    return JsonResponse({'data': serialize_review(review)})


def owner_login(request):
    next_url = request.GET.get('next') or request.POST.get('next') or '/owner/account/'
    context = {
        'next': next_url,
        'errors': {},
        'values': {},
    }

    if request.method == 'GET':
        return render(request, 'maps/owner_login.html', context)

    if request.method != 'POST':
        return HttpResponseNotAllowed(['GET', 'POST'])

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    user = authenticate(request, username=username, password=password)

    if not user:
        context['values'] = {'username': username}
        context['errors'] = {'account': '계정명 또는 비밀번호를 확인해주세요.'}
        return render(request, 'maps/owner_login.html', context, status=400)

    if not get_user_owner_profile(user):
        context['values'] = {'username': username}
        context['errors'] = {'account': '점주로 등록된 계정이 아닙니다.'}
        return render(request, 'maps/owner_login.html', context, status=403)

    login(request, user)
    return redirect(next_url)


def owner_signup(request):
    context = {
        'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
        'values': {
            'place_id': request.GET.get('place_id', '').strip(),
            'place_name': request.GET.get('place_name', '').strip(),
            'place_address': request.GET.get('place_address', '').strip(),
        },
        'errors': {},
    }

    if request.method == 'GET':
        return render(request, 'maps/owner_signup.html', context)

    if request.method != 'POST':
        return HttpResponseNotAllowed(['GET', 'POST'])

    values = {
        'username': request.POST.get('username', '').strip(),
        'place_id': request.POST.get('place_id', '').strip(),
        'place_name': request.POST.get('place_name', '').strip(),
        'place_address': request.POST.get('place_address', '').strip(),
    }
    password = request.POST.get('password', '')
    password_confirm = request.POST.get('password_confirm', '')
    errors = validate_owner_signup(values, password, password_confirm)

    if errors:
        context['values'] = values
        context['errors'] = errors
        return render(request, 'maps/owner_signup.html', context, status=400)

    try:
        with transaction.atomic():
            user = get_user_model().objects.create_user(
                username=values['username'],
                password=password,
                is_staff=True,
            )
            OwnerProfile.objects.create(
                user=user,
                place_id=values['place_id'],
                place_name=values['place_name'] or values['place_id'],
                place_address=values['place_address'],
            )
    except IntegrityError:
        context['values'] = values
        context['errors'] = {'account': '이미 사용 중인 계정명 또는 가게입니다.'}
        return render(request, 'maps/owner_signup.html', context, status=400)

    login(request, user)
    return redirect('maps:owner-account')


def owner_account(request):
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path(), login_url='/owner/login/')

    profile = get_user_owner_profile(request.user)
    if not profile:
        return JsonResponse({'error': 'owner profile is required'}, status=403)

    if request.method == 'POST':
        profile.rotate_client_credentials()
        return redirect('maps:owner-account')

    if request.method != 'GET':
        return HttpResponseNotAllowed(['GET', 'POST'])

    return render(request, 'maps/owner_account.html', {'profile': profile})


def owner_logout(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    logout(request)
    return redirect('maps:index')


def openapi_schema(request):
    return JsonResponse(build_openapi_schema())


def swagger_docs(request):
    return render(request, 'maps/swagger.html')


@csrf_exempt
def oauth_token(request):
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    payload, error = read_request_payload(request)
    if error:
        return JsonResponse({'error': error}, status=400)

    grant_type = str(payload.get('grant_type', 'client_credentials')).strip()
    if grant_type != 'client_credentials':
        return JsonResponse({'error': 'unsupported_grant_type'}, status=400)

    client_id, client_secret = get_client_credentials(request, payload)
    if not client_id or not client_secret:
        return JsonResponse({'error': 'invalid_client'}, status=401)

    try:
        profile = OwnerProfile.objects.get(client_id=client_id, client_secret=client_secret)
    except OwnerProfile.DoesNotExist:
        return JsonResponse({'error': 'invalid_client'}, status=401)

    OwnerAccessToken.objects.filter(owner=profile, expires_at__lte=timezone.now()).delete()
    token = OwnerAccessToken.objects.create(owner=profile)
    expires_in = max(0, int((token.expires_at - timezone.now()).total_seconds()))

    return JsonResponse({
        'access_token': token.token,
        'token_type': 'Bearer',
        'expires_in': expires_in,
        'scope': 'owner:reviews',
        'place_id': profile.place_id,
        'place_name': profile.place_name,
    })


def read_json_body(request):
    try:
        return json.loads(request.body.decode('utf-8') or '{}'), None
    except json.JSONDecodeError:
        return None, 'invalid JSON body'


def read_request_payload(request):
    content_type = request.headers.get('Content-Type', '')
    if content_type.startswith('application/json'):
        return read_json_body(request)

    return request.POST.dict(), None


def validate_review_payload(payload):
    errors = {}
    for field in ('place_id', 'place_name', 'author_name', 'content', 'delete_password'):
        if not str(payload.get(field, '')).strip():
            errors[field] = f'{field} is required'

    try:
        rating = int(payload.get('rating'))
    except (TypeError, ValueError):
        errors['rating'] = 'rating must be an integer from 1 to 5'
    else:
        if rating < 1 or rating > 5:
            errors['rating'] = 'rating must be an integer from 1 to 5'

    if len(str(payload.get('author_name', '')).strip()) > 80:
        errors['author_name'] = 'author_name must be 80 characters or fewer'
    if len(str(payload.get('content', '')).strip()) > 2000:
        errors['content'] = 'content must be 2000 characters or fewer'
    if len(str(payload.get('delete_password', '')).strip()) < 4:
        errors['delete_password'] = 'delete_password must be at least 4 characters'

    return errors


def validate_owner_signup(values, password, password_confirm):
    errors = {}
    for field in ('username', 'place_id'):
        if not values[field]:
            errors[field] = '필수 항목입니다.'

    if len(values['username']) > 150:
        errors['username'] = '150자 이하로 입력해주세요.'
    if len(values['place_id']) > 255:
        errors['place_id'] = '255자 이하로 입력해주세요.'
    if len(values['place_name']) > 255:
        errors['place_name'] = '255자 이하로 입력해주세요.'
    if len(values['place_address']) > 500:
        errors['place_address'] = '500자 이하로 입력해주세요.'
    if len(password) < 8:
        errors['password'] = '비밀번호는 8자 이상이어야 합니다.'
    if password != password_confirm:
        errors['password_confirm'] = '비밀번호가 일치하지 않습니다.'

    return errors


def validate_reply_payload(payload):
    content = str(payload.get('content', '')).strip()
    if not content:
        return content, {'content': 'content is required'}
    if len(content) > 2000:
        return content, {'content': 'content must be 2000 characters or fewer'}

    return content, {}


def has_owner_profile(user):
    return bool(user.is_authenticated and get_user_owner_profile(user))


def get_user_owner_profile(user):
    if not user.is_authenticated:
        return None

    try:
        return user.owner_profile
    except OwnerProfile.DoesNotExist:
        return None


def get_reply_owner(request, place_id):
    profile = get_user_owner_profile(request.user)
    if profile and profile.place_id == place_id:
        return profile

    profile = get_owner_profile_by_access_token(request)
    if profile and profile.place_id == place_id:
        return profile

    return None


def get_client_credentials(request, payload):
    authorization = request.headers.get('Authorization', '')
    if authorization.startswith('Basic '):
        encoded = authorization.removeprefix('Basic ').strip()
        try:
            decoded = base64.b64decode(encoded).decode('utf-8')
        except (binascii.Error, UnicodeDecodeError):
            return '', ''

        client_id, separator, client_secret = decoded.partition(':')
        if separator:
            return client_id, client_secret

    return (
        str(payload.get('client_id', '')).strip(),
        str(payload.get('client_secret', '')).strip(),
    )


def get_owner_profile_by_access_token(request):
    authorization = request.headers.get('Authorization', '')
    if not authorization.startswith('Bearer '):
        return None

    token_value = authorization.removeprefix('Bearer ').strip()
    if not token_value:
        return None

    try:
        token = OwnerAccessToken.objects.select_related('owner', 'owner__user').get(token=token_value)
    except OwnerAccessToken.DoesNotExist:
        return None

    if token.is_expired:
        token.delete()
        return None

    return token.owner


def serialize_review(review):
    replies = [
        {
            'id': reply.id,
            'content': reply.content,
            'owner_name': reply.owner.get_username() if reply.owner_id else 'owner',
            'created_at': reply.created_at.isoformat(),
            'updated_at': reply.updated_at.isoformat(),
        }
        for reply in review.replies.all()
    ]
    return {
        'id': review.id,
        'place_id': review.place_id,
        'place_name': review.place_name,
        'author_name': review.author_name,
        'rating': review.rating,
        'content': review.content,
        'created_at': review.created_at.isoformat(),
        'replies': replies,
    }


def build_openapi_schema():
    return {
        'openapi': '3.0.3',
        'info': {
            'title': '서울 장소 지도 Review API',
            'version': '1.0.0',
            'description': '장소 리뷰 작성, 조회, 점주 답글 API입니다.',
        },
        'servers': [{'url': '/'}],
        'components': {
            'securitySchemes': {
                'OAuthClientCredentials': {
                    'type': 'oauth2',
                    'flows': {
                        'clientCredentials': {
                            'tokenUrl': '/oauth/token/',
                            'scopes': {
                                'owner:reviews': '점주 가게 리뷰 조회와 답글 관리',
                            },
                        },
                    },
                },
                'OwnerSession': {
                    'type': 'apiKey',
                    'in': 'cookie',
                    'name': 'sessionid',
                    'description': 'OwnerProfile이 연결된 점주 계정 로그인 세션입니다.',
                },
            },
            'schemas': {
                'Review': {
                    'type': 'object',
                    'properties': {
                        'id': {'type': 'integer'},
                        'place_id': {'type': 'string'},
                        'place_name': {'type': 'string'},
                        'author_name': {'type': 'string'},
                        'rating': {'type': 'integer', 'minimum': 1, 'maximum': 5},
                        'content': {'type': 'string'},
                        'created_at': {'type': 'string', 'format': 'date-time'},
                        'replies': {
                            'type': 'array',
                            'items': {
                                'type': 'object',
                                'properties': {
                                    'id': {'type': 'integer'},
                                    'content': {'type': 'string'},
                                    'owner_name': {'type': 'string'},
                                    'created_at': {'type': 'string', 'format': 'date-time'},
                                    'updated_at': {'type': 'string', 'format': 'date-time'},
                                },
                            },
                        },
                    },
                },
                'ReviewCreate': {
                    'type': 'object',
                    'required': ['place_id', 'place_name', 'author_name', 'rating', 'content', 'delete_password'],
                    'properties': {
                        'place_id': {'type': 'string'},
                        'place_name': {'type': 'string'},
                        'author_name': {'type': 'string', 'maxLength': 80},
                        'rating': {'type': 'integer', 'minimum': 1, 'maximum': 5},
                        'content': {'type': 'string', 'maxLength': 2000},
                        'delete_password': {'type': 'string', 'minLength': 4},
                    },
                },
                'ReviewDelete': {
                    'type': 'object',
                    'required': ['delete_password'],
                    'properties': {
                        'delete_password': {'type': 'string'},
                    },
                },
                'ReplyCreate': {
                    'type': 'object',
                    'required': ['content'],
                    'properties': {
                        'content': {'type': 'string', 'maxLength': 2000},
                    },
                },
                'OAuthTokenRequest': {
                    'type': 'object',
                    'required': ['grant_type', 'client_id', 'client_secret'],
                    'properties': {
                        'grant_type': {'type': 'string', 'enum': ['client_credentials']},
                        'client_id': {'type': 'string'},
                        'client_secret': {'type': 'string'},
                    },
                },
                'OAuthTokenResponse': {
                    'type': 'object',
                    'properties': {
                        'access_token': {'type': 'string'},
                        'token_type': {'type': 'string', 'example': 'Bearer'},
                        'expires_in': {'type': 'integer'},
                        'scope': {'type': 'string'},
                        'place_id': {'type': 'string'},
                        'place_name': {'type': 'string'},
                    },
                },
            },
        },
        'paths': {
            '/oauth/token/': {
                'post': {
                    'summary': 'OAuth access token 발급',
                    'description': '점주 Client ID와 Client Secret으로 client_credentials 토큰을 발급합니다.',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/OAuthTokenRequest'},
                            },
                            'application/x-www-form-urlencoded': {
                                'schema': {'$ref': '#/components/schemas/OAuthTokenRequest'},
                            },
                        },
                    },
                    'responses': {
                        '200': {
                            'description': '발급된 bearer token',
                            'content': {'application/json': {'schema': {'$ref': '#/components/schemas/OAuthTokenResponse'}}},
                        },
                        '400': {'description': '지원하지 않는 grant_type 또는 잘못된 요청'},
                        '401': {'description': 'client_id 또는 client_secret 불일치'},
                    },
                },
            },
            '/api/reviews/': {
                'get': {
                    'summary': '장소 리뷰 목록 조회',
                    'description': 'place_id 쿼리로 공개 조회하거나, bearer token만 보내 점주 가게 리뷰를 조회합니다.',
                    'security': [{}, {'OAuthClientCredentials': ['owner:reviews']}],
                    'parameters': [{
                        'name': 'place_id',
                        'in': 'query',
                        'required': False,
                        'schema': {'type': 'string'},
                    }],
                    'responses': {
                        '200': {
                            'description': '리뷰 목록',
                            'content': {'application/json': {'schema': {'type': 'object'}}},
                        },
                    },
                },
                'post': {
                    'summary': '리뷰 작성',
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/ReviewCreate'},
                            },
                        },
                    },
                    'responses': {
                        '201': {
                            'description': '작성된 리뷰',
                            'content': {'application/json': {'schema': {'type': 'object'}}},
                        },
                    },
                },
            },
            '/api/reviews/{review_id}/': {
                'delete': {
                    'summary': '리뷰 삭제',
                    'parameters': [{
                        'name': 'review_id',
                        'in': 'path',
                        'required': True,
                        'schema': {'type': 'integer'},
                    }],
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/ReviewDelete'},
                            },
                        },
                    },
                    'responses': {
                        '200': {'description': '삭제 완료'},
                        '403': {'description': '삭제 비밀번호 불일치'},
                        '404': {'description': '리뷰 없음'},
                    },
                },
            },
            '/api/reviews/{review_id}/reply/': {
                'post': {
                    'summary': '점주 답글 작성',
                    'security': [{'OwnerSession': []}, {'OAuthClientCredentials': ['owner:reviews']}],
                    'parameters': [{
                        'name': 'review_id',
                        'in': 'path',
                        'required': True,
                        'schema': {'type': 'integer'},
                    }],
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/ReplyCreate'},
                            },
                        },
                    },
                    'responses': {
                        '200': {'description': '답글이 포함된 리뷰'},
                        '401': {'description': '점주 로그인 또는 해당 가게 bearer token 필요'},
                        '403': {'description': '이 점주 계정은 해당 가게에 답글을 달 수 없음'},
                    },
                },
            },
            '/api/reviews/{review_id}/reply/{reply_id}/': {
                'patch': {
                    'summary': '점주 답글 수정',
                    'security': [{'OwnerSession': []}, {'OAuthClientCredentials': ['owner:reviews']}],
                    'parameters': [
                        {
                            'name': 'review_id',
                            'in': 'path',
                            'required': True,
                            'schema': {'type': 'integer'},
                        },
                        {
                            'name': 'reply_id',
                            'in': 'path',
                            'required': True,
                            'schema': {'type': 'integer'},
                        },
                    ],
                    'requestBody': {
                        'required': True,
                        'content': {
                            'application/json': {
                                'schema': {'$ref': '#/components/schemas/ReplyCreate'},
                            },
                        },
                    },
                    'responses': {
                        '200': {'description': '수정된 답글이 포함된 리뷰'},
                        '400': {'description': '검증 실패'},
                        '401': {'description': '점주 로그인 또는 해당 가게 bearer token 필요'},
                        '403': {'description': '이 점주 계정은 해당 가게 답글을 수정할 수 없음'},
                        '404': {'description': '리뷰 또는 답글 없음'},
                    },
                },
                'delete': {
                    'summary': '점주 답글 삭제',
                    'security': [{'OwnerSession': []}, {'OAuthClientCredentials': ['owner:reviews']}],
                    'parameters': [
                        {
                            'name': 'review_id',
                            'in': 'path',
                            'required': True,
                            'schema': {'type': 'integer'},
                        },
                        {
                            'name': 'reply_id',
                            'in': 'path',
                            'required': True,
                            'schema': {'type': 'integer'},
                        },
                    ],
                    'responses': {
                        '200': {'description': '답글이 삭제된 리뷰'},
                        '401': {'description': '점주 로그인 또는 해당 가게 bearer token 필요'},
                        '403': {'description': '이 점주 계정은 해당 가게 답글을 삭제할 수 없음'},
                        '404': {'description': '리뷰 또는 답글 없음'},
                    },
                },
            },
            '/api/openapi.json': {
                'get': {
                    'summary': 'OpenAPI 문서',
                    'responses': {'200': {'description': 'OpenAPI 3.0 schema'}},
                },
            },
            '/api/docs/': {
                'get': {
                    'summary': 'Swagger UI 문서',
                    'responses': {'200': {'description': 'Swagger UI page'}},
                },
            },
        },
    }
