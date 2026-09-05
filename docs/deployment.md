# TruthScope container and AWS deployment

The validated AWS hackathon deployment uses private ECR, one EC2 host, direct hardened Docker
containers, and two outbound Cloudflare Quick Tunnels. Its reproducible commands and observed
failures are recorded in
[Deployment Part 1](deployment/deployment-part-1.md). The no-domain HTTPS and OAuth continuation is
recorded in [Deployment Part 2](deployment/deployment-part-2-quick-tunnels.md). This document
describes local Compose and the longer-term ECS/Fargate deployment alternative.

TruthScope ships as two independent container images:

| Image | Runtime | Port | Health check |
|---|---|---:|---|
| `truthscope-backend` | FastAPI/Uvicorn | 8000 | `/api/v1/health` |
| `truthscope-frontend` | Nginx static site | 8080 | `/healthz` |

The local Compose stack is the fastest way to validate both images. For a longer-lived AWS target,
each image can become its own ECS service after verification jobs are moved out of process so the
backend can scale and restart safely.

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
URLs. Google and GitHub still redirect to the Supabase callback URL described in
[setup.md](setup.md).

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
Standard ECS/Fargate is the safer current choice for TruthScope because it gives explicit control
over task count, networking, health checks, logs, and Application Load Balancer settings.

### Long-request requirement

An Application Load Balancer has a default idle timeout of 60 seconds. The frontend now starts a
short request and polls a process-local verification job, so its normal flow does not hold one HTTP
connection for the full model runtime. The backward-compatible synchronous endpoint can still take
several minutes; raise <code>idle_timeout.timeout_seconds</code> only if clients use that endpoint.
AWS documents the attribute and default under [Application Load Balancer attributes](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/application-load-balancers.html#load-balancer-attributes).

Run exactly one backend worker/task while jobs remain process-local. Multiple replicas can route a
poll to a process that does not own the job. A shared durable job store/queue is required before
horizontal scaling.

The current prototype already submits a job, returns `202 Accepted`, and polls job state. A
production design must move the process-local registry and background tasks to durable shared
infrastructure before enabling multiple backend replicas. Per-node live progress would additionally
require explicit graph telemetry.

## 5. Push both images to Amazon ECR

Install and configure AWS CLI first. Choose the account and Region deliberately. The validated EC2
deployment uses <code>us-east-1</code>; its Availability Zone <code>us-east-1c</code> is not a valid
CLI Region value. A team may choose another enabled Region, but every ECR, ECS, and registry value
must then use that same Region.
See the official [AWS Region table](https://docs.aws.amazon.com/global-infrastructure/latest/regions/aws-regions.html)
and [Fargate Region support](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate-Regions.html).

~~~bash
export AWS_REGION=us-east-1
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

docker build --pull --no-cache -t truthscope-backend:local backend
docker build --pull --no-cache -t truthscope-frontend:local frontend

docker tag truthscope-backend:local \
  "$ECR_REGISTRY/truthscope-backend:$IMAGE_TAG"
docker tag truthscope-frontend:local \
  "$ECR_REGISTRY/truthscope-frontend:$IMAGE_TAG"

docker push "$ECR_REGISTRY/truthscope-backend:$IMAGE_TAG"
docker push "$ECR_REGISTRY/truthscope-frontend:$IMAGE_TAG"
~~~

Build before tagging: assigning a new remote tag to an old local image deploys old code under a new
name. Inspect the built images before pushing, and use immutable release tags instead of
<code>latest</code>. When rebuilding a corrected image from the same commit, use a new suffix such as
<code>abc1234-r2</code> rather than silently replacing the first artifact. The complete guarded
release procedure is in [Deployment Part 1](deployment/deployment-part-1.md#12-deploy-a-later-image).
The login, tag, and push sequence follows the official
[Amazon ECR image push guide](https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html).

## 6. Create the backend ECS service

Configure the backend container:

- image: `<account>.dkr.ecr.<region>.amazonaws.com/truthscope-backend:<tag>`;
- container port: `8000`;
- target-group health path: `/api/v1/health`;
- initial task size: 1 vCPU and 2 GB memory, then tune from observed utilization;
- desired count: exactly one while verification jobs remain process-local;
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
`SUPABASE_KEY`, `service_role`, Gonka, Brave, Google, or GitHub client secrets to frontend service.

## 8. Align public URLs

Before the first login, make these values agree exactly:

| Location | Value example |
|---|---|
| Frontend `OAUTH_REDIRECT_URL` | `https://app.example.com/` |
| Supabase Site URL | `https://app.example.com/` |
| Supabase additional Redirect URL | `https://app.example.com/` |
| Google authorized JavaScript origin | `https://app.example.com` |
| Google authorized redirect URI | `https://PROJECT.supabase.co/auth/v1/callback` |
| GitHub OAuth App homepage | `https://app.example.com/` |
| GitHub authorization callback URL | `https://PROJECT.supabase.co/auth/v1/callback` |
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
2. Sign in with Google and GitHub separately; confirm both return to frontend origin.
3. Submit one known text claim, switch UI language while it runs, and confirm controls respond.
4. Refresh during the run and confirm polling resumes for the same job.
5. Confirm two verifier analyses, judge, bias audit, evidence links, and inference metadata.
6. Open History and reload the saved result.
7. Inspect CloudWatch Logs without printing tokens or secret environment values.

## 10. Operational cautions

- Supabase remains the persistent data layer; ECS tasks are disposable.
- Changing an injected ECS secret does not update running tasks automatically. Force a new service
  deployment after rotation, as described in the AWS Secrets Manager/ECS documentation.
- Keep backend desired count and Uvicorn worker count at one while jobs remain process-local.
  Introduce a durable shared job store/queue before horizontal scaling, then test Gonka capacity
  and scale against provider limits as well as CPU.
- Restrict backend ALB inbound traffic to HTTPS and do not expose Uvicorn's port directly.
- Set an AWS Budget and billing alerts before leaving demo resources running.
- Delete unused ECS services, load balancers, NAT gateways, ECR images, and log retention after the
  event; several of these resources incur charges while provisioned.

Local development details: [setup.md](setup.md). System behavior: [architecture.md](architecture.md).
API contract: [api.md](api.md).
