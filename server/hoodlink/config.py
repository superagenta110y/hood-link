import hashlib
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings


def _get_machine_id() -> str:
    # Linux: /etc/machine-id or /var/lib/dbus/machine-id
    for path in ("/etc/machine-id", "/var/lib/dbus/machine-id"):
        try:
            mid = Path(path).read_text().strip()
            if mid:
                return mid
        except OSError:
            pass

    # macOS: IOPlatformUUID via ioreg
    try:
        import subprocess

        out = subprocess.run(
            ["ioreg", "-rd1", "-c", "IOPlatformExpertDevice"],
            capture_output=True,
            text=True,
            timeout=3,
        ).stdout
        for line in out.splitlines():
            if "IOPlatformUUID" in line:
                parts = line.split('"')
                if len(parts) >= 4:
                    return parts[3]
    except Exception:
        pass

    # Windows: registry MachineGuid
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography"
        ) as k:
            return winreg.QueryValueEx(k, "MachineGuid")[0]
    except Exception:
        pass

    # Last resort: MAC address
    import uuid

    return hex(uuid.getnode())


def _default_api_key() -> str:
    raw = _get_machine_id()
    return hashlib.sha256(f"hoodlink-v1:{raw}".encode()).hexdigest()[:32]


class Settings(BaseSettings):
    model_config = {"env_prefix": "HOODLINK_"}

    host: str = "127.0.0.1"
    port: int = 7878
    api_key: str = Field(default_factory=_default_api_key)
    bridge_timeout: float = 10.0
    log_level: str = "info"
    open_browser: bool = True


settings = Settings()
