from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render


def index(request):
    return render(
        request,
        'maps/index.html',
        {
            'google_maps_api_key': settings.GOOGLE_MAPS_API_KEY,
        },
    )


def health(request):
    return JsonResponse({'status': 'ok'})
