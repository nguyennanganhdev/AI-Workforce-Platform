# Landing page: Docker and VPS

This independent React + Vite service handles the public homepage and `/landing-assets/`.
The existing Platform frontend continues to handle `/login`, `/register`,
`/workforce/*`, `/assets/` and `/api/`. Signup links open the existing `/register` route.

Vite's asset base is `/landing-assets/`: development opens at
`http://127.0.0.1:5186/landing-assets/`. The production container serves
`dist/index.html` at both `/` and `/landing-assets/`; scripts, styles, fonts and
images use the isolated prefix. The runtime image only needs nginx.

## Build and verify

Run in `landing-page` with Docker Desktop using Linux containers:

```powershell
$release = 'vagents-landing:20261017-react-white'
docker build --pull -t $release .
$env:LANDING_IMAGE = $release
docker compose -p vagents-landing config --quiet
docker compose -p vagents-landing up -d --no-build
curl.exe --fail http://127.0.0.1:5180/
docker compose -p vagents-landing ps
```

The container runs as the nginx user on port `8080`, with a read-only filesystem
and temporary storage in `/tmp`. Host port `5180` binds only to `127.0.0.1`.
The build includes fonts from Fontsource; fonts are served
from the same origin. Hashed Vite assets have immutable caching; mascot
images have a one-day cache and the HTML is revalidated on every request.
Review the page on desktop and mobile, keyboard navigation, reduced motion,
the app CTA and generated asset URLs before deploying.

## Transfer the tested image

Use a unique release tag and an explicit SSH identity already verified for the
Platform host. Do not transfer `.env`, private keys, `node_modules`, or the repo.
The minimal upload is the image archive, `compose.yaml`, and `deploy/` files.

```powershell
docker save -o landing-image.tar $release
# Create a unique directory on the VPS, then upload only the listed files.
ssh -i <identity> -o BatchMode=yes -o StrictHostKeyChecking=yes root@103.238.234.172 'mkdir -p /opt/vagents-landing/releases/20261017-react-white/deploy'
scp -i <identity> -o BatchMode=yes -o StrictHostKeyChecking=yes landing-image.tar compose.yaml root@103.238.234.172:/opt/vagents-landing/releases/20261017-react-white/
scp -i <identity> -o BatchMode=yes -o StrictHostKeyChecking=yes deploy/deploy.sh deploy/nginx-locations.conf root@103.238.234.172:/opt/vagents-landing/releases/20261017-react-white/deploy/
```

On the VPS, verify the archive checksum matches the local file, then load it:

```bash
cd /opt/vagents-landing/releases/20261017-react-white
docker load -i landing-image.tar
bash deploy/deploy.sh vagents-landing:20261017-react-white
```

The script backs up the existing nginx config, starts only the landing Compose
project, probes its root and a generated Vite script, inserts two managed
locations into the audited TLS server when needed, validates nginx before reload
and checks the homepage, login, Platform route and API health. An unchanged
managed block does not trigger a host nginx update or reload. It verifies that
the existing Platform container IDs remain unchanged throughout deployment.
If another deployment changes nginx, the script stops and preserves that newer
configuration. On failure it restores its own nginx change and the previous
landing image. It never recreates the Platform web, app or data services.

Verify HTTPS publicly and inspect the release image, container health and
homepage asset responses. Keep the image archive, previous image and printed
nginx backup for rollback. The landing deployment does not perform migrations
or imply acceptance of model, partner or real-ticket workflows.

## Manual rollback

Use the exact backup path and previous image printed by the deployment:

```bash
cp --preserve=mode,ownership /var/backups/vagents-landing/<printed-backup>.conf /etc/nginx/sites-available/awp-platform.rollback
mv /etc/nginx/sites-available/awp-platform.rollback /etc/nginx/sites-available/awp-platform
nginx -t && systemctl reload nginx
# If there was a previous landing release, restore it with this release's compose:
LANDING_IMAGE=vagents-landing:<previous-release> docker compose -p vagents-landing -f compose.yaml up -d --no-build --pull never
```

For a first deployment, restoring the nginx backup immediately returns `/` to
the existing Platform frontend. Stop only `vagents-landing` after confirming the
public routes; do not stop the `awp-platform` project or delete its volumes.
