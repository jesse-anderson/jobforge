"""Tests never touch the network (CLAUDE.md). conftest's autouse guard makes
any connection from a test fail, so a stub that stops matching the code
fails loudly instead of quietly reaching a real site (found in #28, F5)."""
import socket

import pytest


def test_a_connection_from_a_test_fails():
    with pytest.raises(AssertionError, match="network connection"):
        socket.create_connection(("example.com", 80))
    with pytest.raises(AssertionError, match="network connection"):
        socket.socket().connect(("example.com", 80))
