# Production hosting: Hetzner + Cloudflare

This is the production path for the SHNL 36-0 application. Caddy is the only
public container. It terminates HTTPS on ports 80/443, serves the web app, and
routes same-origin `/api/*` requests to the private API container. The web and
API services have no host-published ports, and account/season data lives in a
named Docker volume.

The local `docker-compose.yml` remains the development stack on ports 3001 and
8002. Production uses `compose.production.yml`.

## 1. Buy the domain

In Cloudflare, open **Domain Registration → Register Domains**, buy the domain,
and verify the registrant email. A Cloudflare Registrar domain automatically
uses Cloudflare nameservers, and an unverified registrant email can put the
domain on hold. See Cloudflare's current
[registration instructions](https://developers.cloudflare.com/registrar/get-started/register-domain/).

Do not create the DNS records yet; first create the server so you know its IP.

## 2. Create and lock down the Hetzner server

In a Hetzner Cloud project, create an x86-64 server with:

- Ubuntu 24.04 LTS
- at least 2 vCPU, 4 GB RAM, and 40 GB disk for a small launch
- a location close to the expected players
- your SSH public key
- Hetzner automated backups enabled

Hetzner documents the server choices and notes that an SSH key must be selected
during creation in its [server creation guide](https://docs.hetzner.com/cloud/servers/getting-started/creating-a-server/).
The plan is only an initial size; watch CPU, RAM, disk, and room concurrency and
resize when the data says to.

Create a Hetzner Cloud Firewall and attach it to this server:

| Direction | Protocol | Port | Source |
|---|---:|---:|---|
| Inbound | TCP | 22 | your fixed IP/CIDR if possible |
| Inbound | TCP | 80 | any IPv4 and IPv6 |
| Inbound | TCP | 443 | any IPv4 and IPv6 |
| Inbound | UDP | 443 | any IPv4 and IPv6 (HTTP/3) |
| Outbound | all | all | any |

Do **not** expose 3000, 3001, 8000, or 8002. Hetzner drops unmatched inbound
traffic when inbound rules exist; see the official
[Cloud Firewall guide](https://docs.hetzner.com/cloud/firewalls/getting-started/creating-a-firewall/).

Connect using the server IPv4 shown in Hetzner:

```bash
ssh root@YOUR_HETZNER_IPV4
```

Hetzner's [SSH connection guide](https://docs.hetzner.com/cloud/servers/getting-started/connecting-to-the-server/)
explains the IPv4/IPv6 forms and first-connect fingerprint prompt. Verify the
fingerprint in the Hetzner console before accepting it.

Create an unprivileged deployment user and copy the authorized key:

```bash
adduser deploy
usermod -aG sudo deploy
install -d -m 700 -o deploy -g deploy /home/deploy/.ssh
cp /root/.ssh/authorized_keys /home/deploy/.ssh/authorized_keys
chown deploy:deploy /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys
```

Open a second terminal and confirm `ssh deploy@YOUR_HETZNER_IPV4` works before
hardening SSH. Then create `/etc/ssh/sshd_config.d/99-hnl.conf`:

```text
PermitRootLogin no
PasswordAuthentication no
PubkeyAuthentication yes
```

Validate and reload without closing the working SSH session:

```bash
sshd -t
systemctl reload ssh
```

Keep the Hetzner web console available as an emergency route.

## 3. Install Docker from Docker's Ubuntu repository

Run these as the `deploy` user. The commands follow Docker's current
[Ubuntu installation guide](https://docs.docker.com/engine/install/ubuntu/):

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

```bash
sudo tee /etc/apt/sources.list.d/docker.sources >/dev/null <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
```

```bash
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker deploy
```

Log out and back in, then verify:

```bash
docker run --rm hello-world
docker compose version
```

Membership in the `docker` group grants root-level control of the host. Keep
this account key-only and private; Docker documents that warning in its
[Linux post-install guide](https://docs.docker.com/engine/install/linux-postinstall/).
Use `sudo docker ...` instead if you do not want to grant that membership.

Docker warns that published container ports can bypass UFW rules. This stack
therefore publishes only Caddy's 80/443 and relies on the Hetzner Cloud
Firewall as the outer control; see Docker's
[Ubuntu firewall warning](https://docs.docker.com/engine/install/ubuntu/).

## 4. Put the repository on the server

Push the tested repository to your Git host first. On the server:

```bash
sudo install -d -o deploy -g deploy /opt/380hnl
git clone YOUR_REPOSITORY_SSH_OR_HTTPS_URL /opt/380hnl
cd /opt/380hnl
```

For a private repository, use a read-only deploy key or short-lived access
token. Do not put a personal access token in the clone URL, shell history, or
repository files.

Create production secrets:

```bash
cp .env.production.example .env.production
openssl rand -hex 32
nano .env.production
chmod 600 .env.production
```

Set:

```dotenv
DOMAIN=your-real-domain.example
ACME_EMAIL=your-real-email@example.com
HNL_AUTH_PEPPER=paste-the-64-character-random-value
HNL_SECURE_COOKIES=1
HNL_AUTH_SESSION_SECONDS=2592000
HNL_PASSWORD_SCRYPT_N=131072
HNL_TRUST_PROXY=1
HNL_AUTH_RATE_LIMIT_ATTEMPTS=10
HNL_AUTH_RATE_LIMIT_WINDOW_SECONDS=300
HNL_ROOM_TTL_SECONDS=86400
```

`DOMAIN` is the bare apex hostname: no scheme, path, `www`, or trailing slash.
Back up `HNL_AUTH_PEPPER` in a password manager. Never commit
`.env.production`; the repository ignores it and the Docker build context
excludes it.

`HNL_AUTH_SESSION_SECONDS=2592000` keeps a login for 30 days. Caddy overwrites
the client-address headers before `HNL_TRUST_PROXY=1` lets the API use them for
the login limiter. Keep the Cloudflare CIDRs in `Caddyfile` synchronized with
Cloudflare's official [IPv4 and IPv6 lists](https://www.cloudflare.com/ips/).

Validate the resolved Compose model before starting:

```bash
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml build --pull
```

## 5. Point Cloudflare DNS to Hetzner and issue HTTPS

In **Cloudflare → DNS → Records**, create:

| Type | Name | Content | Proxy status | TTL |
|---|---|---|---|---|
| A | `@` | Hetzner IPv4 | **DNS only** initially | Auto |
| CNAME | `www` | `@` | **DNS only** initially | Auto |

Add an AAAA record only after IPv6 is configured and tested on the server.
Cloudflare's [DNS record guide](https://developers.cloudflare.com/dns/manage-dns-records/how-to/create-dns-records/)
describes these fields and the DNS-only/proxied switch.

Wait until both names resolve to the Hetzner IP:

```bash
dig +short your-real-domain.example A
dig +short www.your-real-domain.example A
```

Start the stack:

```bash
cd /opt/380hnl
docker compose --env-file .env.production -f compose.production.yml up -d
docker compose --env-file .env.production -f compose.production.yml ps
docker compose --env-file .env.production -f compose.production.yml logs --tail=100 caddy
```

Caddy obtains and renews public certificates automatically when the hostname
resolves to the server and ports 80/443 reach Caddy, as documented in
[Caddy Automatic HTTPS](https://caddyserver.com/docs/automatic-https).

Smoke-test both routes:

```bash
curl --fail --show-error --silent https://your-real-domain.example/api/health
curl --fail --show-error --silent --head https://your-real-domain.example/
```

The first URL proves `/api` is stripped exactly once and reaches API `/health`;
the second proves the frontend is behind Caddy.

After both HTTPS tests pass:

1. Change the apex A and `www` CNAME records to **Proxied** (orange cloud).
2. In **SSL/TLS → Overview**, choose **Full (strict)**. This requires a valid,
   hostname-matching certificate at the origin, which Caddy now has. Cloudflare
   calls Full (strict) its best-security general option in the
   [current mode documentation](https://developers.cloudflare.com/ssl/origin-configuration/ssl-modes/full-strict/).
3. Optionally enable **Always Use HTTPS** under **SSL/TLS → Edge Certificates**.
   Caddy also redirects direct-origin HTTP safely. Cloudflare documents the
   edge switch [here](https://developers.cloudflare.com/ssl/edge-certificates/additional-options/always-use-https/).
4. Create a Cache Rule that bypasses cache when the URI path equals `/api` or
   starts with `/api/`. Caddy already sends `Cache-Control: no-store`, but an
   explicit edge bypass protects authenticated JSON if cache policy changes.

Cloudflare recommends proxying web A/AAAA/CNAME records; its
[proxy-status reference](https://developers.cloudflare.com/dns/proxy-status/)
explains that proxied requests traverse Cloudflare while DNS-only requests go
directly to the origin. SSH still uses the Hetzner IP because Cloudflare's
ordinary proxy does not proxy port 22; see its
[supported-ports reference](https://developers.cloudflare.com/fundamentals/reference/network-ports/).

Run the two `curl` checks again after the proxy becomes active. Also register,
log in, finish a short season, log out/in, and confirm that its history remains.

## 6. Routine operation

Use the same Compose prefix for every production command:

```bash
cd /opt/380hnl
docker compose --env-file .env.production -f compose.production.yml ps
docker compose --env-file .env.production -f compose.production.yml logs --tail=200
```

The stable production volume names are:

- `hnl38_hnl_rooms`: SQLite rooms, accounts, sessions, and season history
- `hnl38_caddy_data`: certificates and Caddy state
- `hnl38_caddy_config`: Caddy runtime configuration

Named volumes outlive container replacement. Docker documents their lifecycle
and backup model in its [volume guide](https://docs.docker.com/engine/storage/volumes/).
Never run `docker compose down -v` in production: `-v` deletes the application
database and Caddy state.

### Database backup

Use SQLite's online backup API so a live database is copied consistently:

```bash
cd /opt/380hnl
mkdir -p backups
chmod 700 backups
BACKUP_NAME="rooms-$(date -u +%Y%m%dT%H%M%SZ).sqlite3"
docker compose --env-file .env.production -f compose.production.yml exec -T api \
  python -c "import sqlite3; s=sqlite3.connect('/data/rooms.sqlite3'); d=sqlite3.connect('/data/$BACKUP_NAME'); s.backup(d); d.close(); s.close()"
docker compose --env-file .env.production -f compose.production.yml cp \
  "api:/data/$BACKUP_NAME" "backups/$BACKUP_NAME"
docker compose --env-file .env.production -f compose.production.yml exec -T api \
  python -c "import os; os.unlink('/data/$BACKUP_NAME')"
sha256sum "backups/$BACKUP_NAME"
```

Copy each backup off the server to encrypted object storage or another machine,
and test restoration regularly. Hetzner server backups complement this process;
they are not a substitute for a separately retained database copy.

### Database restore

Restoration causes downtime and replaces current account/history data. Confirm
the backup filename and checksum first, then:

```bash
cd /opt/380hnl
RESTORE_FILE=rooms-YYYYMMDDTHHMMSSZ.sqlite3
docker compose --env-file .env.production -f compose.production.yml stop api
docker compose --env-file .env.production -f compose.production.yml run --rm --no-deps \
  -v "/opt/380hnl/backups:/restore:ro" api \
  python -c "import sqlite3; s=sqlite3.connect('/restore/$RESTORE_FILE'); d=sqlite3.connect('/data/rooms.sqlite3'); s.backup(d); d.close(); s.close()"
docker compose --env-file .env.production -f compose.production.yml up -d api
docker compose --env-file .env.production -f compose.production.yml up -d
curl --fail --show-error --silent https://your-real-domain.example/api/health
```

### Update with rollback

Deploy immutable release tags or reviewed commit SHAs, not an unreviewed moving
branch:

```bash
cd /opt/380hnl
PREVIOUS_SHA="$(git rev-parse HEAD)"
git fetch --all --tags --prune
git checkout YOUR_TESTED_TAG_OR_COMMIT
docker compose --env-file .env.production -f compose.production.yml config --quiet
docker compose --env-file .env.production -f compose.production.yml build --pull
docker compose --env-file .env.production -f compose.production.yml up -d --remove-orphans
docker compose --env-file .env.production -f compose.production.yml ps
curl --fail --show-error --silent https://your-real-domain.example/api/health
```

To roll application code back:

```bash
git checkout "$PREVIOUS_SHA"
docker compose --env-file .env.production -f compose.production.yml build
docker compose --env-file .env.production -f compose.production.yml up -d --remove-orphans
```

Do not restore the database merely to roll back frontend code. If an API release
contains an incompatible database migration, use the pre-deploy database backup
and accept that records created after that backup will be lost.

## 7. Launch checklist

- DNS resolves correctly and both records are proxied only after Caddy gets a certificate.
- Cloudflare SSL/TLS mode is Full (strict), never Flexible.
- Only 22, 80, and 443 are reachable; 3000/3001/8000/8002 are closed.
- `.env.production` is mode 600, untracked, and backed up securely.
- Registration, login, logout, and cookie persistence work over HTTPS.
- Solo and live-room seasons complete and appear in signed-in history.
- `/api` has an edge cache-bypass rule.
- Daily database backups leave the server and a restore has been tested.
- `docker compose ps` shows API and web healthy.
- Hetzner alerts/monitoring and disk-space checks are configured.

### Before broad public registration

The first account release intentionally has no email-verification/password-
reset provider and no self-service account export/deletion screen. Before
marketing public signups, choose a transactional-email provider, implement
verified recovery, publish a privacy notice with a retention/contact policy,
and add authenticated export/deletion flows. The European Commission's
[GDPR principles](https://commission.europa.eu/law/law-topic/data-protection/information-business-and-organisations/principles-gdpr_en)
cover data minimisation and storage limitation, while its
[individual-request guidance](https://commission.europa.eu/law/law-topic/data-protection/rules-business-and-organisations/dealing-individuals-requests_en)
covers access and erasure requests. This is a launch checklist, not legal
advice.
