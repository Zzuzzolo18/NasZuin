import socket
from unittest.mock import patch
from django.test import TestCase, override_settings
from monitor.tasks import check_dns_resolution

class DNSWatchdogTaskTests(TestCase):

    @patch('socket.gethostbyname_ex')
    @override_settings(DDNS_DOMAIN='raspberrypi')
    def test_check_dns_resolution_success(self, mock_gethostbyname):
        mock_gethostbyname.return_value = ('raspberrypi', [], ['192.168.1.50'])

        result = check_dns_resolution()

        self.assertEqual(result['status'], 'SUCCESS')
        self.assertEqual(result['domain'], 'raspberrypi')
        self.assertEqual(result['ips'], ['192.168.1.50'])
        mock_gethostbyname.assert_called_once_with('raspberrypi')

    @patch('socket.gethostbyname_ex')
    def test_check_dns_resolution_failure(self, mock_gethostbyname):
        mock_gethostbyname.side_effect = socket.gaierror(-2, 'Name or service not known')

        result = check_dns_resolution(domain='nonexistent.local')

        self.assertEqual(result['status'], 'FAILED')
        self.assertEqual(result['domain'], 'nonexistent.local')
        self.assertIn('Name or service not known', result['error'])
        mock_gethostbyname.assert_called_once_with('nonexistent.local')

    @patch('socket.gethostbyname_ex')
    def test_check_dns_resolution_generic_exception(self, mock_gethostbyname):
        mock_gethostbyname.side_effect = RuntimeError('Unexpected socket failure')

        result = check_dns_resolution(domain='raspberrypi')

        self.assertEqual(result['status'], 'ERROR')
        self.assertEqual(result['domain'], 'raspberrypi')
        self.assertIn('Unexpected socket failure', result['error'])
