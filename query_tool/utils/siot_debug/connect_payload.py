from __future__ import annotations

from dataclasses import asdict
import threading
from typing import Optional

from .models import CloudCredentials, DeviceCredentials
from .session import fetch_cloud_credentials


class CloudCredentialPrefetcher:
    def __init__(self, username: str, password: str) -> None:
        self.username = str(username or "").strip()
        self.password = str(password or "").strip()
        self._lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._credentials: Optional[CloudCredentials] = None
        self._error: Optional[Exception] = None

    def start(self) -> "CloudCredentialPrefetcher":
        if not self.username or not self.password:
            return self
        with self._lock:
            if self._thread is not None:
                return self
            self._thread = threading.Thread(
                target=self._prefetch,
                name="siot-cloud-prefetch",
                daemon=True,
            )
            self._thread.start()
        return self

    def get(self, *, require: bool = False) -> Optional[CloudCredentials]:
        self.start()
        thread = self._thread
        if thread is not None:
            thread.join()
        if self._error is not None and require:
            raise self._error
        return self._credentials

    def _prefetch(self) -> None:
        try:
            self._credentials = fetch_cloud_credentials(
                self.username,
                self.password,
                force_refresh=False,
            )
        except Exception as exc:
            self._error = exc


def build_connect_payload(
    *,
    device_credentials: DeviceCredentials,
    cloud_username: str,
    cloud_password: str,
    prefetched_cloud_credentials: Optional[CloudCredentials] = None,
) -> dict:
    return {
        "action": "connect",
        "cloud": {
            "username": str(cloud_username or "").strip(),
            "password": str(cloud_password or "").strip(),
            "credentials": asdict(prefetched_cloud_credentials)
            if isinstance(prefetched_cloud_credentials, CloudCredentials)
            else None,
        },
        "device": {
            "sn": device_credentials.sn,
            "username": device_credentials.username,
            "password": device_credentials.password,
            "dev_id": device_credentials.dev_id,
            "protocol": device_credentials.protocol,
            "is_siot": device_credentials.is_siot,
        },
    }
