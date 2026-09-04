# TruthScope container and AWS deployment

The first completed AWS deployment used private ECR plus one EC2 host and direct hardened Docker
containers. Its reproducible commands and observed failures are recorded in
[Deployment Part 1](deployment/deployment-part-1.md). The no-domain HTTPS and OAuth continuation is
recorded in [Deployment Part 2](deployment/deployment-part-2-quick-tunnels.md). This document
describes local Compose and the longer-term ECS/Fargate deployment alternative.

TruthScope ships as two independent container images:

| Image | Runtime | Port | Health check |
|---|---|---:|---|
| `truthscope-backend` | FastAPI/Uvicorn | 8000 | `/api/v1/health` |
| `truthscope-frontend` | Nginx static site | 8080 | `/healthz` |

The local Compose stack is the fastest way to validate both images. For a longer-lived AWS target,
each image can become its own ECS service so the frontend and backend scale and restart
independently.

## 1. Container files

~~~text
compose.yaml                         Local two-service stack
compose.env.example                  Public Compose configuration template
backend/Dockerfile                   Python runtime image
backend/.dockerignore                Excludes secrets, tests, and local artifacts
frontend/Dockerfile                  Rootless Nginx runtime image
frontend/nginx.conf                  Static serving and health endpoint
frontend/config.template.js          Runtime browser configuration template
frontend/docker-entrypoint.d/        Generates config.js when container starts
frontend/.dockerignore               Excludes local config and artifacts
~~~

Both containers run as non-root users. Compose also enables a read-only root filesystem, drops all
Linux capabilities, and prevents privilege escalation. Temporary runtime files use bounded
`tmpfs` mounts.

## 2. Run the complete stack locally

Prerequisites: Docker Engine with Docker Compose v2 and a configured `backend/.env`.

Create the public Compose configuration:

~~~bash
cp compose.env.example compose.env
~~~

Edit `compose.env` with the same Supabase project used by the backend:

~~~dotenv
FRONTEND_API_BASE_URL=http://127.0.0.1:8000/api/v1
FRONTEND_OAUTH_REDIRECT_URL=http://127.0.0.1:8080/
FRONTEND_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co
FRONTEND_SUPABASE_PUBLISHABLE_KEY=YOUR_PUBLIC_PUBLISHABLE_OR_ANON_KEY
BACKEND_CORS_ALLOWED_ORIGINS=http://127.0.0.1:8080,http://localhost:8080
~~~

Only public browser values belong in `compose.env`. Keep Gonka, Brave, backend Supabase, and OAuth
secrets in `backend/.env`.

Build and start:

~~~bash
docker compose --env-file compose.env up --build -d
docker compose --env-file compose.env ps
~~~

Verify both health endpoints:

~~~bash
curl -sS http://127.0.0.1:8000/api/v1/health
curl -sS http://127.0.0.1:8080/healthz
~~~

Open <http://127.0.0.1:8080/>. For OAuth, add that exact URL to Supabase Site URL and Redirect
URLs. Google still redirects to the Supabase callback URL described in [setup.md](setup.md).

Useful lifecycle commands:

~~~bash
docker compose --env-file compose.env logs -f
docker compose --env-file compose.env restart backend
docker compose --env-file compose.env down
~~~

`down` removes the local containers and network, not the built images or application data in
Supabase.

## 3. Build images independently

~~~bash
docker build -t truthscope-backend:local backend
docker build -t truthscope-frontend:local frontend
~~~

Do not copy `backend/.env` or `frontend/config.js` into either image. Their Docker ignore rules
remove those files from the build context. Frontend `config.js` is generated in `/tmp` from public
environment variables whenever its container starts, allowing one image to be reused across
environments.

## 4. Recommended AWS shape

~~~mermaid
flowchart LR
    User[Browser]
    FrontALB[Frontend HTTPS endpoint]
    Front[ECS Fargate frontend service]
    BackALB[Backend HTTPS endpoint]
    Back[ECS Fargate backend service]
    ECR[(Two private ECR repositories)]
    Secrets[AWS Secrets Manager]
    External[Supabase, Gonka, Brave, public web]

    User --> FrontALB --> Front
    User --> BackALB --> Back
    ECR --> Front
    ECR --> Back
    Secrets --> Back
    Back --> External
~~~

Use:

- two private Amazon ECR repositories;
- two Amazon ECS services using Fargate;
- one public HTTPS endpoint for each service;
- AWS Secrets Manager or encrypted Systems Manager Parameter Store values for backend secrets;
- CloudWatch Logs for container output; and
- ACM certificates and Route 53 records when using custom domains.

AWS documents the standard [ECS Fargate service workflow](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/getting-started-fargate.html)
and a newer [ECS Express Mode workflow](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-getting-started.html).
Standard ECS/Fargate is the safer current choice for TruthScope because the synchronous API needs
explicit control over Application Load Balancer settings.

### Long-request requirement

