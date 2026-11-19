# Kubernetes deployment manifests

This folder contains example Kubernetes manifests for running the ledger service and its dependencies.

## Apply manifests

Build the application image before deploying:

```bash
docker build -t ledger-api:latest -f deploy/docker/django/Dockerfile.prod .
docker build -t ledger-console:latest -f frontend/Dockerfile frontend/
```

Apply the database dependencies first, then run migrations before the API rollout:

```bash
kubectl apply -f deploy/k8/postgres.yaml -f deploy/k8/redis.yaml
kubectl apply -f deploy/k8/ledger-migrate.yaml
kubectl wait --for=condition=complete job/ledger-migrate --timeout=5m
kubectl apply -k deploy/k8/
```

## Components

- `postgres.yaml` — PostgreSQL deployment, service, and PVC
- `redis.yaml` — Redis deployment, service, and PVC
- `api.yaml` — Django API deployment and ClusterIP service
- `celery.yaml` — Celery worker deployment
- `frontend.yaml` — staff operations console deployment and ClusterIP service
- `ledger-migrate.yaml` — one-shot database migration Job; run before API rollout

The console service listens on port `8080` and proxies `/api/` requests to the
`ledger-api` service. Expose it through the cluster ingress or use
`kubectl port-forward service/ledger-console 8080:8080` for local access.

## Notes

- The example uses `ledger-api:latest` for both the API and Celery worker. Replace this image reference with your registry image if needed.
- `DB_PASSWORD` and other runtime secrets are configured in plain text for example purposes; use Kubernetes Secrets for production deployments.
