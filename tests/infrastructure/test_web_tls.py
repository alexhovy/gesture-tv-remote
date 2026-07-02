import tempfile
import unittest
from pathlib import Path

from cryptography import x509

from src.infrastructure.web.tls import ensure_web_certificate


class WebTlsTests(unittest.TestCase):
    def test_ensure_web_certificate_creates_cert_and_key(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cert_file = Path(temp_dir) / "server.crt"
            key_file = Path(temp_dir) / "server.key"

            result = ensure_web_certificate(
                cert_file=cert_file,
                key_file=key_file,
                mdns_name="GestureTvRemote",
            )

            self.assertTrue(result.generated)
            self.assertTrue(cert_file.exists())
            self.assertTrue(key_file.exists())
            certificate = x509.load_pem_x509_certificate(cert_file.read_bytes())
            san = certificate.extensions.get_extension_for_class(
                x509.SubjectAlternativeName
            ).value
            self.assertIn(
                "gesturetvremote.local",
                san.get_values_for_type(x509.DNSName),
            )
            self.assertIn("localhost", san.get_values_for_type(x509.DNSName))

    def test_ensure_web_certificate_keeps_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cert_file = Path(temp_dir) / "server.crt"
            key_file = Path(temp_dir) / "server.key"
            first = ensure_web_certificate(
                cert_file=cert_file,
                key_file=key_file,
                mdns_name="gesturetvremote",
            )

            second = ensure_web_certificate(
                cert_file=cert_file,
                key_file=key_file,
                mdns_name="gesturetvremote",
            )

            self.assertTrue(first.generated)
            self.assertFalse(second.generated)


if __name__ == "__main__":
    unittest.main()
