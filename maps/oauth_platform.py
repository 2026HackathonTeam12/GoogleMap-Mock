import secrets

from django.contrib.auth import authenticate, login
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from urllib.parse import urlencode, urlparse

from .models import OwnerAccessToken, OwnerAuthorizationCode, OwnerProfile, PlatformOAuthClient


def resolve_oauth_client(client_id):
    platform = PlatformOAuthClient.objects.filter(client_id=client_id, is_active=True).first()
    if platform:
        return 'platform', platform, None

    try:
        return 'owner', OwnerProfile.objects.get(client_id=client_id), None
    except OwnerProfile.DoesNotExist:
        return None, None, 'client_id is invalid'


def validate_authorize_request(request, params):
    if params['response_type'] != 'code':
        return None, None, 'response_type must be code'
    if not params['client_id']:
        return None, None, 'client_id is required'
    if not params['redirect_uri']:
        return None, None, 'redirect_uri is required'

    client_kind, client, error = resolve_oauth_client(params['client_id'])
    if error:
        return None, None, error

    if client_kind == 'platform':
        if not client.allows_redirect_uri(params['redirect_uri']):
            return None, None, 'redirect_uri is not allowed'
        return 'platform', client, None

    if not is_allowed_owner_redirect_uri(request, params['redirect_uri']):
        return None, None, 'redirect_uri is not allowed'
    return 'owner', client, None


def is_allowed_owner_redirect_uri(request, redirect_uri):
    if redirect_uri.startswith('/'):
        return True

    parsed = urlparse(redirect_uri)
    allowed_hosts = {request.get_host(), 'testserver'}
    if parsed.hostname in {'localhost', '127.0.0.1'}:
        allowed_hosts.add(parsed.netloc)

    return url_has_allowed_host_and_scheme(
        redirect_uri,
        allowed_hosts=allowed_hosts,
        require_https=False,
    )


def authorize_context(params, client_kind, client, errors, values, owner_profile):
    return {
        'params': params,
        'errors': errors,
        'values': values,
        'profile': owner_profile if client_kind == 'owner' else None,
        'platform_client': client if client_kind == 'platform' else None,
        'owner_profile': owner_profile,
    }


def handle_oauth_authorize(request, params, get_user_owner_profile_fn):
    client_kind, client, error = validate_authorize_request(request, params)
    if error:
        return render(
            request,
            'maps/oauth_authorize.html',
            authorize_context(params, None, None, {'oauth': error}, {}, None),
            status=400,
        )

    current_profile = get_user_owner_profile_fn(request.user)

    if client_kind == 'platform':
        return handle_platform_authorize(request, params, client, current_profile, get_user_owner_profile_fn)

    return handle_owner_client_authorize(
        request,
        params,
        client,
        current_profile,
        get_user_owner_profile_fn,
    )


def handle_platform_authorize(request, params, platform_client, current_profile, get_user_owner_profile_fn):
    if request.method == 'GET' and current_profile:
        return redirect_with_authorization_code(current_profile, params, platform_client)

    if request.method == 'GET':
        return render(
            request,
            'maps/oauth_authorize.html',
            authorize_context(params, 'platform', platform_client, {}, {}, current_profile),
        )

    if request.method != 'POST':
        return HttpResponseNotAllowed(['GET', 'POST'])

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    user = authenticate(request, username=username, password=password)
    owner_profile = get_user_owner_profile_fn(user) if user else None
    if not owner_profile:
        return render(
            request,
            'maps/oauth_authorize.html',
            authorize_context(
                params,
                'platform',
                platform_client,
                {'account': 'MockMap 점주 계정으로 로그인해주세요. 계정이 없다면 먼저 가입해주세요.'},
                {'username': username},
                None,
            ),
            status=403,
        )

    login(request, user)
    return redirect_with_authorization_code(owner_profile, params, platform_client)


