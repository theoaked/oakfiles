import logging
import socket
from typing import Optional

from app.config import AppConfig

logger = logging.getLogger(__name__)

_zeroconf = None
_service_info = None


async def start_mdns(config: AppConfig) -> None:
    global _zeroconf, _service_info

    if not config.mdns.enabled:
        return

    try:
        from zeroconf import ServiceInfo
        from zeroconf.asyncio import AsyncZeroconf
    except ImportError:
        logger.warning("zeroconf not installed — mDNS disabled")
        return

    hostname = config.mdns.hostname or socket.gethostname()
    service_name = f"{hostname}._http._tcp.local."
    server = f"{hostname}.local."

    local_ip = _get_local_ip()

    try:
        _service_info = ServiceInfo(
            "_http._tcp.local.",
            service_name,
            addresses=[socket.inet_aton(local_ip)],
            port=config.server.port,
            properties={"path": "/"},
            server=server,
        )
        _zeroconf = AsyncZeroconf()
        await _zeroconf.async_register_service(_service_info)
        logger.info(f"mDNS: announced as http://{hostname}.local:{config.server.port}")
        print(f"mDNS: accessible at http://{hostname}.local:{config.server.port}")
    except Exception as e:
        exc_type = type(e).__name__
        logger.warning(f"mDNS registration failed ({exc_type}): {e or '(no message)'}")
        # Clean up partial state
        if _zeroconf:
            try:
                await _zeroconf.async_close()
            except Exception:
                pass
        _zeroconf = None
        _service_info = None


async def stop_mdns() -> None:
    global _zeroconf, _service_info
    if _zeroconf and _service_info:
        try:
            await _zeroconf.async_unregister_service(_service_info)
            await _zeroconf.async_close()
        except Exception:
            pass
    _zeroconf = None
    _service_info = None


def _get_local_ip() -> str:
    """Best-effort: get the LAN IP (not 127.0.0.1)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
