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
ready. The local app uses HTTP; production requires HTTPS and secure cookies.

Stop the containers with:

```text
docker compose --env-file .env.docker down
```

The `postgres_data` volume keeps local database data between restarts. Running
`docker compose --env-file .env.docker down -v` also removes that volume and its data.

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
database URL without the `postgresql+psycopg://` driver is used. `ENVIRONMENT`
accepts `development`, `testing`, or `production` (ignoring case and surrounding
spaces); other values are rejected. URL-encode reserved characters in database
credentials. Session lifetimes must be between 5 and 10,080 minutes.

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
- `/health/ready` queries the user and analysis table columns without fetching
  rows. It returns `503` if the database is unavailable or the required schema
  is missing. It does not replace the migration consistency check.
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
- The public URL has passed the browser smoke test, including Secure cookies.
- Authentication and analysis endpoints have request rate limits at the proxy
  or application layer; the application does not yet provide them.
- A rollback to the previous container image is possible.

Keep schema changes compatible with the image being restored. Back up the
database before applying migrations; downgrades can remove tables or columns.

Accounts currently have no password-reset or email-verification flow. Logout
clears the browser cookie but does not revoke a copied session token before its
expiry. These are limitations to address before a wider public launch.

See the [testing guide](testing.md) for automated checks and disposable
PostgreSQL test configuration.
