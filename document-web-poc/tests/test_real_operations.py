"""Opt-in real worker test: TEST_FIXTURES=/absolute/path python -m pytest tests/test_real_operations.py"""
import asyncio
import io
import os
from pathlib import Path
from zipfile import ZipFile

import httpx
import pytest

from app import app


def test_all_seven_real_operations():
    fixture_path = os.getenv('TEST_FIXTURES')
    if not fixture_path:
        pytest.skip('Set TEST_FIXTURES to the synthetic FixtureGenerator output folder.')
    fixtures = Path(fixture_path)
    async def scenario():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://test') as client:
            async def upload(operation, filename, content):
                response = await client.post('/api/process', files={'file': (filename, content)},
                                             data={'operation': operation, 'label': 'WEB-CONFIDENTIAL'})
                assert response.status_code == 200, response.text
                return response.content
            async def process_format(ext, mark, convert):
                content = await upload(mark, f'input.{ext}', (fixtures/f'input.{ext}').read_bytes())
                with ZipFile(io.BytesIO(content)) as archive:
                    assert archive.testzip() is None
                    assert any(b'WEB-CONFIDENTIAL' in archive.read(name)
                               for name in archive.namelist() if name.endswith('.xml'))
                pdf = await upload(convert, f'classified.{ext}', content)
                assert pdf.startswith(b'%PDF-')
                return pdf
            pdfs = await asyncio.gather(
                process_format('docx', 'mark-word', 'word-to-pdf'),
                process_format('xlsx', 'mark-excel', 'excel-to-pdf'),
                process_format('pptx', 'mark-ppt', 'ppt-to-pdf'))
            marked = await upload('watermark-pdf', 'input.pdf', pdfs[0])
            assert marked.startswith(b'%PDF-') and marked != pdfs[0]
    asyncio.run(scenario())
