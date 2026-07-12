import logging
import time
from celery import shared_task

logger = logging.getLogger('devices')


@shared_task(bind=True)
def delayed_device_action(self, device_id, action='off', delay_seconds=120):
    """
    Background task: waits delay_seconds then performs action on device.
    Used by the Klipper webhook for safe delayed shutdown.
    """
    logger.info(f"Task started: waiting {delay_seconds}s before '{action}' on device {device_id}")
    time.sleep(delay_seconds)

    from .models import EdgeDevice
    from .device_registry import get_handler_class

    try:
        device = EdgeDevice.objects.get(id=device_id)
        HandlerClass = get_handler_class(device.device_type)
        handler = HandlerClass(device.ip_address, device.get_decrypted_config())

        if action == 'off':
            handler.turn_off()
        elif action == 'on':
            handler.turn_on()
        else:
            logger.error(f"Unknown action '{action}' for device {device_id}")
            return {'success': False, 'error': f'Unknown action: {action}'}

        logger.info(f"Device {device.name} ({device.ip_address}): '{action}' executed successfully")
        return {'success': True, 'device': device.name, 'action': action}

    except EdgeDevice.DoesNotExist:
        logger.error(f"Device {device_id} not found")
        return {'success': False, 'error': 'Device not found'}
    except Exception as e:
        logger.error(f"Failed to execute '{action}' on device {device_id}: {e}")
        return {'success': False, 'error': str(e)}
