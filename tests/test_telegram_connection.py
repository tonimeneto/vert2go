"""Deterministic TCP race tests: no network, secret, real IP or wall-clock waits."""
import errno
import socket
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.channels.telegram_connection import connect_telegram


class DialerTests(unittest.TestCase):
    def dial(self, *, winner=socket.AF_INET, families=(socket.AF_INET6,socket.AF_INET),
             immediate_failure=False, unsupported=None):
        clock = SimpleNamespace(now=0.0)
        made = []
        class Candidate:
            def __init__(self, family):
                self.family, self.closed, self.timeout = family, False, None
            def setblocking(self, value):
                self.blocking = value
            def connect_ex(self, endpoint):
                return errno.ECONNREFUSED if immediate_failure else errno.EINPROGRESS
            def getsockopt(self, *args):
                return 0
            def settimeout(self, value):
                self.timeout = value
            def close(self):
                self.closed = True
        def make(family, kind, proto):
            if family == unsupported:
                raise OSError('family_unavailable')
            candidate = Candidate(family)
            made.append(candidate)
            return candidate
        class Selector:
            def __init__(self):
                self.registered = set()
            def register(self, candidate, flags):
                self.registered.add(candidate)
            def unregister(self, candidate):
                self.registered.remove(candidate)
            def select(self, timeout):
                for candidate in self.registered:
                    if candidate.family == winner:
                        clock.now += 0.01
                        return [(SimpleNamespace(fileobj=candidate), 2)]
                clock.now += timeout
                return []
            def close(self):
                pass
        addresses = [(family,socket.SOCK_STREAM,6,'',('fictional-address',443)) for family in families]
        patches = [patch('app.channels.telegram_connection.socket.getaddrinfo', return_value=addresses),
                   patch('app.channels.telegram_connection.socket.socket', side_effect=make),
                   patch('app.channels.telegram_connection.selectors.DefaultSelector', Selector),
                   patch('app.channels.telegram_connection.time.monotonic', side_effect=lambda:clock.now)]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return clock, made

    def test_stalled_ipv6_does_not_delay_ipv4_until_full_http_timeout(self):
        clock, made = self.dial()
        winner = connect_telegram(('api.telegram.org',443),35)
        self.assertEqual(winner.family, socket.AF_INET)
        self.assertLess(clock.now, 0.5)
        self.assertTrue(made[0].closed)
        self.assertFalse(winner.closed)
        self.assertEqual(winner.timeout,35)

    def test_working_ipv6_remains_preferred(self):
        clock, made = self.dial(winner=socket.AF_INET6)
        winner = connect_telegram(('api.telegram.org',443),35)
        self.assertEqual(winner.family,socket.AF_INET6)
        self.assertEqual(len(made),1)
        self.assertLess(clock.now,0.25)

    def test_ipv6_only_network_is_supported(self):
        _, made = self.dial(winner=socket.AF_INET6,families=(socket.AF_INET6,))
        self.assertIs(connect_telegram(('api.telegram.org',443),35),made[0])

    def test_resolver_ipv4_preference_is_respected(self):
        _, made = self.dial(families=(socket.AF_INET,socket.AF_INET6))
        self.assertIs(connect_telegram(('api.telegram.org',443),35),made[0])
        self.assertEqual(len(made),1)

    def test_global_connect_deadline_closes_all_candidates(self):
        clock, made = self.dial(winner=None)
        with self.assertRaises(TimeoutError):
            connect_telegram(('api.telegram.org',443),35)
        self.assertEqual(clock.now,35)
        self.assertTrue(all(c.closed for c in made))

    def test_all_addresses_failing_close_sockets_without_sleeping(self):
        clock, made = self.dial(immediate_failure=True)
        with self.assertRaises(OSError):
            connect_telegram(('api.telegram.org',443),35)
        self.assertEqual(clock.now,0)
        self.assertTrue(all(c.closed for c in made))

    def test_unavailable_socket_family_falls_back(self):
        _, made = self.dial(unsupported=socket.AF_INET6)
        self.assertIs(connect_telegram(('api.telegram.org',443),35),made[0])
        self.assertEqual(made[0].family,socket.AF_INET)

    def test_other_hosts_and_source_overrides_are_denied_before_dns(self):
        with patch('app.channels.telegram_connection.socket.getaddrinfo') as resolver:
            for address, source in ((('another-host',443),None),(('api.telegram.org',443),('local',0))):
                with self.assertRaises(OSError):
                    connect_telegram(address,35,source)
            resolver.assert_not_called()
