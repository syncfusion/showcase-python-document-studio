import asyncio
from pathlib import Path

import httpx
import pytest

import admission
from app import app
import app as web


@pytest.fixture(autouse=True)
def reset_admission():
    web.gate.configure(max_requests=10, window_seconds=60, max_concurrent=2,
                       trust_proxy=False, max_tracked=admission.MAX_TRACKED_CLIENTS)
    web.gate.reset()
    yield


STAGING_ORIGIN = 'https://YOUR-APP-NAME.azurewebsites.net'


async def post(data=b'%PDF-1.7\ninput', operation='watermark-pdf', name='input.pdf', label='CONFIDENTIAL',
               origin='http://test'):
    headers = {} if origin is None else {'Origin': origin}
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
        return await client.post('/api/process', files={'file': (name, data)},
                                 data={'operation': operation, 'label': label}, headers=headers)


def test_download_survives_cleanup(monkeypatch):
    folders = []
    async def worker(operation, source, destination, label):
        folders.append(source.parent)
        assert source.read_bytes().startswith(b'%PDF-')
        destination.write_bytes(b'%PDF-1.7\nprocessed')
    monkeypatch.setattr(web, 'run_operation', worker)
    response = asyncio.run(post(name='../../input.pdf'))
    assert response.status_code == 200
    assert response.content == b'%PDF-1.7\nprocessed'
    assert 'watermarked.pdf' in response.headers['content-disposition']
    assert all(not folder.exists() for folder in folders)


@pytest.mark.parametrize('error,status', [(RuntimeError('private server path'), 422),
                                          (asyncio.TimeoutError(), 504),
                                          (FileNotFoundError('missing worker'), 503)])
def test_failure_cleans_folder(monkeypatch, error, status):
    folders = []
    async def worker(operation, source, destination, label):
        folders.append(source.parent)
        destination.write_bytes(b'partial')
        raise error
    monkeypatch.setattr(web, 'run_operation', worker)
    response = asyncio.run(post())
    assert response.status_code == status
    assert 'private server path' not in response.text
    assert folders and all(not folder.exists() for folder in folders)


@pytest.mark.parametrize('kwargs', [dict(operation='delete'), dict(name='file.exe'),
    dict(label=''), dict(label='bad\nlabel'), dict(data=b'not a pdf'), dict(data=b'')])
def test_invalid_input_rejected(monkeypatch, kwargs):
    async def worker(*args):
        pytest.fail('Invalid input reached worker')
    monkeypatch.setattr(web, 'run_operation', worker)
    assert asyncio.run(post(**kwargs)).status_code == 400


def test_simultaneous_requests_are_isolated(monkeypatch):
    folders = []
    async def scenario():
        both_started = asyncio.Event()
        async def worker(operation, source, destination, label):
            folders.append(source.parent)
            if len(folders) == 2:
                both_started.set()
            await asyncio.wait_for(both_started.wait(), 2)
            destination.write_bytes(b'%PDF-1.7\n' + label.encode())
        monkeypatch.setattr(web, 'run_operation', worker)
        return await asyncio.gather(post(label='FIRST'), post(label='SECOND'))
    responses = asyncio.run(scenario())
    assert [r.content for r in responses] == [b'%PDF-1.7\nFIRST', b'%PDF-1.7\nSECOND']
    assert len(set(folders)) == 2
    assert all(not folder.exists() for folder in folders)


def test_cancellation_cleans_request_folder(monkeypatch):
    folders = []
    async def scenario():
        started = asyncio.Event()
        async def worker(operation, source, destination, label):
            folders.append(source.parent)
            started.set()
            await asyncio.Future()
        monkeypatch.setattr(web, 'run_operation', worker)
        task = asyncio.create_task(post())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    asyncio.run(scenario())
    assert folders and all(not folder.exists() for folder in folders)


def test_oversized_file_cleans_folder(monkeypatch):
    monkeypatch.setattr(web, 'MAX_UPLOAD_BYTES', 4)
    assert asyncio.run(post()).status_code == 413


async def _reject_worker(*args):
    pytest.fail('Rejected caller reached worker')


@pytest.mark.parametrize('origin', [None, 'https://evil.example', 'http://test/extra', 'http://user@test'])
def test_process_rejects_disallowed_origin(monkeypatch, origin):
    monkeypatch.setattr(web, 'run_operation', _reject_worker)
    response = asyncio.run(post(origin=origin))
    assert response.status_code == 403
    assert response.json()['detail'] == 'This action is available only from the document site.'


EJ2_SCRIPT = 'https://cdn.syncfusion.com/ej2/34.1.29/dist/ej2.min.js'
EJ2_LIGHT = 'https://cdn.syncfusion.com/ej2/34.1.29/tailwind3.css'
EJ2_DARK = 'https://cdn.syncfusion.com/ej2/34.1.29/tailwind3-dark.css'


