# AWS + Cloudflare deployment

This deployment keeps the browser on the HTTPS Cloudflare Pages origin and
proxies `/api/*` to the AWS ALB. The ALB listener only forwards requests that
contain a generated origin header stored as a Cloudflare Pages secret.

AWS resources:

- ECS Fargate (one AgentScope task)
- RDS PostgreSQL 17 with one-day backups (the account's free-tier limit)
- ElastiCache Valkey with in-transit and at-rest encryption
- private, versioned S3 object storage
- encrypted EFS for workspaces and the single-replica local Qdrant store
- ALB, CloudWatch Logs, ECR, Secrets Manager, and a dedicated VPC

Run from PowerShell after authenticating the `agentscope-deploy` AWS profile and
Wrangler:

```powershell
.\deploy.ps1
```

For a first deployment, the script keeps ECS at zero until the image and
database migration are ready. On later deployments it preserves the running
service while provisioning, uploading secrets, pushing the verified image, and
running the migration; it then replaces the ECS task, deploys Pages, and retries
verification of `/chat` plus `/api/health` while Cloudflare propagates.

Because this setup deliberately uses provider-default links and no custom
domain, the Cloudflare-to-ALB hop uses HTTP. The ALB rejects requests unless the
generated `X-Origin-Verify` secret matches. Add a domain and ACM certificate if
end-to-end TLS is required.

Terraform state and generated deployment results remain local and are ignored
by Git. Treat the state file as sensitive because it contains the RDS password.

