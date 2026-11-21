"""Shared test setup: no test may touch the network or resolve a name."""

import socket

import pytest


def _blocked(*args, **kwargs):
    raise RuntimeError("network access is not allowed in evidex tests")


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    for name in ("getaddrinfo", "gethostbyname", "gethostbyname_ex", "gethostbyaddr",
                 "create_connection"):
        monkeypatch.setattr(socket, name, _blocked)
    monkeypatch.setattr(socket.socket, "connect", _blocked)
    monkeypatch.setattr(socket.socket, "connect_ex", _blocked)
