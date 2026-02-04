# Photoserv

Photoserv is an application for photographers, artists, or similar who want a system to act as a single source of truth
for their publicly published photos.

**Looking to contribute or inspect the code?** See **[CONTRIBUTING.md](CONTRIBUTING.md)**.

| ![Photo detail](docs/screenshots/photo_detail.png) | ![Album detail](docs/screenshots/album_detail.png) |
| --- | --- |
| ![Size list](docs/screenshots/size_list.png) | ![API Key list](docs/screenshots/api_key_list.png) |

## Features

* Upload and categorize photos by albums and tags.
* Extract metadata from photos for consumption in other systems.
* Exposes a REST API for applications and integrations to interact with your data.
    * For example, a photo portfolio website in Astro.js can consume this.
    * Swagger API browser included.
* Define multiple sizes for your photos to be available in.
* OIDC and simple auth optional.
* Web request dispatch upon global changes.
* Python plugin system for advanced integrations.

## Installation

1. Configure (below)
2. `docker compose up -d`

## Configuration

Configure the environment variables; `cp example.env .env`

```env
# openssl rand -hex 64
APP_KEY=""

DEBUG_MODE=false # always false in production

TIME_ZONE=America/New_York

DATABASE_ENGINE=postgres # postgres or sqlite
DATABASE_USER=photoserv
DATABASE_PASSWORD=photoserv
DATABASE_NAME=photoserv
DATABASE_HOST=database
DATABASE_PORT=5432

REDIS_HOST=redis
REDIS_PORT=6379

ALLOWED_HOSTS=127.0.0.1,localhost # Add photoserv domain here

SIMPLE_AUTH=True # Recommended to disable if you use OIDC

# Each of OIDC_CLIENT_*, OIDC_*_ENDPOINT must be filled to enable OIDC
OIDC_NAME=Single Sign On Button Label
OIDC_CLIENT_ID=
OIDC_CLIENT_SECRET=
OIDC_AUTHORIZATION_ENDPOINT=
OIDC_TOKEN_ENDPOINT=
OIDC_USER_ENDPOINT=
OIDC_JWKS_ENDPOINT=
OIDC_SIGN_ALGO=RS256 # optional
```

OIDC Callback URL: `<your-photoserv-root>/login/oidc/callback/`  
Example: `https://photoserv.domain.com/login/oidc/callback/`  

> [!IMPORTANT]
> Be sure to set an OIDC Access Token expiration that is long enough for the duration of time
you may be working on the multi-photo upload form. I use 1 hour.

## API Documentation

Once set up, visit `https://<your-instance/swagger` for an interactive Swagger API browser.

> [!NOTE]
> You will have to create an API key from within Photoserv (`Settings > Public API`) before
using Swagger.

## Security

While I've made my best effort to secure this application, leaning on existing solutions and libraries where possible,
I am one person, and I cannot guarantee it is *perfect*. It is not recommended to expose this application
directly to the internet. Ideally:

* Run this application by a reverse proxy (ports are commented out by default in `docker-compose.yml`).
* Use a tunnel or on-prem runner to build derivative websites off of the API.
* If necessary, try to only expose the public api (`/api`).
* Otherwise, put the frontend in front of a proxy-auth middleware like Authentik.

### Examples (Traefik + Authentik)

Assume:

* `websecure` - internal HTTPS
* `websecure-external` external access HTTPS

#### Internal access only

```
- "traefik.http.routers.photoserv.rule=Host(`photoserv.domain.com`)"
- "traefik.http.routers.photoserv.entrypoints=websecure"
- "traefik.http.services.photoserv.loadbalancer.server.port=8000"
```

#### Public API Only, Private Front End

```
- "traefik.http.routers.photoserv.rule=Host(`photoserv.domain.com`)"
- "traefik.http.routers.photoserv.entrypoints=websecure"
- "traefik.http.routers.photoserv.service=photoserv"

- "traefik.http.routers.photoserv-external.rule=Host(`photoserv.domain.com`) && PathPrefix(`/api`)"
- "traefik.http.routers.photoserv-external.entrypoints=websecure,websecure-external"
- "traefik.http.routers.photoserv-external.service=photoserv"

- "traefik.http.services.photoserv.loadbalancer.server.port=8000"
```

#### Proxy Auth Front End with Public API

```
- "traefik.http.routers.photoserv.rule=Host(`photoserv.domain.com`) && PathPrefix(`/api`)"
- "traefik.http.routers.photoserv-external.entrypoints=websecure,websecure-external"
- "traefik.http.routers.photoserv.service=photoserv"

- "traefik.http.routers.photoserv-external.rule=Host(`photoserv.domain.com`)"
- "traefik.http.routers.photoserv-external.entrypoints=websecure-external"
- "traefik.http.routers.photoserv-external.middlewares=authentik@docker"
- "traefik.http.routers.photoserv-external.service=photoserv"

- "traefik.http.services.photoserv.loadbalancer.server.port=8000"
```

## Integrations

### Web Requests

Photoserv can be configured to dispatch web requests upon a global change.
This can be useful for triggering a static site generator upon creating content.

![Web request example](docs/screenshots/web_request.png)

Web requests will be dispatched 10 minutes after the *most recent* Photoserv change to reduce excessive dispatches.

#### Gitea Example

Suppose you have a SSG project set up in a Gitea repo. You can call the `deploy.yml` workflow using Photoserv like so:

| Parameter | Value |
| --- | --- |
| Method | `POST` |
| URL | `https://your-gitea-instance.domain/api/v1/repos/<namespace>/<repo>/actions/workflows/deploy.yml/dispatches` |
| Headers | `Content-Type: application/json`<br>`Authorization: token ${GITEA_KEY}` |
| Body | `{ "ref": "main" }` |
| Active | Checked |

### Python Plugins

Photoserv supports Python-based plugins to extend functionality beyond web requests.
Plugins can intercept global changes as well as photo publish events. Use plugins for things like social media integration or more complex workflows.

![Plugin example](docs/screenshots/python_plugin.png)

See the [Photoserv plugin repository](https://github.com/photoserv/python-plugins) for first-class plugins, examples, and documentation. **Be careful** running Python plugins as they essentially allow arbitrary code execution.

### Secrets

Both web requests and plugins can use environment variables in the `${ENV_VAR}` format to safely reference secrets. Be careful not to leak secrets with this!

### Integrations for Other Projects

* [Astro Loader](https://github.com/photoserv/astro-loader) - For the Astro static site generator.

## AI Disclosure

AI has been used in the capacity of an advanced autocomplete while making this project.
All architectural choices and model interfaces have been created and decided upon
by a human, with physical pen-and-paper, or while on a long run. This entire README
is handwritten without obnoxious emojis.
