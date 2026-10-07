"""Start the POC locally; use --host 0.0.0.0 to share on your network."""
import argparse
from pathlib import Path
import sys

import uvicorn

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    # asyncio uses the Windows Proactor loop required for subprocess support.
    uvicorn.run('app:app', host=args.host, port=args.port, loop='asyncio')
