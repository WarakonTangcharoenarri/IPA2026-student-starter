from ipaddress import IPv4Interface, IPv4Network
from urllib.parse import quote

import requests

from app.backends._common import (
    applied_response,
    error_response,
    loopback_number,
    router_credentials,
    validate_interface_values,
)
from app.backends.planning import plan_interface as _plan_interface


_BASE_URL = "https://{router}/restconf/data"
_INTERFACE_NS = "ietf-interfaces:interfaces/interface"


def _default_get(url):
    return requests.get(
        url,
        auth=router_credentials(),
        headers={"Accept": "application/yang-data+json"},
        timeout=10,
    )


def _default_put(url, *, json):
    return requests.put(
        url,
        json=json,
        auth=router_credentials(),
        headers={
            "Accept": "application/yang-data+json",
            "Content-Type": "application/yang-data+json",
        },
        timeout=10,
    )


def _interface_url(router, interface_name):
    return (
        f"{_BASE_URL.format(router=router)}/"
        f"{_INTERFACE_NS}={quote(interface_name, safe='')}"
    )


def _status_from_payload(payload):
    if not isinstance(payload, dict):
        raise ValueError("RESTCONF response is not a JSON object")
    interface = payload.get("ietf-interfaces:interface")
    if not isinstance(interface, dict):
        raise ValueError("RESTCONF response has no interface object")

    name = interface.get("name")
    enabled = interface.get("enabled")
    if not isinstance(name, str) or not isinstance(enabled, bool):
        raise ValueError("RESTCONF interface response is incomplete")

    ipv4 = interface.get("ietf-ip:ipv4")
    addresses = ipv4.get("address") if isinstance(ipv4, dict) else None
    if not isinstance(addresses, list) or not addresses:
        raise ValueError("RESTCONF interface response has no IPv4 address")
    address = addresses[0]
    if not isinstance(address, dict):
        raise ValueError("RESTCONF IPv4 address is malformed")

    ip = address.get("ip")
    netmask = address.get("netmask")
    if not isinstance(ip, str) or not isinstance(netmask, str):
        raise ValueError("RESTCONF IPv4 address is incomplete")
    prefix = IPv4Network(f"0.0.0.0/{netmask}").prefixlen
    ipv4_address = str(IPv4Interface(f"{ip}/{prefix}"))

    return {
        "status": "ok",
        "result": "found",
        "interface": {
            "name": name,
            "ipv4": ipv4_address,
            "description": interface.get("description"),
            "admin_state": "up" if enabled else "down",
        },
    }


def get_interface_state(
    router,
    interface_name,
    http_get=None,
):
    """Return normalized interface status using RESTCONF."""
    get = http_get or _default_get
    try:
        response = get(_interface_url(router, interface_name))
        if response.status_code == 404:
            return {
                "status": "ok",
                "result": "not_found",
                "interface": None,
            }
        if response.status_code in (401, 403):
            return {"status": "error", "result": "authentication_failed"}
        if not 200 <= response.status_code < 300:
            return {"status": "error", "result": "backend_failed"}
        return _status_from_payload(response.json())
    except Exception as exc:
        return error_response(exc)


def plan_interface(
    router,
    desired_interface,
    http_get=None,
):
    """Return create/update/no_change plan using RESTCONF status."""
    return _plan_interface(
        router,
        desired_interface,
        lambda target, name: get_interface_state(
            target,
            name,
            http_get,
        ),
    )


def apply_interface(
    router,
    desired_interface,
    http_put=None,
):
    """Apply complete desired interface state using RESTCONF."""
    try:
        validate_interface_values(
            desired_interface["name"],
            desired_interface["ipv4"],
            desired_interface["description"],
            desired_interface["admin_state"],
        )
        number = loopback_number(desired_interface["name"])
        address = IPv4Interface(desired_interface["ipv4"])
        payload = {
            "Cisco-IOS-XE-native:Loopback": {
                "name": number,
                "description": desired_interface["description"],
                "ip": {
                    "address": {
                        "primary": {
                            "address": str(address.ip),
                            "mask": str(address.network.netmask),
                        }
                    }
                },
            }
        }
        if desired_interface["admin_state"] == "down":
            payload["Cisco-IOS-XE-native:Loopback"]["shutdown"] = [None]

        put = http_put or _default_put
        url = (
            f"{_BASE_URL.format(router=router)}/"
            "Cisco-IOS-XE-native:native/interface/"
            f"Loopback={number}"
        )
        response = put(url, json=payload)
        if response.status_code in (401, 403):
            return {"status": "error", "result": "authentication_failed"}
        if response.status_code not in (200, 201, 204):
            return {"status": "error", "result": "backend_failed"}
        return applied_response()
    except Exception as exc:
        return error_response(exc)
