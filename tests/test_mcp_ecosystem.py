from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcp"))

from mqtt_client import MqttBridge
from ota_device import DeviceRegistry
from ota_firmware import FirmwareRepo


class MqttEcosystemTests(unittest.TestCase):
    def test_qos_policy_and_will_configuration_guard(self) -> None:
        bridge = MqttBridge()
        self.assertTrue(bridge.validate_qos_policy("availability", 1, True)["ok"])
        self.assertFalse(bridge.validate_qos_policy("command", 1, True)["ok"])
        incomplete_will = bridge.connect("localhost", will_topic="device/status")
        self.assertFalse(incomplete_will["ok"])
        self.assertIn("will_topic", incomplete_will["error"])


class OtaEcosystemTests(unittest.TestCase):
    def test_signed_firmware_detects_tampering(self) -> None:
        private_key = Ed25519PrivateKey.generate()
        public_pem = private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firmware = root / "firmware.bin"
            firmware.write_bytes(b"signed firmware")
            signature = root / "firmware.sig"
            signature.write_bytes(private_key.sign(firmware.read_bytes()))
            repo = FirmwareRepo(root / "repo", {"release": public_pem})
            uploaded = repo.upload("esp32", "1.2.3", firmware, signature_path=signature, key_id="release")
            self.assertTrue(uploaded["ok"])
            self.assertTrue(repo.verify_artifact("esp32", "1.2.3")["ok"])
            repo.get_firmware_path("esp32", "1.2.3").write_bytes(b"tampered")
            verified = repo.verify_artifact("esp32", "1.2.3")
            self.assertFalse(verified["ok"])
            self.assertFalse(verified["sha256_valid"])

    def test_ab_switch_and_rollback_preserve_known_good_slot(self) -> None:
        registry = DeviceRegistry()
        registry.register("192.0.2.1", "esp32", "1.0.0", "AA:BB:CC:DD:EE:FF")
        prepared = registry.prepare_ab_switch("192.0.2.1", "1.1.0")
        self.assertTrue(prepared["ok"])
        self.assertEqual(prepared["device"]["active_partition"], "A")
        self.assertEqual(prepared["device"]["pending_partition"], "B")
        self.assertTrue(registry.test_rollback("192.0.2.1")["active_partition_preserved"])
        failed = registry.report_boot_result("192.0.2.1", "B", False, "boot self-test failed")
        self.assertTrue(failed["rolled_back"])
        self.assertEqual(failed["device"]["active_partition"], "A")


if __name__ == "__main__":
    unittest.main()
