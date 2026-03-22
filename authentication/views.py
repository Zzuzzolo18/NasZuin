import json
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from django_otp import devices_for_user
from django_otp.plugins.otp_totp.models import TOTPDevice

@ensure_csrf_cookie
@require_GET
def csrf_token_view(request):
    return JsonResponse({'detail': 'CSRF cookie set'})

@require_POST
def login_view(request):
    try:
        data = json.loads(request.body)
        username = data.get('username')
        password = data.get('password')
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    user = authenticate(request, username=username, password=password)

    if user is not None:
        # Check for 2FA devices
        devices = list(devices_for_user(user, confirmed=True))
        if devices:
            # 2FA required
            # Store user_id in session to verify later
            request.session['2fa_user_id'] = user.id
            return JsonResponse({'require_2fa': True, 'user_id': user.id})
        else:
            # Login immediately if no 2FA
            login(request, user)
            return JsonResponse({'success': True, 'is_staff': user.is_staff})
    else:
        return JsonResponse({'detail': 'Invalid credentials'}, status=401)

@require_POST
def verify_2fa_view(request):
    try:
        data = json.loads(request.body)
        token = data.get('token')
        user_id = request.session.get('2fa_user_id')
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    if not user_id:
        return JsonResponse({'detail': 'Session expired or invalid flow'}, status=400)

    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'detail': 'User not found'}, status=404)

    # Verify token
    # We iterate over confirmed devices and check if any match
    devices = devices_for_user(user, confirmed=True)
    verified = False
    for device in devices:
        if device.verify_token(token):
            verified = True
            break
    
    if verified:
        user.backend = 'django.contrib.auth.backends.ModelBackend'
        login(request, user)
        # Mark the device as verified in the session for django-otp middleware
        from django_otp import login as otp_login
        # We need to find the specific device that verified
        # Use the device object from the loop
        otp_login(request, device)
        
        del request.session['2fa_user_id']
        return JsonResponse({'success': True, 'is_staff': user.is_staff})
    else:
        return JsonResponse({'detail': 'Invalid OTP token'}, status=401)

@require_GET
def check_auth_view(request):
    if request.user.is_authenticated:
        return JsonResponse({'is_authenticated': True, 'is_staff': request.user.is_staff, 'username': request.user.username})
    else:
        return JsonResponse({'is_authenticated': False}, status=401)

@require_POST
def logout_view(request):
    logout(request)
    return JsonResponse({'success': True})

# --- 2FA Management Endpoints ---

@require_GET
def status_2fa_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Not authenticated'}, status=401)
    
    # Check if user has confirmed 2FA devices
    has_2fa = TOTPDevice.objects.filter(user=request.user, confirmed=True).exists()
    return JsonResponse({'enabled': has_2fa})

@require_POST
def setup_2fa_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Not authenticated'}, status=401)
    
    # Create a new unconfirmed device
    # Delete existing unconfirmed devices to keep it clean
    TOTPDevice.objects.filter(user=request.user, confirmed=False).delete()
    
    device = TOTPDevice.objects.create(user=request.user, confirmed=False)
    
    # Generate QR Code
    otpauth_url = device.config_url
    
    from .utils import get_qr_code_image
    qr_code_base64 = get_qr_code_image(otpauth_url)
    
    return JsonResponse({
        'otpauth_url': otpauth_url,
        'qr_code_base64': qr_code_base64,
        'device_id': device.id # Optional, might not need if we just verify against user's unconfirmed device
    })

@require_POST
def confirm_2fa_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Not authenticated'}, status=401)
        
    try:
        data = json.loads(request.body)
        token = data.get('token')
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)
    
    # Find the unconfirmed device
    device = TOTPDevice.objects.filter(user=request.user, confirmed=False).first()
    
    if not device:
        return JsonResponse({'detail': 'No setup in progress'}, status=400)
        
    if device.verify_token(token):
        device.confirmed = True
        device.save()
        
        # Also ensure django-otp knows we are verified for this session
        from django_otp import login as otp_login
        otp_login(request, device)
        
        return JsonResponse({'success': True})
    else:
        return JsonResponse({'detail': 'Invalid token'}, status=400)

@require_POST
def disable_2fa_view(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Not authenticated'}, status=401)
    
    # Remove all TOTP devices
    # In a real app, you might want to ask for a password or OTP before disabling this.
    TOTPDevice.objects.filter(user=request.user).delete()
    
    return JsonResponse({'success': True})
