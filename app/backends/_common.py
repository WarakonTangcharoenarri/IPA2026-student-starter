import ipaddress
import os


def error_response(exc):
    """Map transport exceptions to the shared backend error contract."""
    exception_name = type(exc).__name__.lower()
    message = str(exc).lower()

    if isinstance(exc, PermissionError) or any(
        marker in exception_name or marker in message
        for marker in (
            "authentication",
            "authorization",
            "unauthorized",
            "credential",
            "login failed",
            "permission denied",
        )
    ):
        result = "authentication_failed"
    elif isinstance(exc, (ConnectionError, TimeoutError)) or any(
        marker in exception_name or marker in message
        for marker in (
            "connection",
            "timeout",
            "timed out",
            "unreachable",
            "ssh",
            "sessionerror",
        )
    ):
        result = "connection_failed"
    else:
        result = "backend_failed"

    return {"status": "error", "result": result}


def router_credentials():
    username = os.environ.get("ROUTER_USER")
    password = os.environ.get("ROUTER_PASS")
    if not username or not password:
        raise PermissionError("Router credentials are not configured")
    return username, password


def loopback_number(interface_name):
    prefix = "Loopback"
    if not isinstance(interface_name, str) or not interface_name.startswith(prefix):
        raise ValueError("Expected a Loopback interface name")
    number = interface_name[len(prefix):]
    if not number.isdigit():
        raise ValueError("Invalid Loopback interface name")
    return int(number)


def validate_interface_values(
    interface_name,
    ipv4=None,
    description=None,
    admin_state=None,
):
    loopback_number(interface_name)
    if ipv4 is not None:
        ipaddress.IPv4Interface(ipv4)
    if description is not None and (
        not isinstance(description, str)
        or "\n" in description
        or "\r" in description
    ):
        raise ValueError("Invalid interface description")
    if admin_state is not None and admin_state not in ("up", "down"):
        raise ValueError("Invalid interface administrative state")


def applied_response():
    return {"status": "ok", "result": "applied"}
