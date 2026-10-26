"""Verify updater HTTPS with a real local TLS server, without public-network tests."""
import ssl
import shutil
import subprocess
import tempfile
import threading
import unittest
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from bashdock import updates


class UpdateTLSTests(unittest.TestCase):
    def test_certificate_errors_have_actionable_words(self):
        error = ssl.SSLCertVerificationError(1, 'unable to get local issuer certificate')
        message = updates.update_error_message(urllib.error.URLError(error))
        self.assertIn('secure update connection', message)
        self.assertIn('Windows date/time', message)
        self.assertNotIn('_ssl.c', message)
        self.assertEqual('other error', updates.update_error_message(ValueError('other error')))

    def test_context_keeps_required_verification_and_no_global_patch(self):
        original = ssl.SSLContext
        context = updates.tls_context()
        self.assertTrue(context.check_hostname)
        self.assertEqual(ssl.CERT_REQUIRED, context.verify_mode)
        self.assertIs(original, ssl.SSLContext)
        import sys
        if sys.platform == 'win32':
            self.assertEqual('truststore._api', type(context).__module__)

    def test_https_accepts_trusted_certificate_but_rejects_untrusted_names_and_http_redirects(self):
        openssl = shutil.which('openssl')
        if openssl is None:
            self.skipTest('OpenSSL is required to generate an isolated TLS test certificate')
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cert, key = root / 'cert.pem', root / 'key.pem'
            subprocess.run([openssl, 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                            '-keyout', str(key), '-out', str(cert), '-days', '1',
                            '-subj', '/CN=localhost', '-addext', 'subjectAltName=DNS:localhost'],
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, check=True, timeout=30)

            class Handler(BaseHTTPRequestHandler):
                def do_GET(self):
                    if self.path == '/redirect':
                        self.send_response(302)
                        self.send_header('Location', 'http://localhost/never-follow')
                        self.end_headers()
                    else:
                        self.send_response(200)
                        self.end_headers()
                        self.wfile.write(b'verified TLS')

                def log_message(self, *args):
                    pass

            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            server_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            server_context.load_cert_chain(cert, key)
            server.socket = server_context.wrap_socket(server.socket, server_side=True)
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                with patch('urllib.request.getproxies', return_value={}):
                    # This certificate is private to the test, never a system trusted root.
                    with self.assertRaises(urllib.error.URLError):
                        updates.read_url(f'https://localhost:{port}/', 100)
                    trusted = updates.tls_context()
                    trusted.load_verify_locations(cafile=str(cert))
                    with patch.object(updates, 'tls_context', return_value=trusted):
                        self.assertEqual(b'verified TLS', updates.read_url(f'https://localhost:{port}/', 100))
                        with self.assertRaises(urllib.error.URLError):
                            updates.read_url(f'https://127.0.0.1:{port}/', 100)
                        with self.assertRaisesRegex(ValueError, 'insecure redirect'):
                            updates.read_url(f'https://localhost:{port}/redirect', 100)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
