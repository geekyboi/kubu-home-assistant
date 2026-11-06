"""One-time Kubu cloud sign-in, used only by the config flow to fetch sensor keys."""

from __future__ import annotations

from typing import Any

import aiohttp

from .const import API_BASE, normalize_mac

NODE_FIELDS = (
    "name",
    "devAlias",
    "dpKey",
    "type",
    "sensorClass",
    "productType",
    "fwVer",
    "hwRev",
)


class KubuError(Exception):
    """Base error."""


class InvalidAuth(KubuError):
    """Wrong email or password."""


class CannotConnect(KubuError):
    """Kubu cloud unreachable or returned something unexpected."""


async def async_fetch_sensors(
    session: aiohttp.ClientSession, email: str, password: str
) -> tuple[str, list[dict[str, Any]]]:
    """Sign in and return (account id, Bluetooth sensors with their keys)."""
    try:
        async with session.post(
            f"{API_BASE}/oauth/login",
            json={"email": email, "password": password},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status in (400, 401, 403):
                raise InvalidAuth
            resp.raise_for_status()
            login = await resp.json(content_type=None)
        token = login["idToken"]
        sensors: dict[str, dict[str, Any]] = {}
        for home in login.get("homes") or []:
            async with session.get(
                f"{API_BASE}/view/rooms",
                params={"homeId": home["id"]},
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as resp:
                resp.raise_for_status()
                dash = await resp.json(content_type=None)
            for node in dash.get("bleNodes") or []:
                if not node.get("sNo") or not node.get("dpKey"):
                    continue
                mac = normalize_mac(node["sNo"])
                sensors[mac] = {"mac": mac} | {k: node.get(k) for k in NODE_FIELDS}
    except InvalidAuth:
        raise
    except (aiohttp.ClientError, TimeoutError, KeyError, ValueError) as err:
        raise CannotConnect(str(err)) from err
    return str(login.get("id") or email.lower()), list(sensors.values())
