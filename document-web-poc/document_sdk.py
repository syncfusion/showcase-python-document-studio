"""Async JSON-over-stdin adapter for the existing .NET document worker."""
import asyncio
import json
import os
from pathlib import Path
import shutil

BUNDLE = Path(__file__).resolve().parent / 'artifacts'


async def run_operation(operation, source, destination, label=None):
    dll = BUNDLE / 'DocumentBridge.dll'
    dotnet = shutil.which('dotnet')
    if not dll.is_file() or not dotnet:
        raise FileNotFoundError('Publish DocumentBridge and install the .NET 10 runtime first.')
    request = {'Operation': operation, 'Input': str(source), 'Output': str(destination),
               'Label': label, 'AllowTrial': not bool(os.getenv('SYNCFUSION_LICENSE_KEY', '').strip())}
    env = os.environ.copy()
    library_path = str(BUNDLE)
    if env.get('LD_LIBRARY_PATH'):
        library_path = library_path + os.pathsep + env['LD_LIBRARY_PATH']
    env['LD_LIBRARY_PATH'] = library_path
    process = await asyncio.create_subprocess_exec(
        dotnet, str(dll), stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        env=env)
    try:
        _, stderr = await asyncio.wait_for(
            process.communicate(json.dumps(request).encode('utf-8')),
            timeout=float(os.getenv('PROCESS_TIMEOUT_SECONDS', '120')))
    except BaseException:
        # Stop the child before its request folder is deleted, including cancellation.
        if process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
        await process.communicate()
        raise
    if process.returncode:
        raise RuntimeError(stderr.decode('utf-8', errors='replace').strip())
