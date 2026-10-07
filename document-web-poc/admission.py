"""Per-caller rate limit and in-process job slots for POST /api/process.

A rejection is returned before the upload is read.
"""
import json
import logging
import math
import os
import threading
import time
from collections import deque
from ipaddress import ip_address

PROCESS_PATH = '/api/process'
MAX_TRACKED_CLIENTS = 4096
BUSY_RETRY_AFTER = 10
RATE_DETAIL = 'Too many requests. Wait and try again.'
BUSY_DETAIL = 'The server is busy processing other documents. Wait and try again.'
CALLERS_DETAIL = 'Too many distinct callers. Wait and try again.'


def _positive_int(name, default):
    raw = os.environ.get(name, '').strip()
    if not raw:
        return default
    if not raw.isdigit():
        raise RuntimeError(f'{name} must be a positive integer.')
    value = int(raw)
    if value < 1:
        raise RuntimeError(f'{name} must be a positive integer.')
    return value


def _trust_proxy():
    raw = os.environ.get('TRUST_PROXY_HEADERS', '').strip().lower()
    if raw in ('', '0', 'false', 'no', 'off'):
        return False
    if raw in ('1', 'true', 'yes', 'on'):
        return True
    raise RuntimeError('TRUST_PROXY_HEADERS must be 1 or 0.')


def gate_from_env():
    return AdmissionGate(
        max_requests=_positive_int('RATE_LIMIT_REQUESTS', 10),
        window_seconds=_positive_int('RATE_LIMIT_WINDOW_SECONDS', 60),
        max_concurrent=_positive_int('MAX_CONCURRENT_JOBS', 2),
        trust_proxy=_trust_proxy(),
    )


def _parse_ip(value):
    text = value.strip().strip('"')
    if not text:
        return None
    if text.startswith('[') and ']' in text:
        text = text[1:text.index(']')]
    elif text.count(':') == 1 and '.' in text:
        host, port = text.rsplit(':', 1)
        if port.isdigit():
            text = host
    try:
        return str(ip_address(text))
    except ValueError:
        return None


def _header(scope, name):
    found = None
    for key, value in scope.get('headers') or ():
        if key.lower() == name:
            found = value
    if found is None:
        return ''
    return found.decode('latin-1', errors='replace')


def _peer(scope):
    client = scope.get('client')
    if not client or not client[0]:
        return 'unknown'
    return _parse_ip(str(client[0])) or 'unknown'


class AdmissionGate:
    def __init__(self, max_requests, window_seconds, max_concurrent, trust_proxy,
                 max_tracked=MAX_TRACKED_CLIENTS):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_concurrent = max_concurrent
        self.trust_proxy = trust_proxy
        self.max_tracked = max_tracked
        self._hits = {}
        self._active = 0
        self._lock = threading.Lock()
        self._now = time.monotonic

    def configure(self, *, max_requests=None, window_seconds=None, max_concurrent=None,
                  trust_proxy=None, max_tracked=None):
        if max_requests is not None:
            self.max_requests = max_requests
        if window_seconds is not None:
            self.window_seconds = window_seconds
        if max_concurrent is not None:
            self.max_concurrent = max_concurrent
        if trust_proxy is not None:
            self.trust_proxy = trust_proxy
        if max_tracked is not None:
            self.max_tracked = max_tracked

    def reset(self):
        with self._lock:
            self._hits.clear()
            self._active = 0
            self._now = time.monotonic

    def client_key(self, scope):
        peer = _peer(scope)
        if not self.trust_proxy:
            return peer
        forwarded = _header(scope, b'x-forwarded-for')
        if not forwarded:
            return peer
        for part in reversed(forwarded.split(',')):
            parsed = _parse_ip(part)
            if parsed:
                return parsed
        return peer

    def _prune(self, now):
        cutoff = now - self.window_seconds
        empty = []
        for key, hits in self._hits.items():
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if not hits:
                empty.append(key)
        for key in empty:
            del self._hits[key]

    def _retry_after(self, hits, now):
        wait = self.window_seconds - (now - hits[0])
        return max(1, math.ceil(wait))

    def try_admit(self, scope):
        """Return None when the request holds a slot. Otherwise (detail, retry_after, reason)."""
        key = self.client_key(scope)
        now = self._now()
        with self._lock:
            self._prune(now)
            if key not in self._hits and len(self._hits) >= self.max_tracked:
                self._log(key, 'callers')
                return (CALLERS_DETAIL, self.window_seconds, 'callers')
            hits = self._hits.setdefault(key, deque())
            if len(hits) >= self.max_requests:
                retry = self._retry_after(hits, now)
                self._log(key, 'rate')
                return (RATE_DETAIL, retry, 'rate')
            hits.append(now)
            if self._active >= self.max_concurrent:
                self._log(key, 'busy')
                return (BUSY_DETAIL, BUSY_RETRY_AFTER, 'busy')
            self._active += 1
            return None

    def release(self):
        with self._lock:
            if self._active < 1:
                raise RuntimeError('job slot released too many times')
            self._active -= 1

    def _log(self, key, reason):
        logged = key if len(key) <= 64 and '\r' not in key and '\n' not in key else 'invalid'
        logging.warning('Rejected POST /api/process reason=%s client=%s', reason, logged)


class AdmissionMiddleware:
    def __init__(self, app, gate):
        self.app = app
        self.gate = gate

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('method') != 'POST' or scope.get('path') != PROCESS_PATH:
            await self.app(scope, receive, send)
            return
        decision = self.gate.try_admit(scope)
        if decision is not None:
            detail, retry_after, _reason = decision
            await _reject(send, detail, retry_after)
            return
        try:
            await self.app(scope, receive, send)
        finally:
            # Synchronous so a cancelled request still returns the slot.
            self.gate.release()


async def _reject(send, detail, retry_after):
    body = json.dumps({'detail': detail}).encode('utf-8')
    await send({
        'type': 'http.response.start',
        'status': 429,
        'headers': [
            (b'content-type', b'application/json'),
            (b'content-length', str(len(body)).encode('ascii')),
            (b'retry-after', str(int(retry_after)).encode('ascii')),
            (b'cache-control', b'no-store'),
            (b'x-content-type-options', b'nosniff'),
        ],
    })
    await send({'type': 'http.response.body', 'body': body})
