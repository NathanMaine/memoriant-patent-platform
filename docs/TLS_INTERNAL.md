# TLS Between Internal Docker Containers

This document describes how to enable mutual TLS (mTLS) for communication between services in the Memoriant Patent Platform Docker stack. TLS between internal containers is **optional for single-host deployments** and **recommended for multi-host deployments** (e.g., Docker Swarm across multiple machines or Kubernetes).

For single-host Docker, all inter-container traffic travels over a private Docker bridge network that is not accessible from outside the host. The risk profile is low. For multi-host deployments, traffic crosses physical or virtual network segments where interception is possible, and TLS should be enabled.

## Overview of the Approach

1. Generate an internal Certificate Authority (CA) for the platform.
2. Issue a certificate/key pair for each service (patent-api, qdrant, supabase-db).
3. Mount the CA cert and per-service cert/key into each container.
4. Configure each service to use TLS for incoming connections.
5. Configure each client service to verify peer certificates against the CA.

## Step 1 — Generate the Internal CA

```bash
mkdir -p certs
cd certs

# Generate CA private key
openssl genrsa -out ca.key 4096

# Self-signed CA certificate (valid 10 years for internal use)
openssl req -new -x509 -days 3650 -key ca.key -out ca.crt \
  -subj "/CN=Memoriant Patent Platform Internal CA/O=Memoriant/C=US"
```

Keep `ca.key` secure. Only `ca.crt` needs to be distributed to containers.

## Step 2 — Issue Service Certificates

Repeat for each service. Use the Docker service name as the Common Name so that hostname verification works on the Docker network.

```bash
# patent-api
openssl genrsa -out api.key 2048
openssl req -new -key api.key -out api.csr \
  -subj "/CN=patent-api/O=Memoriant/C=US"
openssl x509 -req -days 825 -in api.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out api.crt \
  -extfile <(printf "subjectAltName=DNS:patent-api,DNS:localhost")

# qdrant
openssl genrsa -out qdrant.key 2048
openssl req -new -key qdrant.key -out qdrant.csr \
  -subj "/CN=qdrant/O=Memoriant/C=US"
openssl x509 -req -days 825 -in qdrant.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out qdrant.crt \
  -extfile <(printf "subjectAltName=DNS:qdrant,DNS:localhost")

# supabase-db
openssl genrsa -out pg.key 2048
openssl req -new -key pg.key -out pg.csr \
  -subj "/CN=supabase-db/O=Memoriant/C=US"
openssl x509 -req -days 825 -in pg.csr -CA ca.crt -CAkey ca.key \
  -CAcreateserial -out pg.crt \
  -extfile <(printf "subjectAltName=DNS:supabase-db,DNS:localhost")

cd ..
```

Set restrictive permissions on all private keys:
```bash
chmod 600 certs/*.key
```

Add `certs/` to `.gitignore` — never commit private keys:
```bash
echo "certs/" >> .gitignore
```

## Step 3 — Configure Postgres SSL

Postgres reads SSL config from `postgresql.conf` and command-line flags. Pass flags via the compose `command:` override:

```yaml
supabase-db:
  image: supabase/postgres:15
  command: >
    postgres
    -c ssl=on
    -c ssl_cert_file=/certs/pg.crt
    -c ssl_key_file=/certs/pg.key
    -c ssl_ca_file=/certs/ca.crt
  volumes:
    - pg_data:/var/lib/postgresql/data
    - ./certs/ca.crt:/certs/ca.crt:ro
    - ./certs/pg.crt:/certs/pg.crt:ro
    - ./certs/pg.key:/certs/pg.key:ro
```

The `patent-api` service connecting to Postgres should set `sslmode=verify-full` and point to the CA certificate:
```
DATABASE_URL=postgresql://postgres:<password>@supabase-db:5432/postgres?sslmode=verify-full&sslrootcert=/certs/ca.crt
```

## Step 4 — Configure Qdrant TLS

Qdrant supports TLS via environment variables:

```yaml
qdrant:
  image: qdrant/qdrant:latest
  environment:
    QDRANT__SERVICE__ENABLE_TLS: "true"
    QDRANT__TLS__CERT: /certs/qdrant.crt
    QDRANT__TLS__KEY: /certs/qdrant.key
    QDRANT__TLS__CA_CERT: /certs/ca.crt
  volumes:
    - qdrant_data:/qdrant/storage
    - ./certs/ca.crt:/certs/ca.crt:ro
    - ./certs/qdrant.crt:/certs/qdrant.crt:ro
    - ./certs/qdrant.key:/certs/qdrant.key:ro
```

The `patent-api` service must then use `https://qdrant:6333` and pass the CA cert when constructing the Qdrant client:

```python
from qdrant_client import QdrantClient

client = QdrantClient(
    host="qdrant",
    port=6333,
    https=True,
    ca_certs="/certs/ca.crt",
    # For mutual TLS, also pass:
    # cert=("/certs/api.crt", "/certs/api.key"),
)
```

## Step 5 — Mount Certs into patent-api

```yaml
patent-api:
  build: .
  volumes:
    - ./certs/ca.crt:/certs/ca.crt:ro
    - ./certs/api.crt:/certs/api.crt:ro
    - ./certs/api.key:/certs/api.key:ro
  environment:
    SSL_CA_CERT: /certs/ca.crt
    SSL_CERT: /certs/api.crt
    SSL_KEY: /certs/api.key
```

Note: The existing compose file uses `read_only: true` on `patent-api`. The cert mounts use `:ro` (read-only), which is compatible with this setting.

## Certificate Rotation

Certificates issued with 825-day validity should be rotated annually. Steps:

1. Generate new cert/key pairs for each service (re-using the same CA).
2. Replace the files in `certs/`.
3. Restart affected services: `docker compose restart patent-api qdrant supabase-db`.

To rotate the CA itself, all service certs must also be re-issued simultaneously and all containers restarted.

## Summary: Single-Host vs. Multi-Host

| Deployment | Recommendation |
|---|---|
| Single host, Docker bridge | Optional. Bridge network is isolated; risk is low. |
| Multi-host Docker Swarm | Recommended. Traffic crosses network segments. |
| Kubernetes (future) | Use a service mesh (Istio, Linkerd) or cert-manager for mTLS. |

For the current Memoriant Patent Platform single-host deployment on the DGX Spark, enabling TLS between internal containers is a hardening measure rather than a strict requirement. Enable it if the host is shared or if the platform handles data subject to compliance requirements (HIPAA, FedRAMP) that mandate encryption in transit for all network paths.
