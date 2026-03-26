# Docker Secrets for Production Deployments

This document describes how to replace `.env` file secrets with Docker secrets for production use. Docker secrets are stored in encrypted form in the Docker swarm Raft log and are only ever written to container memory (never to disk inside the container).

## When to Use Docker Secrets

- Any production or staging deployment running Docker Swarm
- Deployments where the `.env` file would otherwise contain passwords, API keys, or tokens in plaintext
- Multi-host deployments where secrets must be distributed to worker nodes securely

For single-developer local development, `.env` is acceptable. For CI/CD pipelines and production, use secrets.

## Creating Secrets

```bash
# Initialize swarm mode if not already active
docker swarm init

# Create a secret from a string value
echo "my-super-secure-password" | docker secret create postgres_password -

# Create a secret from a file
docker secret create postgres_password ./postgres_password.txt

# List all secrets
docker secret ls

# Inspect a secret (metadata only — value is never retrievable after creation)
docker secret inspect postgres_password
```

## Referencing Secrets in docker-compose.yml

Docker secrets are mounted as files under `/run/secrets/<secret_name>` inside the container. Applications read the secret value from the file rather than from an environment variable.

```yaml
services:
  supabase-db:
    image: supabase/postgres:15
    secrets:
      - postgres_password
    environment:
      # The Postgres image reads POSTGRES_PASSWORD_FILE and uses its contents
      POSTGRES_PASSWORD_FILE: /run/secrets/postgres_password

  patent-api:
    build: .
    secrets:
      - openai_api_key
      - jwt_secret
    environment:
      OPENAI_API_KEY_FILE: /run/secrets/openai_api_key
      JWT_SECRET_FILE: /run/secrets/jwt_secret

secrets:
  postgres_password:
    external: true   # created via `docker secret create` before deploying
  openai_api_key:
    external: true
  jwt_secret:
    external: true
```

## Application-Side Secret File Reading

If your application reads environment variables directly and does not support `_FILE` suffixes natively, use a small entrypoint wrapper:

```bash
#!/bin/sh
# entrypoint.sh — load Docker secrets into environment variables
set -e

load_secret() {
  local var_name="$1"
  local file_path="$2"
  if [ -f "$file_path" ]; then
    export "$var_name"="$(cat "$file_path")"
  fi
}

load_secret OPENAI_API_KEY /run/secrets/openai_api_key
load_secret JWT_SECRET /run/secrets/jwt_secret

exec "$@"
```

Reference this in your `Dockerfile`:
```dockerfile
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
```

## Migration Guide: .env to Docker Secrets

### Step 1 — Identify secrets in .env

Audit your `.env` file for values that are sensitive:
```
POSTGRES_PASSWORD=...     <- secret
OPENAI_API_KEY=...        <- secret
JWT_SECRET=...            <- secret
APP_ENV=production        <- not a secret, keep in environment
LOG_LEVEL=info            <- not a secret, keep in environment
```

### Step 2 — Create the Docker secrets

```bash
docker swarm init  # if not already in swarm mode

# Read interactively to avoid shell history leakage
read -rs POSTGRES_PASSWORD && echo "$POSTGRES_PASSWORD" | docker secret create postgres_password -
read -rs OPENAI_API_KEY    && echo "$OPENAI_API_KEY"    | docker secret create openai_api_key -
read -rs JWT_SECRET        && echo "$JWT_SECRET"        | docker secret create jwt_secret -
```

### Step 3 — Update docker-compose.yml

Remove the `env_file: .env` directive from services that carried secrets. Replace with explicit `environment:` entries for non-secret config and `secrets:` entries for sensitive values (as shown above).

### Step 4 — Update the application

Ensure the application reads from `_FILE` environment variables or the entrypoint wrapper above loads secrets before the app process starts.

### Step 5 — Rotate a secret

Docker secrets are immutable — you cannot update a secret in place. To rotate:

```bash
# Create new version
echo "new-password" | docker secret create postgres_password_v2 -

# Update the service to use the new secret
docker service update \
  --secret-rm postgres_password \
  --secret-add postgres_password_v2 \
  memoriant-patent-platform_supabase-db

# Remove old secret once confirmed working
docker secret rm postgres_password
```

### Step 6 — Remove .env from the repository

```bash
# Add to .gitignore if not already there
echo ".env" >> .gitignore

# Remove a previously tracked .env file
git rm --cached .env
git commit -m "chore: remove .env from tracking, use Docker secrets"
```

## Security Notes

- Secrets are only available to services explicitly granted access via `secrets:` in the compose file.
- Secrets are mounted read-only at `/run/secrets/<name>` and visible only to processes in that container.
- On swarm nodes, secrets are stored encrypted at rest in the Raft log and transmitted encrypted over TLS between manager and worker nodes.
- Never log, print, or expose secret values in application output.
