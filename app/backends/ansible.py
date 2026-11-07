import ipaddress
import json
import os
import shutil
import subprocess
from pathlib import Path

from app.backends._common import (
    applied_response,
    error_response,
    router_credentials,
    validate_interface_values,
)


_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def _default_run_playbook(variables):
    executable = shutil.which("ansible-playbook")
    if executable is None:
        raise RuntimeError("ansible-playbook executable is unavailable")

    router_credentials()
    ipv4 = ipaddress.IPv4Interface(variables["ipv4"])
    extra_vars = {
        "router": variables["router"],
        "interface_name": variables["interface_name"],
        "ipv4_address": str(ipv4.ip),
        "netmask": str(ipv4.network.netmask),
        "description": variables["description"],
        "shutdown": variables["shutdown"],
        "ansible_host": variables["router"],
    }
    environment = os.environ.copy()
    environment["ANSIBLE_HOST_KEY_CHECKING"] = "False"
    result = subprocess.run(
        [
            executable,
            "-i",
            str(_REPOSITORY_ROOT / "ansible" / "inventory.ini"),
            str(_REPOSITORY_ROOT / "ansible" / "apply_interface.yml"),
            "--extra-vars",
            json.dumps(extra_vars),
        ],
        cwd=_REPOSITORY_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(f"{result.stdout}\n{result.stderr}")


def apply_interface(
    router,
    desired_interface,
    run_playbook=None,
):
    """Apply complete desired interface state using Ansible."""
    try:
        validate_interface_values(
            desired_interface["name"],
            desired_interface["ipv4"],
            desired_interface["description"],
            desired_interface["admin_state"],
        )
        address = ipaddress.IPv4Interface(desired_interface["ipv4"])
        variables = {
            "router": router,
            "interface_name": desired_interface["name"],
            "ipv4": desired_interface["ipv4"],
            "ipv4_address": str(address.ip),
            "netmask": str(address.network.netmask),
            "description": desired_interface["description"],
            "shutdown": desired_interface["admin_state"] == "down",
        }
        (run_playbook or _default_run_playbook)(variables)
        return applied_response()
    except Exception as exc:
        return error_response(exc)
