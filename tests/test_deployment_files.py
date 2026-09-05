"""Static checks for systemd deployment artifacts; no Pi hardware is used."""

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICE_FILE = PROJECT_ROOT / "deploy" / "attendance.service"
ENVIRONMENT_EXAMPLE = PROJECT_ROOT / "deploy" / "rfid-attendance.env.example"
README = PROJECT_ROOT / "README.md"
MAIN = PROJECT_ROOT / "main.py"


class DeploymentFileTests(unittest.TestCase):
    def test_systemd_service_uses_expected_paths_and_startup_settings(self):
        service = SERVICE_FILE.read_text()

        self.assertIn("After=network-online.target", service)
        self.assertIn("Wants=network-online.target", service)
        self.assertIn("User=raspberry-user", service)
        self.assertIn(
            "WorkingDirectory=/home/raspberry-user/rfid-attendance",
            service,
        )
        self.assertIn("EnvironmentFile=/etc/rfid-attendance.env", service)
        self.assertIn(
            "ExecStart=/home/raspberry-user/rfid-attendance/venv/bin/python "
            "/home/raspberry-user/rfid-attendance/main.py",
            service,
        )
        self.assertIn("Restart=always", service)
        self.assertIn("RestartSec=3", service)
        self.assertIn("WantedBy=multi-user.target", service)

    def test_environment_example_has_required_placeholder_only_values(self):
        environment = ENVIRONMENT_EXAMPLE.read_text()

        self.assertIn("API_BASE_URL=https://example-attendance-domain", environment)
        self.assertIn("DEVICE_ID=attendance-pi-01", environment)
        self.assertIn("REQUEST_TIMEOUT_SECONDS=5", environment)
        self.assertIn("ENROLLMENT_POLL_SECONDS=3", environment)
        self.assertNotIn("PASSWORD=", environment)
        self.assertNotIn("AES", environment)

    def test_readme_documents_systemd_management_commands(self):
        readme = README.read_text()

        self.assertIn("sudo systemctl daemon-reload", readme)
        self.assertIn("sudo systemctl enable attendance.service", readme)
        self.assertIn("journalctl -u attendance.service -f", readme)

    def test_main_handles_systemd_sigterm_with_existing_cleanup_path(self):
        main = MAIN.read_text()

        self.assertIn("signal.signal(signal.SIGTERM, _handle_shutdown_signal)", main)
        self.assertIn("raise KeyboardInterrupt", main)
