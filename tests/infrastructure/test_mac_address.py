import unittest

from src.infrastructure.network.mac_address import _extract_mac_address


class MacAddressResolverTests(unittest.TestCase):
    def test_extract_mac_address_from_ip_neigh_output(self) -> None:
        output = "10.0.0.25 dev eth0 lladdr aa:bb:cc:dd:ee:ff REACHABLE"

        self.assertEqual(_extract_mac_address(output), "aa:bb:cc:dd:ee:ff")

    def test_extract_mac_address_normalizes_windows_arp_output(self) -> None:
        output = "  10.0.0.25           AA-BB-CC-DD-EE-FF     dynamic"

        self.assertEqual(_extract_mac_address(output), "aa:bb:cc:dd:ee:ff")

    def test_extract_mac_address_returns_none_when_output_has_no_mac(self) -> None:
        self.assertIsNone(_extract_mac_address("no neighbor entry"))


if __name__ == "__main__":
    unittest.main()