def handle_owner_client_authorize(
    request,
    params,
    owner_profile,
    current_profile,
    get_user_owner_profile_fn,
):
    effective_profile = owner_profile or current_profile

    if request.method == 'GET' and not effective_profile:
        return render(
            request,
            'maps/oauth_authorize.html',
            authorize_context(params, 'owner', owner_profile, {}, {}, None),
        )

    if request.method == 'GET' and current_profile and current_profile.pk == effective_profile.pk:
        return redirect_with_authorization_code(effective_profile, params, None)

    if request.method == 'GET':
        return render(
            request,
            'maps/oauth_authorize.html',
            authorize_context(params, 'owner', owner_profile, {}, {}, effective_profile),
        )

    if request.method != 'POST':
        return HttpResponseNotAllowed(['GET', 'POST'])

    username = request.POST.get('username', '').strip()
    password = request.POST.get('password', '')
    user = authenticate(request, username=username, password=password)
    logged_in_profile = get_user_owner_profile_fn(user) if user else None
    if not logged_in_profile or (owner_profile and logged_in_profile.pk != owner_profile.pk):
        return render(
            request,
            'maps/oauth_authorize.html',
            authorize_context(
                params,
                'owner',
                owner_profile,
                {'account': '이 OAuth client의 점주 계정으로 로그인해주세요.'},
                {'username': username},
                effective_profile,
            ),
            status=403,
        )

    login(request, user)
    return redirect_with_authorization_code(logged_in_profile, params, None)


def redirect_with_authorization_code(owner_profile, params, platform_client=None):
    OwnerAuthorizationCode.objects.filter(owner=owner_profile, expires_at__lte=timezone.now()).delete()
    code = OwnerAuthorizationCode.objects.create(
        owner=owner_profile,
        platform_client=platform_client,
        redirect_uri=params['redirect_uri'],
        state=params['state'],
        scope=normalize_scope(params.get('scope')),
    )
    query_parts = [('code', code.code)]
    if params['state']:
        query_parts.append(('state', params['state']))
    query = urlencode(query_parts)
    separator = '&' if '?' in params['redirect_uri'] else '?'
    return redirect(f'{params["redirect_uri"]}{separator}{query}')


def authenticate_platform_client(request, payload, platform_client, get_client_credentials):
    client_id, client_secret = get_client_credentials(request, payload)
    if not client_id:
        client_id = str(payload.get('client_id', '')).strip()
    if client_id != platform_client.client_id:
        return JsonResponse({'error': 'invalid_client'}, status=401)
    if not client_secret:
        return JsonResponse({'error': 'invalid_client'}, status=401)
    if not secrets.compare_digest(client_secret, platform_client.client_secret):
        return JsonResponse({'error': 'invalid_client'}, status=401)
    return None


def authenticate_owner_client(request, payload, owner_profile, get_client_credentials):
    client_id, client_secret = get_client_credentials(request, payload)
    if not client_id:
        client_id = str(payload.get('client_id', '')).strip()
    if client_id != owner_profile.client_id:
        return JsonResponse({'error': 'invalid_client'}, status=401)
    if not client_secret:
        return JsonResponse({'error': 'invalid_client'}, status=401)
    if not secrets.compare_digest(client_secret, owner_profile.client_secret):
        return JsonResponse({'error': 'invalid_client'}, status=401)
    return None


def issue_token_from_authorization_code(owner_profile, payload):
    code_value = str(payload.get('code', '')).strip()
    redirect_uri = str(payload.get('redirect_uri', '')).strip()
    state = str(payload.get('state', '')).strip()
    if not code_value or not redirect_uri:
        return JsonResponse({'error': 'code and redirect_uri are required'}, status=400)

    try:
        code = OwnerAuthorizationCode.objects.get(code=code_value, owner=owner_profile)
    except OwnerAuthorizationCode.DoesNotExist:
        return JsonResponse({'error': 'invalid_grant'}, status=400)

    if code.is_used or code.is_expired or code.redirect_uri != redirect_uri:
        return JsonResponse({'error': 'invalid_grant'}, status=400)

    if code.state and code.state != state:
        return JsonResponse({'error': 'invalid_grant'}, status=400)

    code.used_at = timezone.now()
    code.save(update_fields=['used_at'])
    token = OwnerAccessToken.objects.create(owner=owner_profile, scope=code.scope)
    response_client_id = (
        code.platform_client.client_id if code.platform_client else owner_profile.client_id
    )
    return JsonResponse(build_token_response(token, response_client_id))