def test_index_serves_ej2_controls_and_empty_js_license(monkeypatch):
    monkeypatch.delenv('SYNCFUSION_LICENSE_KEY', raising=False)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            root = await client.get('/')
            script = await client.get('/static/app.js')
            missing = await client.get('/static/ej2/ej2.min.js')
            assert root.status_code == script.status_code == 200
            assert missing.status_code == 404
            assert f'src="{EJ2_SCRIPT}"' in root.text
            assert 'id="ej2-theme"' in root.text
            assert f'href="{EJ2_LIGHT}"' in root.text
            assert f"document.getElementById('ej2-theme').href = '{EJ2_DARK}'" in root.text
            assert 'window.__SYNCFUSION_JS_LICENSE_KEY__ = "";' in root.text
            assert '__SYNCFUSION_JS_LICENSE_JSON__' not in root.text
            assert 'static/ej2/' not in root.text
            assert EJ2_LIGHT in script.text
            assert EJ2_DARK in script.text
            assert 'static/ej2/' not in script.text
    asyncio.run(scenario())


def test_index_injects_js_license_key(monkeypatch):
    monkeypatch.setenv('SYNCFUSION_LICENSE_KEY', 'abc"def<')

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            page = (await client.get('/')).text
            assert 'window.__SYNCFUSION_JS_LICENSE_KEY__ = "abc\\"def\\u003c";' in page
            assert '__SYNCFUSION_JS_LICENSE_JSON__' not in page
    asyncio.run(scenario())


def test_azure_without_allow_list_fails_closed(monkeypatch):
    monkeypatch.setattr(web, 'ALLOWED_PROCESS_ORIGINS', frozenset())
    monkeypatch.setenv('WEBSITE_SITE_NAME', 'example-app-name')
    monkeypatch.setattr(web, 'run_operation', _reject_worker)
    response = asyncio.run(post())
    assert response.status_code == 503
    assert response.json()['detail'] == 'Document processing is not configured.'


def test_allow_list_accepts_only_configured_origin(monkeypatch):
    monkeypatch.setattr(web, 'ALLOWED_PROCESS_ORIGINS', frozenset({STAGING_ORIGIN}))
    calls = []

    async def worker(operation, source, destination, label):
        calls.append(label)
        destination.write_bytes(b'%PDF-1.7\nprocessed')

    monkeypatch.setattr(web, 'run_operation', worker)
    allowed = asyncio.run(post(origin=STAGING_ORIGIN))
    blocked = asyncio.run(post(origin='http://test'))
    assert allowed.status_code == 200
    assert allowed.content == b'%PDF-1.7\nprocessed'
    assert blocked.status_code == 403
    assert calls == ['CONFIDENTIAL']


def _allow_worker(monkeypatch, calls=None):
    async def worker(operation, source, destination, label):
        if calls is not None:
            calls.append(1)
        destination.write_bytes(b'%PDF-1.7\nprocessed')
    monkeypatch.setattr(web, 'run_operation', worker)


def _track_temp_dirs(monkeypatch):
    created = []
    real = web.tempfile.TemporaryDirectory

    def track(*args, **kwargs):
        created.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(web.tempfile, 'TemporaryDirectory', track)
    return created


def _post_with(headers):
    async def one():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            return await client.post(
                '/api/process',
                files={'file': ('input.pdf', b'%PDF-1.7\ninput')},
                data={'operation': 'watermark-pdf', 'label': 'CONFIDENTIAL'},
                headers=headers)
    return one()


def test_rate_limit_rejects_before_the_upload_is_stored(monkeypatch):
    web.gate.configure(max_requests=1, window_seconds=60, max_concurrent=2)
    clock = {'t': 1000.0}
    web.gate._now = lambda: clock['t']
    calls = []
    created = _track_temp_dirs(monkeypatch)
    _allow_worker(monkeypatch, calls)

    async def scenario():
        first = await post()
        clock['t'] = 1010.0
        second = await post()
        return first, second

    first, second = asyncio.run(scenario())
    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()['detail'] == admission.RATE_DETAIL
    assert second.headers['retry-after'] == '50'
    assert second.headers['cache-control'] == 'no-store'
    assert calls == [1]
    assert created == [1]


def test_concurrency_limit_rejects_the_overlapping_request(monkeypatch):
    web.gate.configure(max_requests=10, max_concurrent=1)
    created = _track_temp_dirs(monkeypatch)

    async def scenario():
        started = asyncio.Event()
        release = asyncio.Event()

        async def worker(operation, source, destination, label):
            started.set()
            await release.wait()
            destination.write_bytes(b'%PDF-1.7\nprocessed')

        monkeypatch.setattr(web, 'run_operation', worker)
        first = asyncio.create_task(post())
        await started.wait()
        assert created == [1]
        second = await post()
        assert second.status_code == 429
        assert second.json()['detail'] == admission.BUSY_DETAIL
        assert second.headers['retry-after'] == '10'
        assert created == [1]
        release.set()
        assert (await first).status_code == 200
        assert (await post()).status_code == 200
        assert created == [1, 1]

    asyncio.run(scenario())


