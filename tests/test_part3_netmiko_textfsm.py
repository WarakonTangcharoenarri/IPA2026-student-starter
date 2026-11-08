import sys
from types import SimpleNamespace
from pathlib import Path

import pytest
import yaml

import app.backends.netmiko_textfsm as netmiko_textfsm
from app.backends.netmiko_textfsm import (
    delete_interface,
    get_interface_state,
)


PART3_DIR = (
    Path(__file__).resolve().parents[1]
    / "sample-tests"
    / "part3"
    / "netmiko-textfsm"
)

FIXTURE_DIR = PART3_DIR / "fixtures"
CASE_DIR = PART3_DIR / "cases"

CASE_FILES = sorted(
    CASE_DIR.glob("*.yaml")
)


def load_yaml(path):
    with path.open() as f:
        return yaml.safe_load(f)


def make_fake_netmiko_get(fixture):
    data = fixture["netmiko"]

    def fake_netmiko_get(
        router,
        interface_name,
    ):
        exception = data.get("exception")

        if exception == "authentication_error":
            raise PermissionError()

        if exception == "connection_error":
            raise ConnectionError()

        if exception == "backend_error":
            raise RuntimeError()

        return (
            data.get("ip_info", []),
            data.get("descriptions", []),
        )

    return fake_netmiko_get


def make_fake_netmiko_delete(fixture):
    data = fixture["netmiko"]

    def fake_netmiko_delete(
        router,
        interface_name,
    ):
        exception = data.get("exception")

        if exception == "authentication_error":
            raise PermissionError()

        if exception == "connection_error":
            raise ConnectionError()

        if exception == "backend_error":
            raise RuntimeError()

        return data["delete_result"]

    return fake_netmiko_delete


@pytest.mark.parametrize(
    "case_file",
    CASE_FILES,
    ids=lambda path: path.stem,
)
def test_netmiko_textfsm_case(case_file):
    case = load_yaml(case_file)

    fixture = load_yaml(
        FIXTURE_DIR / case["fixture"]
    )

    target = case.get("target", "status")

    if target == "status":
        result = get_interface_state(
            fixture["router"],
            fixture["interface_name"],
            make_fake_netmiko_get(
                fixture
            ),
        )

    elif target == "delete":
        result = delete_interface(
            fixture["router"],
            fixture["interface_name"],
            make_fake_netmiko_delete(
                fixture
            ),
        )

    else:
        pytest.fail(
            f"Unknown target: {target}"
        )

    assert result == case["expected"]


@pytest.mark.parametrize(
    ("interfaces", "expected"),
    [
        (
            [{"intf": "GigabitEthernet1"}],
            {"status": "ok", "result": "deleted"},
        ),
        (
            [{"intf": "Loopback123"}],
            {"status": "error", "result": "backend_failed"},
        ),
        (
            [],
            {"status": "error", "result": "backend_failed"},
        ),
    ],
)
def test_delete_verifies_with_interface_brief(
    monkeypatch,
    interfaces,
    expected,
):
    class FakeConnection:
        def send_command(self, command, use_textfsm=False):
            assert command == "show ip interface brief"
            assert use_textfsm
            return interfaces

        def disconnect(self):
            pass

    monkeypatch.setenv("ROUTER_USER", "user")
    monkeypatch.setenv("ROUTER_PASS", "password")
    monkeypatch.setitem(
        sys.modules,
        "netmiko",
        SimpleNamespace(
            ConnectHandler=lambda **kwargs: FakeConnection(),
        ),
    )
    monkeypatch.setattr(
        netmiko_textfsm,
        "get_interface_state",
        lambda router, interface_name: {
            "status": "ok",
            "result": "found",
            "interface": {"name": interface_name},
        },
    )
    monkeypatch.setattr(
        netmiko_textfsm,
        "_default_netmiko_delete",
        lambda router, interface_name: None,
    )

    result = delete_interface("router", "Loopback123")

    assert result == expected
