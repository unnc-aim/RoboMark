"""Retired page endpoints must not remain reachable or access business data."""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.core import get_db_dependency
from app.routers.admin import router


@pytest.mark.parametrize("query", ["", "?format=csv", "?format=json"])
def test_statistics_export_is_removed(query):
    app = FastAPI()
    app.include_router(router)

    def unexpected_database_access():
        pytest.fail("A retired statistics export must not access the database")

    app.dependency_overrides[get_db_dependency] = unexpected_database_access
    with TestClient(app) as client:
        response = client.get("/api/admin/statistics/export" + query)
    assert response.status_code == 404
