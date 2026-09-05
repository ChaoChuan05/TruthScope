# TruthScope deployment — Part 1: Docker images on Amazon EC2

Status: completed prototype deployment on 4 September 2026.

This runbook records the first working TruthScope cloud deployment. It is intended for rebuilding,
debugging, or handing over the environment without relying on chat history.

The source inputs were:

- the successful terminal transcript captured during this deployment;
- the [shared AWS planning conversation](https://chatgpt.com/share/6a9ad4fd-5a4c-83ec-bc84-66057d4afcfb);
  and
- the repository's container definitions and current architecture.

The shared conversation considered copying the repository and building on EC2, Docker Compose,
Cloudflare Tunnel, and ECR. The path actually completed was **local build → private ECR → EC2 pull
→ direct hardened Docker containers**. This document follows that observed path.

## 1. Completed result

| Item | Deployed state |
|---|---|
| AWS Region | US East (N. Virginia), `us-east-1` |
| Availability Zone | `us-east-1c` |
| Compute | One `t3.micro` EC2 instance |
| Operating system | Ubuntu 26.04 LTS, x86-64 |
| Registry | Two private Amazon ECR repositories |
| Backend | FastAPI/Uvicorn container on host port 8000 |
| Frontend | Rootless Nginx container on host port 8080 |
| Persistence | External Supabase integration |
| Container restart | `unless-stopped` |
| Network access | Ports 8000 and 8080 restricted to operator IP |
| First recorded tag | Git commit `5ca3569` |
| Backend health | `/api/v1/health` returned configured providers and persistence |
| Frontend health | `/healthz` returned `ok` |

AWS account IDs, instance IDs, public addresses, Security Group IDs, Supabase values, and all
secrets are intentionally omitted. Resolve current values from AWS and local configuration instead
of copying expired identifiers from an old terminal log.

## 2. Runtime architecture

~~~mermaid
flowchart LR
    Developer[Developer workstation]
    ECR[(Private ECR repositories)]
    Role[EC2 instance role<br/>ECR pull only]
    EC2[EC2 t3.micro<br/>Ubuntu x86-64]
    Front[Frontend container<br/>Nginx :8080]
    Back[Backend container<br/>FastAPI :8000]
    External[Supabase, Gonka,<br/>Brave, public evidence]
    Browser[Operator browser]

    Developer -->|build and push Git tag| ECR
    Role --> EC2
    ECR -->|authenticated pull| EC2
    EC2 --> Front
    EC2 --> Back
    Browser -->|HTTP, source IP restricted| Front
    Browser -->|HTTP, source IP restricted| Back
    Back -->|outbound HTTPS| External
~~~

No source repository is required on EC2. The images contain application code. EC2 requires only:

- Docker;
- AWS CLI for ECR authentication;
- the attached ECR pull role;
- one backend secret environment file; and
- one frontend public environment file.

Compose remains useful locally, but this first AWS deployment used direct `docker run` commands.

## 3. Security and cost guardrails

Before deployment:

- create and confirm an AWS Budget notification appropriate for the hackathon;
- keep SSH port 22 restricted to **My IP**;
- use an EC2 instance role for ECR pulls instead of access keys on the server;
- use an IAM or IAM Identity Center identity for workstation access;
- never use root credentials for normal deployment work;
- never add Gonka, Brave, backend Supabase, or OAuth secrets to an image;
- keep backend environment files readable only by the EC2 user; and
- use Git-derived image tags rather than `latest`.

The first workstation login was recorded as an AWS root identity. Do not repeat that pattern.
Replace it with a least-privilege IAM/Identity Center deployment identity before the next push. AWS
recommends temporary credentials and explicitly warns against routine root use in its
[root-user best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/root-user-best-practices.html).

The EC2 instance uses a public IPv4 address. Current charges and free-tier treatment can change;
review [Amazon VPC public IPv4 pricing](https://aws.amazon.com/vpc/pricing/) and the Billing console.
A normal stop can also assign a different public IPv4 address when the instance starts again, while
EBS storage persists and may continue incurring charges. See
[EC2 stop/start behavior](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/how-ec2-instance-stop-start-works.html).

## 4. One-time AWS preparation

### 4.1 Region and architecture

The EC2 Availability Zone is `us-east-1c`; its Region is `us-east-1`. AWS CLI commands accept the
Region, not the Availability Zone.

The instance architecture is x86-64, matching the images built on the developer workstation. Check
before future deployments:

~~~bash
uname -m
docker image inspect truthscope-backend:local --format '{{.Architecture}}'
~~~

Expected EC2 output is `x86_64`; expected image architecture is `amd64`.

### 4.2 EC2 instance role

Attach an EC2-trusted IAM role with ECR pull-only permission to the instance. The AWS-managed
`AmazonEC2ContainerRegistryPullOnly` policy is sufficient for pulling these private images. Do not
store workstation access keys on EC2. AWS CLI automatically reads temporary credentials from the
attached instance profile, as described in the
[EC2 IAM role documentation](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_use_switch-role-ec2.html).

Verify from EC2 after AWS CLI is installed:

~~~bash
aws sts get-caller-identity
~~~

The ARN must contain `assumed-role`. It must not identify the account root user.

### 4.3 Security Group baseline

The working instance had one application Security Group attached. Its inbound rules were:

| Protocol | Port | Source | Purpose |
|---|---:|---|---|
| TCP | 22 | Operator public IP `/32` | SSH |
| TCP | 8000 | Operator public IP `/32` | Temporary backend test |
| TCP | 8080 | Operator public IP `/32` | Temporary frontend test |

Select **My IP** when adding test rules. Do not select another Security Group as the source and do
not use `0.0.0.0/0` for SSH. Security Group changes apply to associated resources; see the official
[EC2 rule-editing procedure](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/changing-security-group.html).

The console may show rules from different groups in one instance panel. Confirm actual attachment
under **Actions → Security → Change security groups** before deleting or detaching anything. Never
remove the only group containing the SSH rule during an active remote setup.

## 5. Workstation: authenticate AWS CLI

Install current AWS CLI v2 on Linux/WSL:

~~~bash
curl -fsSL https://awscli.amazonaws.com/v2/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"
aws --version
~~~

The official installer and alternatives are documented in the
[AWS CLI installation guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html).

Use short-term browser authentication with an IAM or federated console identity:

~~~bash
aws login
aws configure set region us-east-1
aws configure set output json
aws configure set cli_pager ""
export AWS_PAGER=""
aws sts get-caller-identity
~~~

`aws login` requires AWS CLI 2.32.0 or later and an appropriately permitted identity. See
[AWS local-development login](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sign-in.html).
If the account uses IAM Identity Center, use `aws configure sso` and `aws sso login` instead.

Define reusable values from repository root:

~~~bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export ECR_REGISTRY="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
export IMAGE_TAG="$(git rev-parse --short HEAD)"

printf 'Region: %s\nRegistry: %s\nTag: %s\n' \
  "$AWS_REGION" "$ECR_REGISTRY" "$IMAGE_TAG"
~~~

Do not set `AWS_REGION=us-east-1c`. Do not leave `IMAGE_TAG=YOUR_IMAGE_TAG` as a literal placeholder.

## 6. Workstation: create ECR and push images

Create the two repositories once:

~~~bash
aws ecr create-repository \
  --repository-name truthscope-backend \
  --image-scanning-configuration scanOnPush=true \
  --region "$AWS_REGION"

aws ecr create-repository \
  --repository-name truthscope-frontend \
  --image-scanning-configuration scanOnPush=true \
  --region "$AWS_REGION"
~~~

`RepositoryAlreadyExistsException` is expected when repeating this step. If output opens at
`(END)`, press `q`; disabling `cli_pager` above prevents recurrence.

Authenticate Docker, then build, tag, and push:

~~~bash
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

docker build -t truthscope-backend:local backend
docker build -t truthscope-frontend:local frontend

docker tag \
  truthscope-backend:local \
  "$ECR_REGISTRY/truthscope-backend:$IMAGE_TAG"

docker tag \
  truthscope-frontend:local \
  "$ECR_REGISTRY/truthscope-frontend:$IMAGE_TAG"

docker push "$ECR_REGISTRY/truthscope-backend:$IMAGE_TAG"
docker push "$ECR_REGISTRY/truthscope-frontend:$IMAGE_TAG"
~~~

The process follows the official
[private ECR push workflow](https://docs.aws.amazon.com/AmazonECR/latest/userguide/docker-push-ecr-image.html).
The warning that Docker stored the short-lived registry credential in `~/.docker/config.json` does
not mean the push failed. Configure the Amazon ECR Docker credential helper before longer-term use.

Verify both tagged images:

~~~bash
aws ecr describe-images \
  --repository-name truthscope-backend \
  --region "$AWS_REGION" \
  --query 'imageDetails[].imageTags'

aws ecr describe-images \
  --repository-name truthscope-frontend \
  --region "$AWS_REGION" \
  --query 'imageDetails[].imageTags'
~~~

## 7. EC2: install AWS CLI and pull images

Docker must already be installed and usable by the `ubuntu` user:

~~~bash
docker --version
docker run --rm hello-world
~~~

For a replacement host, use Docker's maintained
[Ubuntu installation procedure](https://docs.docker.com/engine/install/ubuntu/) and complete its
[Linux post-installation steps](https://docs.docker.com/engine/install/linux-postinstall). Do not
mix distribution Docker packages with Docker's official packages.

Install the AWS CLI system-wide:

~~~bash
sudo apt update
sudo apt install -y unzip

curl -fsSL https://awscli.amazonaws.com/v2/install.sh \
  | sudo bash -s -- --system

aws --version
aws sts get-caller-identity
~~~

Installing `unzip` is required by the official CLI installer. Do not run `aws login` or
`aws configure` on EC2; the attached instance role supplies temporary credentials.

Set deployment values on EC2. Copy the actual Git tag printed on the workstation:

~~~bash
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text)"
export ECR_REGISTRY="$AWS_ACCOUNT_ID.dkr.ecr.$AWS_REGION.amazonaws.com"
export IMAGE_TAG=<GIT_COMMIT_TAG>
~~~

Authenticate and pull:

~~~bash
aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

docker pull "$ECR_REGISTRY/truthscope-backend:$IMAGE_TAG"
docker pull "$ECR_REGISTRY/truthscope-frontend:$IMAGE_TAG"
~~~

Retagging keeps the original local container commands simple:

~~~bash
docker tag \
  "$ECR_REGISTRY/truthscope-backend:$IMAGE_TAG" \
  truthscope-backend:local

docker tag \
  "$ECR_REGISTRY/truthscope-frontend:$IMAGE_TAG" \
  truthscope-frontend:local
~~~

## 8. EC2: create runtime configuration

Create a configuration directory without cloning application source:

~~~bash
mkdir -p "$HOME/truthscope"
cd "$HOME/truthscope"
~~~

### 8.1 Backend secrets

Create `backend.env`:

~~~dotenv
APP_ENV=production
LOG_LEVEL=INFO
GONKA_API_KEY=<SECRET>
BRAVE_SEARCH_API_KEY=<SECRET>
SUPABASE_URL=https://<PROJECT_REF>.supabase.co
SUPABASE_KEY=<BACKEND_SECRET_KEY>
CORS_ALLOWED_ORIGINS=http://<EC2_PUBLIC_IP>:8080
~~~

The full backend configuration remains documented in [setup.md](../setup.md). After creation:

~~~bash
chmod 600 "$HOME/truthscope/backend.env"
~~~

Never print or commit this file.

### 8.2 Frontend public values

The frontend source uses `config.js` locally. The container intentionally uses runtime variables
and generates `/tmp/truthscope-config.js` when it starts. Therefore EC2 needs a Docker env file even
though the source frontend does not use `.env`.

Create `frontend.env` using Docker `KEY=value` syntax:

~~~dotenv
API_BASE_URL=http://<EC2_PUBLIC_IP>:8000/api/v1
OAUTH_REDIRECT_URL=http://<EC2_PUBLIC_IP>:8080/
SUPABASE_URL=https://<PROJECT_REF>.supabase.co
SUPABASE_PUBLISHABLE_KEY=<PUBLIC_PUBLISHABLE_OR_ANON_KEY>
~~~

These four values are browser-visible. Do not add `SUPABASE_KEY`, `service_role`, Gonka, Brave, or
Google client secrets.

An env file is not a JavaScript object. Do not use colons, quotes, trailing commas, spaces around
`=`, or Markdown links such as `[URL](URL)`. To avoid pasted-link corruption, generate the two
application URLs safely:

~~~bash
export APP_SCHEME=http
export EC2_PUBLIC_IP=<CURRENT_PUBLIC_IP>

printf 'API_BASE_URL=%s://%s:8000/api/v1\n' \
  "$APP_SCHEME" "$EC2_PUBLIC_IP" > frontend.env

printf 'OAUTH_REDIRECT_URL=%s://%s:8080/\n' \
  "$APP_SCHEME" "$EC2_PUBLIC_IP" >> frontend.env

read -r -p 'Supabase URL: ' supabaseUrl
printf 'SUPABASE_URL=%s\n' "$supabaseUrl" >> frontend.env

read -r -p 'Supabase publishable key: ' supabaseKey
printf 'SUPABASE_PUBLISHABLE_KEY=%s\n' "$supabaseKey" >> frontend.env
~~~

Verify names without exposing values:

~~~bash
cut -d= -f1 frontend.env
~~~

Expected:

~~~text
API_BASE_URL
OAUTH_REDIRECT_URL
SUPABASE_URL
SUPABASE_PUBLISHABLE_KEY
~~~

## 9. EC2: run hardened containers

Start backend:

~~~bash
docker run -d \
  --name truthscope-backend \
  --restart unless-stopped \
  --env-file "$HOME/truthscope/backend.env" \
  --read-only \
  --tmpfs /tmp:size=64m,mode=1777 \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  -p 8000:8000 \
  truthscope-backend:local
~~~

Start frontend:

~~~bash
docker run -d \
  --name truthscope-frontend \
  --restart unless-stopped \
  --env-file "$HOME/truthscope/frontend.env" \
  --read-only \
  --tmpfs /tmp:size=32m,mode=1777 \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  -p 8080:8080 \
  truthscope-frontend:local
~~~

These commands run both processes non-root, make their image filesystems read-only, provide bounded
temporary storage, drop Linux capabilities, and disable privilege escalation.

## 10. Validate the deployment

On EC2:

~~~bash
docker ps
curl -sS http://127.0.0.1:8000/api/v1/health
curl -sS http://127.0.0.1:8080/healthz
~~~

Expected container state is `Up ... (healthy)`. A fully configured backend returns a shape like:

~~~json
{
  "status": "ok",
  "gonkaConfigured": true,
  "searchConfigured": true,
  "persistenceBackend": "external"
}
~~~

Frontend returns:

~~~text
ok
~~~

After ports 8000 and 8080 are allowed from the operator's current IP, test from the workstation:

~~~bash
curl -sS --max-time 10 http://<EC2_PUBLIC_IP>:8000/api/v1/health
curl -sS --max-time 10 http://<EC2_PUBLIC_IP>:8080/healthz
~~~

Open `http://<EC2_PUBLIC_IP>:8080` in the browser. Successful loading from the allowed workstation
completes Part 1.

## 11. Failures encountered and fixes

| Symptom | Cause | Fix |
|---|---|---|
| AWS output stops at `(END)` | AWS CLI pager | Press `q`; set `cli_pager` to empty |
| Sign-in URL contains `us-east-1c` | Availability Zone used as Region | Set Region to `us-east-1` |
| `aws: command not found` on EC2 | CLI not installed | Install AWS CLI v2 |
| CLI installer reports missing dependency | `unzip` absent | `sudo apt install -y unzip` |
| ECR says `YOUR_IMAGE_TAG` not found | Placeholder used literally | Export actual Git tag |
| Docker login warns about unencrypted config | No credential helper | Login still worked; add helper later |
| `frontend.env: no such file` | Runtime file was not created/saved | Create it under `$HOME/truthscope` |
| Docker env variable contains whitespace | JavaScript object pasted into env file | Use strict `KEY=value` lines |
| Frontend repeatedly restarts | Startup URL validation rejected malformed value | Inspect logs and rebuild env file |
| Editing env does not fix existing container | Docker captured env at creation | Remove and recreate that container |
| Local frontend URL uses `127.0.0.1` | Browser would call visitor's own machine | Use EC2 public origin temporarily |
| Public request times out | Security Group does not allow client IP | Add ports 8000/8080 from **My IP** |

Useful diagnostics:

~~~bash
docker ps -a
docker logs --tail=100 truthscope-backend
docker logs --tail=100 truthscope-frontend

docker inspect \
  --format '{{range .Config.Env}}{{println .}}{{end}}' \
  truthscope-frontend \
  | cut -d= -f1
~~~

To apply changed runtime variables, remove only the disposable container and rerun its documented
`docker run` command. Removing a container does not remove its image or Supabase data:

~~~bash
docker rm -f truthscope-frontend
~~~

## 12. Deploy a later image

On the workstation, repeat authentication, build, tag, and push with a new Git-derived tag. On EC2:

~~~bash
export IMAGE_TAG=<NEW_GIT_COMMIT_TAG>

aws ecr get-login-password --region "$AWS_REGION" \
  | docker login --username AWS --password-stdin "$ECR_REGISTRY"

docker pull "$ECR_REGISTRY/truthscope-backend:$IMAGE_TAG"
docker pull "$ECR_REGISTRY/truthscope-frontend:$IMAGE_TAG"

docker tag \
  "$ECR_REGISTRY/truthscope-backend:$IMAGE_TAG" \
  truthscope-backend:local

docker tag \
  "$ECR_REGISTRY/truthscope-frontend:$IMAGE_TAG" \
  truthscope-frontend:local
~~~

Then recreate the two containers one at a time with the commands in section 9. For a hackathon
deployment, replace and validate the backend first, then the frontend. A later phase should automate
this release process.

## 13. Part 1 limitations and Part 2 entry point

Part 1 proves image distribution, EC2 execution, provider configuration, and network reachability.
It is not yet a production-ready public endpoint:

- traffic is HTTP rather than HTTPS;
- the frontend and backend expose ports 8080 and 8000 directly;
- access is limited to the operator's changing public IP;
- the EC2 public address can change after stop/start;
- Google OAuth redirects are not finalized for a public HTTPS origin;
- backend secrets live in an EC2 file rather than AWS Secrets Manager;
- no reverse proxy, Cloudflare Tunnel, domain, certificate, monitoring, or CI/CD is configured; and
- verification jobs survive browser refresh but not a backend container restart, and require one
  backend worker while the registry remains process-local.

The completed no-domain continuation uses two Cloudflare Quick Tunnels and is documented step by
step in [Deployment Part 2](deployment-part-2-quick-tunnels.md). Quick Tunnels are appropriate for
testing and a hackathon demonstration, not a stable production deployment.

For a longer-lived endpoint, choose one HTTPS approach:

1. Cloudflare Tunnel for a quick hackathon endpoint without public application ports; or
2. stable DNS plus a reviewed TLS reverse proxy/load balancer for a longer-lived deployment.

Then update these values together:

- frontend `API_BASE_URL`;
- frontend `OAUTH_REDIRECT_URL`;
- backend `CORS_ALLOWED_ORIGINS`;
- Supabase Site URL and Redirect URLs; and
- Google OAuth authorized origin and Supabase callback.

The target production-oriented alternatives remain documented in [deployment.md](../deployment.md).
System boundaries are documented in [architecture.md](../architecture.md).

## 14. End-of-event cleanup

Stopping EC2 preserves its EBS-backed disk but normally changes its public IP on the next start and
does not eliminate storage-related charges. Terminating deletes the instance; verify EBS deletion
settings first. At the end of the event, review:

- EC2 instances and attached EBS volumes;
- public IPv4 and Elastic IP allocations;
- ECR repositories and retained image tags;
- CloudWatch log groups;
- IAM roles and local-development sessions; and
- AWS Budgets and Cost Explorer.

Never terminate the instance until required environment values or other non-reproducible data have
been backed up securely.
