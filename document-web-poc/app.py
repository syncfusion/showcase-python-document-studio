"""Single-page document POC. Run with: python run.py"""
import asyncio
import json
import logging
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit
from zipfile import BadZipFile, ZipFile

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from admission import AdmissionMiddleware, gate_from_env
from document_sdk import run_operation

ROOT = Path(__file__).resolve().parent
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
OPERATIONS = {
    'mark-word': ('MarkWord', '.docx', 'classified.docx', True),
    'mark-excel': ('MarkExcel', '.xlsx', 'classified.xlsx', True),
    'mark-ppt': ('MarkPowerPoint', '.pptx', 'classified.pptx', True),
    'word-to-pdf': ('WordToPdf', '.docx', 'converted.pdf', False),
    'excel-to-pdf': ('ExcelToPdf', '.xlsx', 'converted.pdf', False),
    'ppt-to-pdf': ('PowerPointToPdf', '.pptx', 'converted.pdf', False),
    'watermark-pdf': ('WatermarkPdf', '.pdf', 'watermarked.pdf', True),
}
MEDIA_TYPES = {
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
    '.pdf': 'application/pdf',
}
app = FastAPI(title='Document Studio POC')
app.mount('/static', StaticFiles(directory=ROOT / 'static'), name='static')


def _parse_allowed_origins(raw):
    origins = set()
    for item in raw.split(','):
        item = item.strip()
        if not item:
            continue
        parsed = urlsplit(item)
        if (parsed.scheme.lower() not in ('http', 'https') or not parsed.hostname
                or parsed.username or parsed.password
                or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
            raise RuntimeError('ALLOWED_PROCESS_ORIGINS entries must look like https://host')
        host = parsed.hostname.lower()
        if parsed.port:
            host = f'{host}:{parsed.port}'
        origins.add(f'{parsed.scheme.lower()}://{host}')
    return frozenset(origins)


ALLOWED_PROCESS_ORIGINS = _parse_allowed_origins(os.environ.get('ALLOWED_PROCESS_ORIGINS', ''))


def _normalize_origin(origin):
    parsed = urlsplit(origin)
    if (not origin or origin.lower() == 'null' or parsed.username or parsed.password
            or parsed.scheme.lower() not in ('http', 'https') or not parsed.hostname
            or parsed.path not in ('', '/') or parsed.query or parsed.fragment):
        return None
    host = parsed.hostname.lower()
    if parsed.port:
        host = f'{host}:{parsed.port}'
    return f'{parsed.scheme.lower()}://{host}'


def _origin_allowed(scope):
    # An empty allow list on Azure must not mean every caller is accepted.
    if not ALLOWED_PROCESS_ORIGINS and os.environ.get('WEBSITE_SITE_NAME'):
        return None
    headers = {key.decode('latin-1').lower(): value.decode('latin-1')
               for key, value in scope.get('headers') or []}
    normalized = _normalize_origin(headers.get('origin', '').strip())
    if normalized is None:
        return False
    if ALLOWED_PROCESS_ORIGINS:
        return normalized in ALLOWED_PROCESS_ORIGINS
    request_host = headers.get('host', '').strip().lower()
    return normalized.split('://', 1)[1] == request_host


class ProcessOriginMiddleware:
    """Reject POST /api/process unless Origin is the configured site."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http' and scope.get('method') == 'POST':
            path = scope.get('path') or '/'
            if path == '/api/process':
                allowed = _origin_allowed(scope)
                if allowed is None:
                    response = JSONResponse(
                        {'detail': 'Document processing is not configured.'}, status_code=503)
                    await response(scope, receive, send)
                    return
                if not allowed:
                    response = JSONResponse(
                        {'detail': 'This action is available only from the document site.'},
                        status_code=403)
                    await response(scope, receive, send)
                    return
        await self.app(scope, receive, send)


gate = gate_from_env()
# Last registered middleware runs first. Origin rejects a foreign caller before
# a job slot or rate-limit count is taken.
app.add_middleware(AdmissionMiddleware, gate=gate)
app.add_middleware(ProcessOriginMiddleware)


def _js_string(value):
    # json.dumps quotes and escapes. Replace "<" so a key cannot close the script tag.
    return json.dumps(value, ensure_ascii=True).replace('<', '\\u003c')


@app.get('/', include_in_schema=False)
async def index():
    html = (ROOT / 'static' / 'index.html').read_text(encoding='utf-8')
    html = html.replace(
        '__SYNCFUSION_JS_LICENSE_JSON__',
        _js_string(os.environ.get('SYNCFUSION_LICENSE_KEY', '')))
    return HTMLResponse(html, headers={'Cache-Control': 'no-cache'})


def validate_document(source, extension):
    if extension == '.pdf':
        with source.open('rb') as stream:
            valid = stream.read(5) == b'%PDF-'
    else:
        part = {'.docx': 'word/document.xml', '.xlsx': 'xl/workbook.xml',
                '.pptx': 'ppt/presentation.xml'}[extension]
        try:
            with ZipFile(source) as archive:
                valid = part in archive.namelist() and '[Content_Types].xml' in archive.namelist()
        except BadZipFile:
            valid = False
    if not valid:
        raise HTTPException(400, 'The file content does not match the selected document type.')


@app.post('/api/process')
async def process(file: UploadFile = File(...), operation: str = Form(...), label: str = Form('')):
    try:
        if operation not in OPERATIONS:
            raise HTTPException(400, 'Choose a supported operation.')
        method, extension, output_name, needs_label = OPERATIONS[operation]
        if Path(file.filename or '').suffix.lower() != extension:
            raise HTTPException(400, f'This operation requires a {extension} file.')
        if needs_label and (not label.strip() or len(label) > 80 or
                            any(ord(c) < 32 or ord(c) > 126 for c in label)):
            raise HTTPException(400, 'Enter 1–80 printable English characters for the label.')
        # Never use client-supplied filenames as server paths.
        with tempfile.TemporaryDirectory(prefix='document-poc-') as folder:
            source = Path(folder) / ('input' + extension)
            destination = Path(folder) / output_name
            size = 0
            with source.open('wb') as stream:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > MAX_UPLOAD_BYTES:
                        raise HTTPException(413, 'Choose a document smaller than 25 MB.')
                    stream.write(chunk)
            if not size:
                raise HTTPException(400, 'The uploaded file is empty.')
            validate_document(source, extension)
            await run_operation(method, source, destination, label if needs_label else None)
            # POC tradeoff: buffer the result so all disk files can be deleted now.
            content = destination.read_bytes()
        return Response(content, media_type=MEDIA_TYPES[Path(output_name).suffix], headers={
            'Content-Disposition': f'attachment; filename="{output_name}"',
            'Cache-Control': 'no-store', 'X-Content-Type-Options': 'nosniff'})
    except asyncio.TimeoutError:
        raise HTTPException(504, 'Processing took too long. Try a smaller document.') from None
    except FileNotFoundError:
        raise HTTPException(503, 'The document worker is unavailable. Check the server setup.') from None
    except RuntimeError:
        logging.exception('Document processing failed')
        raise HTTPException(422, 'Could not process this document. Check that it opens correctly and is not password protected.') from None
    finally:
        await file.close()
