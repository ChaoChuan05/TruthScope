# TruthScope deployment — Part 2: public HTTPS with Cloudflare Quick Tunnels

Status: completed hackathon HTTPS tunnel path on 4 September 2026.

This runbook continues [Deployment Part 1](deployment-part-1.md). Part 1 builds the two images,
stores them in private Amazon ECR, pulls them onto EC2, and starts the backend and frontend
containers. Part 2 publishes those existing containers over temporary HTTPS without buying a
domain.

This path is suitable for testing and a short hackathon demonstration. Cloudflare explicitly
describes Quick Tunnels as development/testing infrastructure: the hostname is random, there is no
uptime SLA, concurrent requests are limited, and Server-Sent Events are unsupported. Use a named
tunnel with a controlled domain or another stable HTTPS endpoint for a persistent deployment. See
the official [Cloudflare Quick Tunnels documentation](https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/).

## 1. Result and request path

The completed setup runs four Docker containers on one EC2 instance:

| Container | Purpose | Local origin |
|---|---|---|
| `truthscope-backend` | FastAPI API | `http://127.0.0.1:8000` |
| `truthscope-frontend` | Nginx static frontend | `http://127.0.0.1:8080` |
| `truthscope-backend-tunnel` | Temporary public HTTPS route to the API | Random `trycloudflare.com` URL |
| `truthscope-frontend-tunnel` | Temporary public HTTPS route to the UI | Random `trycloudflare.com` URL |

~~~mermaid
flowchart LR
    Browser[User browser]
    FrontURL[Frontend Quick Tunnel<br/>temporary HTTPS URL]
    FrontTunnel[cloudflared container]
    Front[Frontend container<br/>Nginx :8080]
    BackURL[Backend Quick Tunnel<br/>temporary HTTPS URL]
    BackTunnel[cloudflared container]
    Back[Backend container<br/>FastAPI :8000]
    Supabase[Supabase Auth and data]
    Providers[Gonka, Brave, evidence sites]

    Browser -->|page and OAuth return| FrontURL
    FrontURL --> FrontTunnel --> Front
    Browser -->|API requests| BackURL
    BackURL --> BackTunnel --> Back
    Browser -->|Google OAuth through Supabase| Supabase
    Back --> Supabase
    Back --> Providers
~~~

`cloudflared` uses outbound connections, so ports 8000 and 8080 do not need to remain publicly
allowed in the EC2 Security Group after the tunnels are validated.

## 2. Important limitations

Read these before continuing:

- No domain or Cloudflare account is required for a Quick Tunnel.
- Each tunnel receives a random `https://...trycloudflare.com` URL.
- Recreating or restarting a tunnel container can produce a new URL.
- When either URL changes, update the EC2 env files, recreate the application containers, and
  update the Supabase/Google allowlists again.
- Anyone who knows the backend tunnel URL can reach the public API. UI login controls do not by
  themselves protect a separately exposed API endpoint.
- Use this setup only for a controlled demo window. Stop both tunnel containers afterward.
- Do not paste Markdown links such as `[https://example](https://example)` into a terminal or env
  file. Paste only the plain URL.

## 3. Prerequisites

Complete Part 1 first. On EC2, verify that both application containers are healthy:

~~~bash
docker ps
curl -sS http://127.0.0.1:8000/api/v1/health
curl -sS http://127.0.0.1:8080/healthz
~~~

Expected backend shape:

~~~json
{
  "status": "ok",
  "gonkaConfigured": true,
  "searchConfigured": true,
  "persistenceBackend": "external"
}
~~~

Expected frontend response:

~~~text
ok
~~~

Also confirm:

- EC2 can make outbound HTTPS requests;
- `~/truthscope/backend.env` exists and has mode `600`;
- `~/truthscope/frontend.env` exists;
- Google is enabled under Supabase **Authentication → Sign In / Providers**; and
- an Owner or Administrator is available for Supabase and Google project settings.

Do not print the backend env file because it contains secrets.

## 4. Start the backend Quick Tunnel

Run on EC2:

~~~bash
docker run -d \
  --name truthscope-backend-tunnel \
  --restart unless-stopped \
  --network host \
  cloudflare/cloudflared:latest \
  tunnel --no-autoupdate --url http://127.0.0.1:8000
~~~

Docker downloads `cloudflare/cloudflared:latest` automatically when it is not present locally.
Host networking lets `cloudflared` reach the host-published application port through
`127.0.0.1`.

Wait several seconds and inspect the raw log:

~~~bash
docker logs truthscope-backend-tunnel --tail 100
~~~

