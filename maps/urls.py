from django.urls import path

from . import views


app_name = 'maps'

urlpatterns = [
    path('', views.index, name='index'),
    path('health/', views.health, name='health'),
    path('owner/login/', views.owner_login, name='owner-login'),
    path('owner/logout/', views.owner_logout, name='owner-logout'),
    path('owner/signup/', views.owner_signup, name='owner-signup'),
    path('owner/account/', views.owner_account, name='owner-account'),
    path('oauth/token/', views.oauth_token, name='oauth-token'),
    path('api/reviews/', views.review_collection, name='review-collection'),
    path('api/reviews/<int:review_id>/', views.review_detail, name='review-detail'),
    path('api/reviews/<int:review_id>/reply/', views.review_reply, name='review-reply'),
    path('api/reviews/<int:review_id>/reply/<int:reply_id>/', views.review_reply_detail, name='review-reply-detail'),
    path('api/openapi.json', views.openapi_schema, name='openapi-schema'),
    path('api/docs/', views.swagger_docs, name='swagger-docs'),
]