@pytest.mark.parametrize('error', [RuntimeError('private server path'), asyncio.TimeoutError()])
def test_slot_released_after_worker_failure(monkeypatch, error):
    web.gate.configure(max_requests=10, max_concurrent=1)
    calls = {'n': 0}

    async def worker(operation, source, destination, label):
        calls['n'] += 1
        if calls['n'] == 1:
            raise error
        destination.write_bytes(b'%PDF-1.7\nprocessed')

    monkeypatch.setattr(web, 'run_operation', worker)
    assert asyncio.run(post()).status_code in (422, 504)
    assert asyncio.run(post()).status_code == 200


def test_slot_released_after_validation_failure(monkeypatch):
    web.gate.configure(max_requests=10, max_concurrent=1)
    _allow_worker(monkeypatch)
    assert asyncio.run(post(operation='delete')).status_code == 400
    assert asyncio.run(post()).status_code == 200


def test_slot_released_after_cancel(monkeypatch):
    web.gate.configure(max_requests=10, max_concurrent=1)

    async def scenario():
        started = asyncio.Event()
        phase = {'wait': True}

        async def worker(operation, source, destination, label):
            if phase['wait']:
                started.set()
                await asyncio.Future()
            destination.write_bytes(b'%PDF-1.7\nprocessed')

        monkeypatch.setattr(web, 'run_operation', worker)
        task = asyncio.create_task(post())
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        phase['wait'] = False
        assert (await post()).status_code == 200

    asyncio.run(scenario())


def test_page_and_static_are_not_rate_limited(monkeypatch):
    web.gate.configure(max_requests=1, max_concurrent=1)
    _allow_worker(monkeypatch)

    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            for _ in range(5):
                assert (await client.get('/')).status_code == 200
                assert (await client.get('/static/app.js')).status_code == 200
            return await post()

    assert asyncio.run(scenario()).status_code == 200


def test_rejected_origin_does_not_use_a_rate_slot(monkeypatch):
    web.gate.configure(max_requests=1, max_concurrent=1)
    _allow_worker(monkeypatch)
    assert asyncio.run(post(origin='https://evil.example')).status_code == 403
    assert asyncio.run(post()).status_code == 200


def test_forwarded_for_is_ignored_unless_trust_is_enabled(monkeypatch):
    web.gate.configure(max_requests=1, trust_proxy=False)
    _allow_worker(monkeypatch)

    async def one(forwarded):
        return await _post_with({'Origin': 'http://test', 'X-Forwarded-For': forwarded})

    async def scenario():
        first = await one('1.1.1.1')
        second = await one('2.2.2.2')
        return first.status_code, second.status_code

    assert asyncio.run(scenario()) == (200, 429)

    web.gate.configure(trust_proxy=True)
    web.gate.reset()

    async def trusted():
        first = await one('8.8.8.8, 1.1.1.1')
        second = await one('9.9.9.9, 2.2.2.2')
        third = await one('1.1.1.1')
        spoofed_peer = await one('not-an-ip')
        same_peer = await one('also-not-an-ip')
        return (first.status_code, second.status_code, third.status_code,
                spoofed_peer.status_code, same_peer.status_code)

    assert asyncio.run(trusted()) == (200, 200, 429, 200, 429)


def test_tracked_caller_cap_rejects_a_new_address(monkeypatch):
    web.gate.configure(max_requests=2, max_concurrent=2, trust_proxy=True, max_tracked=1,
                       window_seconds=60)
    clock = {'t': 5000.0}
    web.gate._now = lambda: clock['t']
    _allow_worker(monkeypatch)

    async def one(forwarded):
        return await _post_with({'Origin': 'http://test', 'X-Forwarded-For': forwarded})

    async def scenario():
        first = await one('1.1.1.1')
        blocked = await one('2.2.2.2')
        again = await one('1.1.1.1')
        clock['t'] = 5061.0
        expired = await one('2.2.2.2')
        return (first.status_code, blocked.status_code, blocked.json()['detail'],
                again.status_code, expired.status_code)

    assert asyncio.run(scenario()) == (200, 429, admission.CALLERS_DETAIL, 200, 200)


def test_admission_env_fails_closed(monkeypatch):
    monkeypatch.delenv('RATE_LIMIT_REQUESTS', raising=False)
    monkeypatch.delenv('RATE_LIMIT_WINDOW_SECONDS', raising=False)
    monkeypatch.delenv('MAX_CONCURRENT_JOBS', raising=False)
    monkeypatch.delenv('TRUST_PROXY_HEADERS', raising=False)
    gate = admission.gate_from_env()
    assert (gate.max_requests, gate.window_seconds, gate.max_concurrent, gate.trust_proxy) == (10, 60, 2, False)

    monkeypatch.setenv('MAX_CONCURRENT_JOBS', '0')
    with pytest.raises(RuntimeError):
        admission.gate_from_env()
    monkeypatch.setenv('MAX_CONCURRENT_JOBS', 'no')
    with pytest.raises(RuntimeError):
        admission.gate_from_env()
    monkeypatch.setenv('MAX_CONCURRENT_JOBS', '2')
    monkeypatch.setenv('TRUST_PROXY_HEADERS', 'maybe')
    with pytest.raises(RuntimeError):
        admission.gate_from_env()
    monkeypatch.setenv('TRUST_PROXY_HEADERS', '1')
    assert admission.gate_from_env().trust_proxy is True
