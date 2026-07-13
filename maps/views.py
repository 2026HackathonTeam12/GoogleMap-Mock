from django.http import JsonResponse


def index(request):
    return JsonResponse(
        {
            'service': 'GoogleMap-Mock',
            'message': 'Django project is running.',
        }
    )


def health(request):
    return JsonResponse({'status': 'ok'})

# Create your views here.
