"""Test package for JobHunt AI backend.

Tests are organized by layer:
- conftest.py: pytest fixtures (database, session, in-memory repositories)
- test_conftest.py: base fixtures
- test_schema*: schema validation tests
- test_normalization*: normalization tests
- test_dedup*: deduplication tests
- test_scoring*: match scoring tests
- test_api*: FastAPI endpoint tests
- test_persistence*: persistence tests
"""