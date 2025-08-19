# tests/conftest.py
import os
import sys
import pathlib
import importlib
import pytest
from fastapi.testclient import TestClient
from sqlmodel import SQLModel

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

@pytest.fixture(scope="session")
def client(tmp_path_factory):
    # temp DB for tests
    dbfile = tmp_path_factory.mktemp("data") / "test.db"
    os.environ["DB_URL"] = f"sqlite:///{dbfile}"

    # import the app fresh with the test DB_URL
    if "app.main" in sys.modules:
        del sys.modules["app.main"]
    m = importlib.import_module("app.main")

    # make sure tables exist
    SQLModel.metadata.create_all(m.engine)

    with TestClient(m.api) as c:
        yield c