def issue_platform_token_from_authorization_code(platform_client, payload):
    code_value = str(payload.get('code', '')).strip()
    redirect_uri = str(payload.get('redirect_uri', '')).strip()
    state = str(payload.get('state', '')).strip()
    if not code_value or not redirect_uri:
        return JsonResponse({'error': 'code and redirect_uri are required'}, status=400)

    try:
        code = OwnerAuthorizationCode.objects.get(code=code_value)
    except OwnerAuthorizationCode.DoesNotExist:
        return JsonResponse({'error': 'invalid_grant'}, status=400)

    if code.platform_client_id != platform_client.id:
        return JsonResponse({'error': 'invalid_grant'}, status=400)

    if code.is_used or code.is_expired or code.redirect_uri != redirect_uri:
        return JsonResponse({'error': 'invalid_grant'}, status=400)

    if code.state and code.state != state:
        return JsonResponse({'error': 'invalid_grant'}, status=400)

    code.used_at = timezone.now()
    code.save(update_fields=['used_at'])
    token = OwnerAccessToken.objects.create(owner=code.owner, scope=code.scope)
    return JsonResponse(build_token_response(token, platform_client.client_id))


def issue_token_from_refresh_token(owner_profile, payload):
    refresh_token = str(payload.get('refresh_token', '')).strip()
    if not refresh_token:
        return JsonResponse({'error': 'refresh_token is required'}, status=400)

    try:
        token = OwnerAccessToken.objects.get(owner=owner_profile, refresh_token=refresh_token)
    except OwnerAccessToken.DoesNotExist:
        return JsonResponse({'error': 'invalid_grant'}, status=400)

    if token.is_revoked or token.is_refresh_expired:
        return JsonResponse({'error': 'invalid_grant'}, status=400)

    token.revoked_at = timezone.now()
    token.save(update_fields=['revoked_at'])
    next_token = OwnerAccessToken.objects.create(owner=owner_profile, scope=token.scope)
    return JsonResponse(build_token_response(next_token, owner_profile.client_id))


def issue_platform_token_from_refresh(platform_client, payload):
    refresh_token = str(payload.get('refresh_token', '')).strip()
    if not refresh_token:
        return JsonResponse({'error': 'refresh_token is required'}, status=400)

    try:
        token = OwnerAccessToken.objects.get(refresh_token=refresh_token)
    except OwnerAccessToken.DoesNotExist:
        return JsonResponse({'error': 'invalid_grant'}, status=400)

    if token.is_revoked or token.is_refresh_expired:
        return JsonResponse({'error': 'invalid_grant'}, status=400)

    token.revoked_at = timezone.now()
    token.save(update_fields=['revoked_at'])
    next_token = OwnerAccessToken.objects.create(owner=token.owner, scope=token.scope)
    return JsonResponse(build_token_response(next_token, platform_client.client_id))


def build_token_response(token, client_id):
    expires_in = max(0, int((token.expires_at - timezone.now()).total_seconds()))
    refresh_expires_in = max(0, int((token.refresh_expires_at - timezone.now()).total_seconds()))
    return {
        'access_token': token.token,
        'refresh_token': token.refresh_token,
        'token_type': 'Bearer',
        'expires_in': expires_in,
        'refresh_expires_in': refresh_expires_in,
        'scope': token.scope,
        'client_id': client_id,
        'place_id': token.owner.place_id,
        'place_name': token.owner.place_name,
    }


def normalize_scope(scope_value):
    scope = str(scope_value or 'owner:reviews').strip()
    return scope or 'owner:reviews'
