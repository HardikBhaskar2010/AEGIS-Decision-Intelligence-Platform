# Shared conftest fixtures for the AEGIS E2E test suite running on the Gemini Enterprise Agent Platform.
import os
import socket
import threading
import time
import pytest
import asyncio
import httpx
import uvicorn
from backend.gateway.main import app
from tests.e2e.mock_server.app import init_db

def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    return port

@pytest.fixture(scope="session")
def mock_server():
    # Ensure database is initialized
    init_db()
    
    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    
    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()
    
    # Wait briefly for uvicorn to startup
    retries = 10
    started = False
    while retries > 0:
        try:
            with socket.create_connection(('127.0.0.1', port), timeout=0.1):
                started = True
                break
        except OSError:
            time.sleep(0.05)
            retries -= 1
            
    if not started:
        raise RuntimeError(f"Mock server failed to start on port {port}")
        
    yield {
        "http_url": f"http://127.0.0.1:{port}",
        "ws_url": f"ws://127.0.0.1:{port}",
        "port": port
    }
    
    server.should_exit = True
    thread.join(timeout=2)

@pytest.fixture
def auth_headers():
    return {"Authorization": "Bearer mock-test-token-key"}

@pytest.fixture
async def client(mock_server):
    async with httpx.AsyncClient(base_url=mock_server["http_url"]) as async_client:
        yield async_client
