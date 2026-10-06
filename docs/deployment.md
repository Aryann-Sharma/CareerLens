# Deployment guide

CareerLens is packaged as one web application container. A production deployment
should run that container behind an HTTPS proxy and connect it to a managed
PostgreSQL database.

```text
Browser → HTTPS proxy → CareerLens container → PostgreSQL
```

## Containerized local environment

The Compose setup is useful for testing the container and PostgreSQL together. It
uses the development environment because it is served over local HTTP.

1. Copy `.env.docker.example` to `.env.docker`.
2. Set `POSTGRES_PASSWORD` to a URL-safe local database password.
3. Generate a session-signing secret:

   ```text
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

4. Put the generated value in `AUTH_SECRET_KEY`.
5. Build and start the stack:

   ```text
   docker compose --env-file .env.docker up --build
   ```

Compose waits for PostgreSQL to become healthy, applies the Alembic migrations,
and then starts the application. Open `http://127.0.0.1:8000` when the app is
ready.

Stop the containers with:

```text
docker compose --env-file .env.docker down
```

The `postgres_data` volume keeps local database data between restarts. Running
`docker compose down -v` also removes that volume and its data.

## Production environment

Set these values in the hosting provider's secret or environment settings. Do
not commit production values to Git.

| Variable | Purpose |
| --- | --- |
| `ENVIRONMENT=production` | Enables production configuration checks and secure cookies. |
| `DATABASE_URL` | PostgreSQL connection URL using the `postgresql+psycopg://` driver. |
| `AUTH_SECRET_KEY` | Random secret of at least 32 characters used to sign sessions. |
| `AUTH_TOKEN_EXPIRE_MINUTES` | Session lifetime in minutes. Defaults to `60`. |

Production startup is rejected when the development signing secret or a
non-PostgreSQL database URL is used.

## Release process

The exact screens differ between hosting providers, but the deployment sequence
should remain the same:

1. Provision a managed PostgreSQL database with backups enabled.
2. Build the repository's `Dockerfile`.
3. Set the production environment variables through the provider.
4. Run `python -m alembic upgrade head` as a release or migration command.
5. Start the image with its default command.
6. Route HTTPS traffic to port `8000`.
7. Configure the platform readiness check to use `/health/ready`.
8. Keep application logs on standard output so the platform can collect them.

Run one application process per container. If more capacity is needed later,
increase the number of containers through the hosting platform rather than
adding unrelated process-management tools to the image.

## Health checks

- `/health/live` confirms that the application process is responding.
- `/health/ready` also checks the database connection and returns `503` when the
  database is unavailable.
- `/health` remains available as the original liveness endpoint.

## Post-deployment checks

After each deployment:

1. Confirm `/health/live` and `/health/ready` return `200`.
2. Register a temporary account through the browser.
3. Run one job-description analysis and confirm it appears in history.
4. Log out and back in to confirm secure session cookies work through HTTPS.
5. Check that application logs contain no startup, migration, or database errors.
6. Delete the temporary account through an administrator process when account
   management is introduced. Until then, use a clearly labelled deployment-test
   account and remove it directly from the database after validation.

## Operational checklist

Before calling the deployment production-ready, confirm that:

- HTTPS is enforced by the hosting platform.
- Database backups and recovery options are enabled.
- Secrets are stored outside the repository.
- Health alerts and basic error monitoring are configured.
- The public URL has passed the browser smoke test.
- A rollback to the previous container image is possible.
