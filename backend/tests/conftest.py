import os
import sys

import pytest
from fastapi.testclient import TestClient

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)

