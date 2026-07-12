import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from .models import EdgeDevice
from .device_registry import get_device_types, get_handler_class, DEVICE_TYPE_REGISTRY
from .tasks import delayed_device_action

logger = logging.getLogger('devices')


def _require_auth(request):
    if not request.user.is_authenticated:
        return JsonResponse({'detail': 'Not authenticated'}, status=401)
    if not request.user.is_staff:
        return JsonResponse({'detail': 'Admin access required'}, status=403)
    return None


@require_GET
def device_types_view(request):
    auth_err = _require_auth(request)
    if auth_err:
        return auth_err
    return JsonResponse({'types': get_device_types()})


@require_http_methods(["GET", "POST"])
def device_list_view(request):
    auth_err = _require_auth(request)
    if auth_err:
        return auth_err

    if request.method == 'GET':
        devices = EdgeDevice.objects.all()
        return JsonResponse({'devices': [d.to_api_dict() for d in devices]})

    # POST - Create new device
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    name = data.get('name', '').strip()
    device_type = data.get('device_type', '').strip()
    ip_address = data.get('ip_address', '').strip()
    config = data.get('config', {})

    if not all([name, device_type, ip_address]):
        return JsonResponse({'detail': 'name, device_type, and ip_address are required'}, status=400)

    if device_type not in DEVICE_TYPE_REGISTRY:
        return JsonResponse({'detail': f'Unknown device type: {device_type}'}, status=400)

    device = EdgeDevice(name=name, device_type=device_type, ip_address=ip_address)
    device.set_config(config)
    device.save()

    logger.info(f"Device created: {device.name} ({device.device_type}) at {device.ip_address}")
    return JsonResponse({'device': device.to_api_dict()}, status=201)


@require_http_methods(["PATCH", "DELETE"])
def device_detail_view(request, device_id):
    auth_err = _require_auth(request)
    if auth_err:
        return auth_err

    try:
        device = EdgeDevice.objects.get(id=device_id)
    except EdgeDevice.DoesNotExist:
        return JsonResponse({'detail': 'Device not found'}, status=404)

    if request.method == 'DELETE':
        device_name = device.name
        device.delete()
        logger.info(f"Device deleted: {device_name}")
        return JsonResponse({'success': True})

    # PATCH - Update device
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    if 'name' in data:
        device.name = data['name'].strip()
    if 'ip_address' in data:
        device.ip_address = data['ip_address'].strip()
    if 'config' in data:
        # Merge: only update provided config fields, keep existing ones
        existing_config = device.get_decrypted_config()
        for key, value in data['config'].items():
            existing_config[key] = value
        device.set_config(existing_config)

    device.save()
    logger.info(f"Device updated: {device.name}")
    return JsonResponse({'device': device.to_api_dict()})


@require_POST
def device_action_view(request, device_id):
    """Execute an action (on/off/status) on a device."""
    auth_err = _require_auth(request)
    if auth_err:
        return auth_err

    try:
        device = EdgeDevice.objects.get(id=device_id)
    except EdgeDevice.DoesNotExist:
        return JsonResponse({'detail': 'Device not found'}, status=404)

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'detail': 'Invalid JSON'}, status=400)

    action = data.get('action', '').strip()
    entry = DEVICE_TYPE_REGISTRY.get(device.device_type, {})
    capabilities = entry.get('capabilities', [])

    if action not in capabilities:
        return JsonResponse({'detail': f'Action "{action}" not supported for this device'}, status=400)

    try:
        HandlerClass = get_handler_class(device.device_type)
        handler = HandlerClass(device.ip_address, device.get_decrypted_config())

        if action == 'on':
            handler.turn_on()
            device.is_online = True
            device.save(update_fields=['is_online', 'updated_at'])
            return JsonResponse({'success': True, 'action': 'on'})
        elif action == 'off':
            handler.turn_off()
            device.is_online = False
            device.save(update_fields=['is_online', 'updated_at'])
            return JsonResponse({'success': True, 'action': 'off'})
        elif action == 'status':
            status = handler.get_status()
            device.is_online = status.get('online', False)
            device.save(update_fields=['is_online', 'updated_at'])
            return JsonResponse({'success': True, 'action': 'status', 'status': status})

    except Exception as e:
        logger.error(f"Action '{action}' failed on device {device.name}: {e}")
        return JsonResponse({'detail': f'Action failed: {str(e)}'}, status=500)


@csrf_exempt
@require_POST
def printer_shutdown_webhook(request):
    """
    Webhook endpoint for Klipper. NO authentication required.
    Responds immediately with 200, then schedules a delayed shutdown.
    """
    # Find the first Tapo device (the printer plug)
    # You could also accept a device_id or name in the request body
    device = EdgeDevice.objects.filter(device_type__startswith='tapo').first()

    if not device:
        logger.warning("Printer shutdown webhook called but no Tapo device configured")
        return JsonResponse({'status': 'no_device_configured'}, status=200)

    # Parse optional delay from request body
    delay = 120  # default 2 minutes
    try:
        if request.body:
            data = json.loads(request.body)
            delay = int(data.get('delay', 120))
    except (json.JSONDecodeError, ValueError):
        pass  # Use default

    # Schedule the delayed shutdown via Celery (non-blocking)
    delayed_device_action.delay(device.id, action='off', delay_seconds=delay)

    logger.info(f"Printer shutdown webhook: scheduled '{device.name}' OFF in {delay}s")
    return JsonResponse({
        'status': 'shutdown_scheduled',
        'device': device.name,
        'delay_seconds': delay
    })