Extract only the generated HTTPS URL:

~~~bash
docker logs truthscope-backend-tunnel 2>&1 \
  | grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' \
  | head -1
~~~

Record it temporarily as:

~~~text
https://BACKEND_RANDOM_NAME.trycloudflare.com
~~~

Do not add `/api/v1` when recording the origin. Test the API by adding the path:

~~~bash
curl -sS \
  https://BACKEND_RANDOM_NAME.trycloudflare.com/api/v1/health
~~~

Continue only after this returns the same health response as the localhost request.

## 5. Start the frontend Quick Tunnel

The existing frontend container can remain running while the tunnel starts:

~~~bash
docker run -d \
  --name truthscope-frontend-tunnel \
  --restart unless-stopped \
  --network host \
  cloudflare/cloudflared:latest \
  tunnel --no-autoupdate --url http://127.0.0.1:8080
~~~

Extract its URL:

~~~bash
docker logs truthscope-frontend-tunnel 2>&1 \
  | grep -Eo 'https://[a-zA-Z0-9.-]+\.trycloudflare\.com' \
  | head -1
~~~

Record it temporarily as:

~~~text
https://FRONTEND_RANDOM_NAME.trycloudflare.com
~~~

Check the public health endpoint:

~~~bash
curl -sS \
  https://FRONTEND_RANDOM_NAME.trycloudflare.com/healthz
~~~

Expected response: `ok`.

## 6. Connect the frontend to both public origins

Edit the frontend runtime file:

~~~bash
nano "$HOME/truthscope/frontend.env"
~~~

Set the two URL values. Preserve the existing public Supabase values:

~~~dotenv
API_BASE_URL=https://BACKEND_RANDOM_NAME.trycloudflare.com/api/v1
OAUTH_REDIRECT_URL=https://FRONTEND_RANDOM_NAME.trycloudflare.com/
SUPABASE_URL=https://PROJECT_REF.supabase.co
SUPABASE_PUBLISHABLE_KEY=PUBLIC_PUBLISHABLE_OR_ANON_KEY
~~~

Rules for this file:

- use `KEY=value`, not JavaScript object syntax;
- do not use quotes, colons, trailing commas, or spaces around `=`;
- `API_BASE_URL` includes `/api/v1`;
- `OAUTH_REDIRECT_URL` includes the final `/`; and
- only the publishable/anon Supabase key belongs in frontend configuration.

Save in Nano with `Ctrl+O`, `Enter`, then `Ctrl+X`.

## 7. Allow the frontend origin through backend CORS

Edit the protected backend runtime file:

~~~bash
nano "$HOME/truthscope/backend.env"
~~~

Set this exact origin:

~~~dotenv
CORS_ALLOWED_ORIGINS=https://FRONTEND_RANDOM_NAME.trycloudflare.com
~~~

Do not add `/api/v1`, another path, or a trailing `/` to a CORS origin. Keep every other backend
value unchanged, then restore restrictive permissions:

~~~bash
chmod 600 "$HOME/truthscope/backend.env"
~~~

## 8. Recreate the application containers

Docker captures environment values when a container is created. `docker restart` does not reload
an edited env file, so recreate the backend and frontend. The tunnel containers remain running and
keep their current URLs during this step.

Remove only the two disposable application containers:

~~~bash
docker rm -f truthscope-backend truthscope-frontend
~~~

Start the backend:

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

Start the frontend:

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

Wait for the health checks, then verify all four containers:

~~~bash
docker ps
curl -sS http://127.0.0.1:8000/api/v1/health
curl -sS http://127.0.0.1:8080/healthz
~~~

## 9. Configure Supabase OAuth redirect permission

The frontend supplies `OAUTH_REDIRECT_URL` to Supabase as the OAuth `redirectTo` value. Supabase
must explicitly allow it.

In the Supabase Dashboard:

1. Open the project.
2. Open **Authentication → URL Configuration**.
3. Under **Redirect URLs**, select **Add URL**.
4. Enter the exact frontend URL with its trailing slash:

   ~~~text
   https://FRONTEND_RANDOM_NAME.trycloudflare.com/
   ~~~

5. Save it and confirm the URL appears in the list.

An exact URL is preferable here because the application redirects to the root path. The Site URL
can remain the local-development URL when this Supabase project is shared and the frontend always
supplies `redirectTo`. For a dedicated deployment, its administrator may instead set Site URL to
the deployed frontend origin.

