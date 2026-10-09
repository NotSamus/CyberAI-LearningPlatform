# Database migrations (Alembic)

Run every command from `sql/`. The database is whatever `DATABASE_URL` points to
(default: the dev Postgres on `localhost:5433` that `./dev.sh` starts; production: Postgres, set in
`deploy/docker-compose.yml`). `./dev.sh` runs `alembic upgrade head` every time it starts.

```bash
alembic upgrade head                              # apply all migrations
alembic revision --autogenerate -m "add users"    # new migration in versions/ from model changes
alembic downgrade -1                              # undo the last migration
alembic current                                   # show the applied revision
```

From the project root, use `alembic -c sql/alembic.ini <command>` instead.

Models subclass `Base` from `api/app/db.py` and must be imported in `env.py` for autogenerate
to see them. Always read a generated migration before applying it. `pytest test` checks that
migrations apply, roll back, and match the models, in a throwaway database on the dev Postgres.

Production (from `deploy/`):  `docker compose exec backend alembic -c ../sql/alembic.ini upgrade head`