An Application Load Balancer has a default idle timeout of 60 seconds. TruthScope live verification
can take several minutes when provider retries occur. Set the backend ALB
`idle_timeout.timeout_seconds` above the worst permitted request duration; `400` seconds matches the
current six-minute client smoke-test allowance with a small margin. AWS documents the attribute and
default under [Application Load Balancer attributes](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/application-load-balancers.html#load-balancer-attributes).

This is a prototype accommodation. A production design should submit a job, return `202 Accepted`,
and expose polling or server-sent progress instead of keeping one HTTP connection open.

## 5. Push both images to Amazon ECR

Install and configure AWS CLI first. Choose the account and region deliberately. AWS identifies
`ap-southeast-5` as Asia Pacific (Malaysia), and ECS on Fargate supports Linux containers there.
This Region requires account opt-in, so enable it first or use the team's existing selected Region.
See the official [AWS Region table](https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-regions.html)
and [Fargate Region support](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate-Regions.html).

~~~bash
export AWS_REGION=ap-southeast-5
export AWS_ACCOUNT_ID=123456789012
export ECR_REGISTRY="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
export IMAGE_TAG="$(git rev-parse --short HEAD)"

aws ecr create-repository \
  --repository-name truthscope-backend \
  --image-scanning-configuration scanOnPush=true \
  --region "$AWS_REGION"

aws ecr create-repository \
  --repository-name truthscope-frontend \
  --image-scanning-configuration scanOnPush=true \
  --region "$AWS_REGION"

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

docker build -t "$ECR_REGISTRY/truthscope-backend:$IMAGE_TAG" backend
docker build -t "$ECR_REGISTRY/truthscope-frontend:$IMAGE_TAG" frontend

docker push "$ECR_REGISTRY/truthscope-backend:$IMAGE_TAG"
docker push "$ECR_REGISTRY/truthscope-frontend:$IMAGE_TAG"
~~~

Use immutable Git-derived tags for deployments instead of relying on `latest`. The login, tag, and
push sequence follows the official [Amazon ECR image push guide](https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html).

## 6. Create the backend ECS service

Configure the backend container:

- image: `<account>.dkr.ecr.<region>.amazonaws.com/truthscope-backend:<tag>`;
- container port: `8000`;
- target-group health path: `/api/v1/health`;
- initial task size: 1 vCPU and 2 GB memory, then tune from observed utilization;
- desired count: one for a demo, two or more for availability;
- public environment: `APP_ENV=production`, `LOG_LEVEL=INFO`, exact
  `CORS_ALLOWED_ORIGINS`, model IDs, and non-secret timeout settings;
- secret environment: `GONKA_API_KEY`, `BRAVE_SEARCH_API_KEY`, and `SUPABASE_KEY`; and
- ordinary environment: `SUPABASE_URL` and provider base URLs.

Do not paste secret values into the task definition. ECS task-definition environment values are
visible to principals allowed to describe the definition. Reference Secrets Manager ARNs through
the container `secrets` field and grant the task execution role access. See AWS guidance for
[passing Secrets Manager values to ECS](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-secrets-manager.html).

The backend requires outbound HTTPS access to Supabase, Gonka, Brave Search, and public evidence
pages. If tasks use private subnets, configure a NAT gateway or another reviewed egress path.

## 7. Create the frontend ECS service

Deploy the backend first and copy its public HTTPS origin. Then configure the frontend container:

- image: `<account>.dkr.ecr.<region>.amazonaws.com/truthscope-frontend:<tag>`;
- container port: `8080`;
- target-group health path: `/healthz`;
- `API_BASE_URL=https://api.example.com/api/v1`;
- `OAUTH_REDIRECT_URL=https://app.example.com/`;
- `SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co`; and
- `SUPABASE_PUBLISHABLE_KEY=<public publishable or anon key>`.

These frontend values are intentionally public: browsers receive them in `config.js`. Never add
`SUPABASE_KEY`, `service_role`, Gonka, Brave, or Google client secrets to the frontend service.

## 8. Align public URLs

Before the first login, make these values agree exactly:

| Location | Value example |
|---|---|
| Frontend `OAUTH_REDIRECT_URL` | `https://app.example.com/` |
| Supabase Site URL | `https://app.example.com/` |
| Supabase additional Redirect URL | `https://app.example.com/` |
| Google authorized JavaScript origin | `https://app.example.com` |
| Google authorized redirect URI | `https://PROJECT.supabase.co/auth/v1/callback` |
| Backend `CORS_ALLOWED_ORIGINS` | `https://app.example.com` |
| Frontend `API_BASE_URL` | `https://api.example.com/api/v1` |

Use HTTPS for deployed origins. Do not add paths or a trailing slash to CORS origins.

## 9. Deployment validation

After ECS reports both target groups healthy:

~~~bash
curl -sS https://api.example.com/api/v1/health
curl -sS https://app.example.com/healthz
curl -sS https://app.example.com/config.js
~~~

Then complete this browser smoke test:

1. Load the frontend over HTTPS and confirm there are no browser-console errors.
2. Sign in with Google and return to the frontend origin.
3. Submit one known text claim and wait for a final result.
4. Confirm two verifier analyses, judge, bias audit, evidence links, and inference metadata.
5. Open History and reload the saved result.
6. Inspect CloudWatch Logs without printing tokens or secret environment values.

## 10. Operational cautions

- Supabase remains the persistent data layer; ECS tasks are disposable.
- Changing an injected ECS secret does not update running tasks automatically. Force a new service
  deployment after rotation, as described in the AWS Secrets Manager/ECS documentation.
- Keep backend desired count at one until concurrent Gonka capacity is tested; scale based on
  provider limits as well as CPU.
- Restrict backend ALB inbound traffic to HTTPS and do not expose Uvicorn's port directly.
- Set an AWS Budget and billing alerts before leaving demo resources running.
- Delete unused ECS services, load balancers, NAT gateways, ECR images, and log retention after the
  event; several of these resources incur charges while provisioned.

Local development details: [setup.md](setup.md). System behavior: [architecture.md](architecture.md).
API contract: [api.md](api.md).
