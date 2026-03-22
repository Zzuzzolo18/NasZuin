from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='api_login'),
    path('verify-2fa/', views.verify_2fa_view, name='api_verify_2fa'),
    path('check/', views.check_auth_view, name='api_check_auth'),
    path('logout/', views.logout_view, name='api_logout'),
    path('csrf/', views.csrf_token_view, name='api_csrf'),
    
    # 2FA Management
    path('2fa/status/', views.status_2fa_view, name='api_2fa_status'),
    path('2fa/setup/', views.setup_2fa_view, name='api_2fa_setup'),
    path('2fa/confirm/', views.confirm_2fa_view, name='api_2fa_confirm'),
    path('2fa/disable/', views.disable_2fa_view, name='api_2fa_disable'),
]
