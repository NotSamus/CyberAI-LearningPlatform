"""Migrations in sql/ apply and roll back on an empty database, and match the models.

Runs against a throwaway database on the dev Postgres (see test/conftest.py).
"""


def test_upgrade_downgrade_and_models_in_sync(empty_db_url, alembic):
    alembic("upgrade", "head", db_url=empty_db_url)
    alembic("check", db_url=empty_db_url)          # fails if a model changed without a migration
    alembic("downgrade", "base", db_url=empty_db_url)
    alembic("upgrade", "head", db_url=empty_db_url)
