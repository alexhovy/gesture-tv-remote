import unittest
from unittest.mock import patch

from src.infrastructure.network.mac_address import (
    LocalNetworkMacAddressResolver,
    _extract_mac_address,
)
from tests.fakes.fake_logger import FakeLogger


class MacAddressResolverTests(unittest.TestCase):
    def test_extract_mac_address_from_ip_neigh_output(self) -> None:
        output = "10.0.0.25 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE"

        self.assertEqual(_extract_mac_address(output), "aa:bb:cc:dd:ee:ff")

    def test_extract_mac_address_normalizes_windows_arp_output(self) -> None:
        output = "  10.0.0.25           AA-BB-CC-DD-EE-FF     dynamic"

        self.assertEqual(_extract_mac_address(output), "aa:bb:cc:dd:ee:ff")

    def test_extract_mac_address_returns_none_when_output_has_no_mac(self) -> None:
        self.assertIsNone(_extract_mac_address("no neighbor entry"))

    def test_resolve_broadcast_address_for_same_ipv4_subnet(self) -> None:
        resolver = LocalNetworkMacAddressResolver(FakeLogger())

        with (
            patch("socket.gethostbyname", return_value="192.168.8.7"),
            patch(
                "src.infrastructure.network.mac_address._local_ipv4_for",
                return_value="192.168.8.20",
            ),
        ):
            address = resolver.resolve_broadcast_address("tv.local")

        self.assertEqual(address, "192.168.8.255")

    def test_resolve_broadcast_address_returns_none_for_different_ipv4_subnet(
        self,
    ) -> None:
        resolver = LocalNetworkMacAddressResolver(FakeLogger())

        with (
            patch("socket.gethostbyname", return_value="192.168.8.7"),
            patch(
                "src.infrastructure.network.mac_address._local_ipv4_for",
                return_value="192.168.68.20",
            ),
        ):
            address = resolver.resolve_broadcast_address("tv.local")

        self.assertIsNone(address)


if __name__ == "__main__":
    unittest.main()
