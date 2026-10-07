import asyncio
from pathlib import Path
import sys
import pytest
import document_sdk


@pytest.mark.parametrize('cancel', [False, True])
def test_worker_stops_before_cleanup(monkeypatch, tmp_path, cancel):
    # Use a real sleeping child process to verify timeout/cancellation actually kills it.
    (tmp_path / 'DocumentBridge.dll').touch()
    monkeypatch.setattr(document_sdk, 'BUNDLE', tmp_path)
    monkeypatch.setattr(document_sdk.shutil, 'which', lambda _: sys.executable)
    monkeypatch.setenv('PROCESS_TIMEOUT_SECONDS', '0.05' if not cancel else '120')
    original_spawn = asyncio.create_subprocess_exec
    async def scenario():
        started = asyncio.Event()
        children = []
        async def spawn(*args, **kwargs):
            child = await original_spawn(sys.executable, '-c', 'import time; time.sleep(30)', **kwargs)
            children.append(child)
            started.set()
            return child
        monkeypatch.setattr(asyncio, 'create_subprocess_exec', spawn)
        task = asyncio.create_task(document_sdk.run_operation('WordToPdf', tmp_path/'in', tmp_path/'out'))
        await started.wait()
        if cancel:
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else asyncio.TimeoutError):
            await task
        assert children[0].returncode is not None
    asyncio.run(scenario())
