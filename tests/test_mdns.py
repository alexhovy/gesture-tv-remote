import sys
import types
import unittest
from unittest.mock import patch

from src.infrastructure.network.mdns import MdnsPublisher


class MdnsPublisherTests(unittest.TestCase):
    def test_start_registers_http_service_and_stop_unregisters_it(self) -> None:
        registered_services = []
        unregistered_services = []

        class FakeServiceInfo:
            def __init__(self, *args: object, **kwargs: object) -> None:
                self.args = args
                self.kwargs = kwargs

        class FakeZeroconf:
            def register_service(self, service_info: object) -> None:
                registered_services.append(service_info)

            def unregister_service(self, service_info: object) -> None:
                unregistered_services.append(service_info)

            def close(self) -> None:
                pass

        fake_zeroconf = types.ModuleType("zeroconf")
        fake_zeroconf.ServiceInfo = FakeServiceInfo
        fake_zeroconf.Zeroconf = FakeZeroconf
        publisher = MdnsPublisher("GestureTvRemote.local", 80)

        with (
            patch.dict(sys.modules, {"zeroconf": fake_zeroconf}),
            patch(
                "src.infrastructure.network.mdns._local_ipv4_address",
                return_value="10.0.0.2",
            ),
        ):
            publisher.start()
            publisher.stop()

        self.assertEqual(publisher.url, "http://gesturetvremote.local")
        self.assertEqual(len(registered_services), 1)
        self.assertEqual(unregistered_services, registered_services)
        service_info = registered_services[0]
        self.assertEqual(service_info.args[0], "_http._tcp.local.")
        self.assertEqual(service_info.args[1], "gesturetvremote._http._tcp.local.")
        self.assertEqual(service_info.kwargs["port"], 80)
        self.assertEqual(service_info.kwargs["server"], "gesturetvremote.local.")

    def test_url_includes_non_default_port(self) -> None:
        publisher = MdnsPublisher("GestureTvRemote", 8765)

        self.assertEqual(publisher.url, "http://gesturetvremote.local:8765")

    def test_rejects_empty_normalized_name(self) -> None:
        with self.assertRaisesRegex(ValueError, "mDNS name"):
            MdnsPublisher("...", 8765)


if __name__ == "__main__":
    unittest.main()
