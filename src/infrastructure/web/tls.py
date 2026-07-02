from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

CERTIFICATE_DAYS = 825


@dataclass(frozen=True)
class WebCertificateResult:
    cert_file: Path
    key_file: Path
    generated: bool
    hosts: tuple[str, ...]


def ensure_web_certificate(
    *,
    cert_file: Path,
    key_file: Path,
    mdns_name: str,
    extra_hosts: tuple[str, ...] = (),
) -> WebCertificateResult:
    hosts = _certificate_hosts(mdns_name, extra_hosts)
    if cert_file.exists() and key_file.exists():
        return WebCertificateResult(
            cert_file=cert_file,
            key_file=key_file,
            generated=False,
            hosts=hosts,
        )

    cert_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.parent.mkdir(parents=True, exist_ok=True)

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    common_name = f"{_normalize_mdns(mdns_name)}.local"
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COMMON_NAME, common_name),
        ]
    )
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=CERTIFICATE_DAYS))
        .add_extension(_subject_alt_name(hosts), critical=False)
        .sign(key, hashes.SHA256())
    )

    key_file.write_bytes(
        key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    cert_file.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    return WebCertificateResult(
        cert_file=cert_file,
        key_file=key_file,
        generated=True,
        hosts=hosts,
    )


def _certificate_hosts(mdns_name: str, extra_hosts: tuple[str, ...]) -> tuple[str, ...]:
    hosts = [
        "localhost",
        "127.0.0.1",
        f"{_normalize_mdns(mdns_name)}.local",
        *_local_addresses(),
        *extra_hosts,
    ]
    unique_hosts = []
    for host in hosts:
        if host and host not in unique_hosts:
            unique_hosts.append(host)
    return tuple(unique_hosts)


def _subject_alt_name(hosts: tuple[str, ...]) -> x509.SubjectAlternativeName:
    names: list[x509.GeneralName] = []
    for host in hosts:
        try:
            names.append(x509.IPAddress(ipaddress.ip_address(host)))
        except ValueError:
            names.append(x509.DNSName(host))
    return x509.SubjectAlternativeName(names)


def _local_addresses() -> tuple[str, ...]:
    addresses: list[str] = []
    try:
        hostname = socket.gethostname()
        for result in socket.getaddrinfo(hostname, None, socket.AF_INET):
            host = result[4][0]
            if isinstance(host, str) and not host.startswith("127."):
                addresses.append(host)
    except OSError:
        pass

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
            probe.connect(("8.8.8.8", 80))
            host = probe.getsockname()[0]
            if host and not host.startswith("127."):
                addresses.append(host)
    except OSError:
        pass

    unique_addresses = []
    for address in addresses:
        if address not in unique_addresses:
            unique_addresses.append(address)
    return tuple(unique_addresses)


def _normalize_mdns(name: str) -> str:
    normalized = name.strip().lower()
    if normalized.endswith(".local"):
        normalized = normalized[: -len(".local")]
    return normalized or "gesturetvremote"
