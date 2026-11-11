"""Fixed-host TCP race; HTTPSConnection retains TLS, certificate checks and SNI."""
import errno
from itertools import zip_longest
import selectors
import socket
import time


def connect_telegram(address, timeout, source_address=None):
    """Start the other address family after 250 ms, without waiting one full timeout.

    This hook replaces only HTTPConnection's TCP dialer on one connection instance.
    It neither wraps TLS nor changes any system-wide socket/network configuration.
    """
    if address != ('api.telegram.org', 443) or source_address is not None:
        raise OSError('telegram_connection_target_denied')
    infos = socket.getaddrinfo(*address, type=socket.SOCK_STREAM)
    infos = [item for item in infos if item[0] in (socket.AF_INET, socket.AF_INET6)]
    if not infos:
        raise OSError('telegram_connection_unavailable')
    first = infos[0][0]
    primary = [item for item in infos if item[0] == first]
    alternate = [item for item in infos if item[0] != first]
    ordered = [item for pair in zip_longest(primary, alternate) for item in pair if item is not None]
    in_progress = {0, errno.EINPROGRESS, errno.EWOULDBLOCK, errno.EALREADY,
                   10035, 10036, 10037}  # Winsock nonblocking connection states.
    selector = selectors.DefaultSelector()
    sockets, winner = [], None
    pending = set()
    budget = float(timeout)
    deadline, next_start = time.monotonic()+budget, time.monotonic()
    index, last_error = 0, None
    try:
        while pending or index < len(ordered):
            now = time.monotonic()
            if now >= deadline:
                raise TimeoutError('telegram_connection_timeout')
            if index < len(ordered) and (not pending or now >= next_start):
                family, kind, proto, _, endpoint = ordered[index]
                index += 1
                try:
                    candidate = socket.socket(family, kind, proto)
                except OSError as error:
                    last_error = error
                    continue
                sockets.append(candidate)
                candidate.setblocking(False)
                try:
                    status = candidate.connect_ex(endpoint)
                except OSError as error:
                    last_error = error
                    candidate.close()
                else:
                    if status == 0:
                        candidate.settimeout(budget)
                        winner = candidate
                        return winner
                    if status in in_progress:
                        selector.register(candidate, selectors.EVENT_WRITE)
                        pending.add(candidate)
                    else:
                        last_error = OSError(status, 'telegram_connection_unavailable')
                        candidate.close()
                next_start = time.monotonic()+0.25
                if not pending:
                    continue
            now = time.monotonic()
            wait = max(0, deadline-now)
            if index < len(ordered):
                wait = min(wait, max(0, next_start-now))
            for key, _ in selector.select(wait):
                candidate = key.fileobj
                error = candidate.getsockopt(socket.SOL_SOCKET, socket.SO_ERROR)
                selector.unregister(candidate)
                pending.remove(candidate)
                if error == 0:
                    candidate.settimeout(budget)
                    winner = candidate
                    return winner
                last_error = OSError(error, 'telegram_connection_unavailable')
                candidate.close()
        raise last_error or OSError('telegram_connection_unavailable')
    finally:
        selector.close()
        for candidate in sockets:
            if candidate is not winner:
                candidate.close()