Supabase documents the allowlist behavior in
[Redirect URLs](https://supabase.com/docs/guides/auth/redirect-urls). A Developer role cannot
change project settings. If **Add URL** fails with `Forbidden` or `Unauthorized`, ask a Supabase
Owner or Administrator to perform this step; do not request their password or access token. See
[Supabase access control](https://supabase.com/docs/guides/platform/access-control).

## 10. Confirm Google OAuth configuration

In Google Auth Platform, open the Web application OAuth client used by Supabase:

1. Add the frontend origin under **Authorized JavaScript origins**:

   ~~~text
   https://FRONTEND_RANDOM_NAME.trycloudflare.com
   ~~~

   Do not add the trailing slash or a path.

2. Under **Authorized redirect URIs**, keep the Supabase callback shown on the Supabase Google
   provider page. Its shape is:

   ~~~text
   https://PROJECT_REF.supabase.co/auth/v1/callback
   ~~~

3. Save the OAuth client.

The Google redirect URI is the Supabase callback, not the frontend Quick Tunnel URL. Supabase then
returns the browser to the allowlisted frontend `redirectTo` URL. The official
[Supabase Google sign-in guide](https://supabase.com/docs/guides/auth/social-login/auth-google)
documents both settings.

If the OAuth client belongs to a teammate's Google Cloud project, that teammate must make this
change or grant an appropriate project role. Never exchange the Google client secret in chat.

## 11. Validate the public application

### 11.1 Public health checks

From a different machine or network:

~~~bash
curl -sS \
  https://BACKEND_RANDOM_NAME.trycloudflare.com/api/v1/health

curl -sS \
  https://FRONTEND_RANDOM_NAME.trycloudflare.com/healthz
~~~

### 11.2 Confirm generated frontend configuration

Open the frontend `config.js` without sharing its full output publicly:

~~~bash
curl -sS \
  https://FRONTEND_RANDOM_NAME.trycloudflare.com/config.js
~~~

Confirm it contains the current frontend and backend tunnel URLs. A publishable/anon Supabase key
is intentionally browser-visible; a `service_role`, secret key, Gonka key, or Brave key must never
appear there.

### 11.3 Check CORS

Run this with the real tunnel names:

~~~bash
curl -i -X OPTIONS \
  https://BACKEND_RANDOM_NAME.trycloudflare.com/api/v1/verifications \
  -H 'Origin: https://FRONTEND_RANDOM_NAME.trycloudflare.com' \
  -H 'Access-Control-Request-Method: POST' \
  -H 'Access-Control-Request-Headers: authorization,content-type'
~~~

The response must include an `access-control-allow-origin` header matching the frontend origin.

### 11.4 Browser smoke test

1. Open the frontend tunnel URL.
2. Open browser developer tools with `F12` and select **Console** and **Network**.
3. Sign in with Google.
4. Confirm Google returns to the frontend tunnel rather than `localhost`.
5. Submit a known text claim.
6. Wait for a complete or explicitly degraded result.
7. Confirm claims, evidence, two verifier analyses, judge, bias audit, score, and Gonka inference
   metadata are shown when available.
8. Open History and reload the persisted result.
9. Confirm another tester can repeat the flow from a different network.

## 12. Remove temporary public EC2 ports

Do this only after both tunnel URLs and the complete browser flow work.

In the AWS console:

1. Open **EC2 → Instances**.
2. Select the TruthScope instance.
3. Open the **Security** tab.
4. Click the Security Group ID actually attached to the instance.
5. Select **Edit inbound rules**.
6. Delete the inbound rules for TCP ports `8000` and `8080`.
7. Keep SSH TCP port `22` restricted to the operator's current IP `/32`.
8. Save the rules.

Do not detach the only Security Group and do not delete the SSH rule while connected remotely.
Cloudflare reaches the application through an outbound tunnel connection, so application-port
inbound rules are unnecessary.

Retest both Quick Tunnel URLs after saving. Direct requests to
`http://EC2_PUBLIC_IP:8000` and `http://EC2_PUBLIC_IP:8080` should no longer be reachable from the
Internet, while the HTTPS tunnel URLs should continue to work.

## 13. Watch logs in real time

The backend log is the most useful stream while another person submits a verification:

~~~bash
docker logs --follow --tail 50 --timestamps truthscope-backend
~~~

Press `Ctrl+C` to stop following without stopping the container.

Other individual streams:

~~~bash
docker logs --follow --tail 50 --timestamps truthscope-frontend
docker logs --follow --tail 50 --timestamps truthscope-backend-tunnel
docker logs --follow --tail 50 --timestamps truthscope-frontend-tunnel
~~~

To combine all four streams in one terminal:

~~~bash
trap 'kill $(jobs -p) 2>/dev/null' EXIT INT TERM

for containerName in \
  truthscope-backend \
  truthscope-frontend \
  truthscope-backend-tunnel \
  truthscope-frontend-tunnel
do
  docker logs --follow --tail 25 --timestamps "$containerName" 2>&1 \
    | sed -u "s/^/[$containerName] /" &
done

wait
~~~

Press `Ctrl+C` to stop the combined follower. For OAuth diagnosis, also inspect:

- browser **Developer Tools → Console and Network**; and
- Supabase Dashboard **Logs → Auth Logs**.

Do not paste logs containing access tokens, authorization headers, API keys, email addresses, or
other personal data into public issues or chat.

## 14. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Tunnel container starts but URL command prints nothing | Incorrect grep pattern such as a literal `\*` | Inspect raw `docker logs`; use the exact `grep -Eo` command above |
| `Conflict: container name is already in use` | Tunnel/application container already exists | Inspect it with `docker ps -a`; reuse it or deliberately remove only that named container |
| Quick Tunnel returns `502 Bad Gateway` | Target application container is down or not listening | Check localhost health and application logs |
| Frontend container repeatedly restarts | Malformed Docker env syntax or unsafe URL | Use plain `KEY=value`; inspect frontend logs |
| Frontend still calls the old API URL | Env file changed but container only restarted | Remove and recreate the frontend container |
| Browser reports a CORS error | Backend origin does not exactly match frontend tunnel origin | Correct `CORS_ALLOWED_ORIGINS`, then recreate backend |
| OAuth returns to `localhost` | Old frontend runtime config or unapproved redirect fell back to Site URL | Correct `OAUTH_REDIRECT_URL`, recreate frontend, and allowlist the tunnel URL |
| Supabase URL button fails with permission error | Current member is a Developer | Ask an Owner/Administrator to add the redirect URL |
| Google reports `redirect_uri_mismatch` | Wrong Google authorized redirect URI | Use the exact Supabase callback from its provider page |
| Frontend works locally but not publicly | Frontend tunnel stopped or URL changed | Inspect tunnel status/logs and repeat URL alignment |

General status commands:

~~~bash
docker ps -a
docker logs --tail 100 truthscope-backend
docker logs --tail 100 truthscope-frontend
docker logs --tail 100 truthscope-backend-tunnel
docker logs --tail 100 truthscope-frontend-tunnel
~~~

Show recent warning/error lines without printing environment files:

~~~bash
for containerName in \
  truthscope-backend \
  truthscope-frontend \
  truthscope-backend-tunnel \
  truthscope-frontend-tunnel
do
  printf '\n===== %s =====\n' "$containerName"
  docker logs --since 30m "$containerName" 2>&1 \
    | grep -Ei 'error|failed|exception|warning|timeout|forbidden' \
    | tail -50
done
~~~

## 15. Reboot and URL-change recovery

All four containers use `--restart unless-stopped`, but Quick Tunnel hostnames are not persistent.
After an EC2 reboot or any tunnel-container restart:

1. Run `docker ps` and confirm all four containers are up.
2. Extract the current backend and frontend URLs from their logs.
3. Compare them with `API_BASE_URL`, `OAUTH_REDIRECT_URL`, and backend CORS.
4. If either hostname changed, repeat sections 6–10.
5. Recreate both application containers so the new env values are loaded.
6. Repeat public health, CORS, OAuth, verification, and history tests.

Do not assume a bookmarked Quick Tunnel URL will keep working.

## 16. Stop public access after the demo

Stop the two tunnel containers:

~~~bash
docker stop truthscope-backend-tunnel truthscope-frontend-tunnel
~~~

This leaves the application containers running locally on EC2 but removes the Cloudflare public
routes. The Security Group should still have no public inbound rules for ports 8000 or 8080.

If the temporary tunnel containers are no longer needed, remove only those containers:

~~~bash
docker rm truthscope-backend-tunnel truthscope-frontend-tunnel
~~~

The application images, application containers, env files, and Supabase data remain intact.

## 17. Permanent next step

Replace Quick Tunnels before treating the application as a persistent service. Recommended choices:

1. acquire a domain and create a named, remotely managed Cloudflare Tunnel with stable frontend and
   backend hostnames; or
2. use stable DNS, ACM certificates, and reviewed AWS HTTPS endpoints.

A permanent rollout must also add managed backend secrets, rate limiting, monitoring, log
retention, backup/recovery procedures, and automated image deployment. The longer-term AWS design
is described in [deployment.md](../deployment.md).
