import socket
import logging
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)

@shared_task
def check_dns_resolution(domain=None):
    """
    Watchdog task to verify DNS resolution for local/DDNS domain.
    Attempts to resolve the configured domain (defaulting to settings.DDNS_DOMAIN or 'raspberrypi').
    Logs warnings or errors if resolution fails or returns unexpected results.
    """
    target_domain = domain or getattr(settings, 'DDNS_DOMAIN', 'raspberrypi')

    try:
        ip_addresses = socket.gethostbyname_ex(target_domain)[2]
        msg = f"DNS resolution check successful for '{target_domain}': IP(s) {', '.join(ip_addresses)}"
        logger.info(msg)
        return {
            'status': 'SUCCESS',
            'domain': target_domain,
            'ips': ip_addresses,
            'message': msg
        }
    except socket.gaierror as e:
        error_msg = f"DNS resolution failed for '{target_domain}': {e}"
        logger.error(error_msg)
        return {
            'status': 'FAILED',
            'domain': target_domain,
            'error': str(e),
            'message': error_msg
        }
    except Exception as e:
        error_msg = f"Unexpected error during DNS resolution check for '{target_domain}': {e}"
        logger.exception(error_msg)
        return {
            'status': 'ERROR',
            'domain': target_domain,
            'error': str(e),
            'message': error_msg
        }
