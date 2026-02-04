# Contributing to Photoserv

## Architecture

This must be respected when contributing.

* **Core** contains core business logic and models for media. It only depends on "utility" apps.
    * Caveat: `core.PhotoForm` imports from `integration` because I couldn't find a better way to do this.
    It is done in such a way to avoid circular dependency and provide loose-ish coupling.
* **Public REST API** depends on core to expose read-only endpoints for external consumption (including integration).
* **Integration** depends on core and public_rest_api to extend functionality via plugins and webhooks.
* **Home** is a placeholder for dashboard functionality and depends on core.
* **All other apps** are utility apps with no dependencies on core or each other. They can be lifted right into other projects if needed.

## Development

### Setup

1. Create venv
2. `npm ci`
3. `./dev.sh`

### Secret Environment Variables

* `IS_CONTAINER` - Set to `true` to simulate running in Docker (you likely don't want to use this)
* `PLUGINS_PATH` - Override default plugin directory (`./plugins`) for local development... i.e pointing to a cloned copy of the plugins repository.

### Testing

**Always add or update tests for code changes**.

```bash
python manage.py test
```

Run tests before every commit.

## Coding Standards

**YOUR PR WILL BE REJECTED IF THESE STANDARDS ARE NOT MET.**

### In General

* NO EMOJIS in source code, commit messages, Markdown documentation.

### Python

* Follow PEP 8 for imports (top of file)
* Exception: Importing `integration` within `core.PhotoForm` is allowed to avoid circular dependency and loose-ish coupling.

### Templates

* Use DaisyUI theme variables. Do not explicitly color text or elements.
* Do not add border radius styles or classes.

Example:

```html
<!-- Good: Uses theme color -->
<button class="btn btn-primary">Submit</button>

<!-- Bad: Explicit colors -->
<button class="bg-blue-500 text-white rounded-lg">Submit</button>

<!-- Bad: Border radius -->
<div class="rounded-md">Content</div>
```

### Documentation

* Use `*` for bullet lists.
* There should be a blank line between headings and the following text.

### Before Committing

0. Understand your code will be under the MIT License.
1. Run `python manage.py test`
2. Verify all tests pass
3. Review code style guidelines above

## TODO (Wanted Contributions)

### Bugs

* OIDC reauthorization redirect drops POST requests, essentially losing form submissions.

### Feature Requests

* Query photos (photo table in UI) by any arbitrary fields and/or metadata
* Dynamic entires-per-page for all tables.
* Automatic albums based on photo data/metadata (e.g., camera model, location)
* Real implementation of a dashboard (home app)?... This is very low priority.
* Support for geotags, manual geotags, and a photo map
* Stylized error pages (404, 500, etc.)

## Project Structure

```
photoserv/
├── api_key/           # API key management
├── core/              # Photos, albums, tags (core logic)
├── iam/               # User authentication
├── integration/       # Plugins & webhooks
├── job_overview/      # Celery task monitoring frontend
├── public_rest_api/   # REST API endpoints
├── home/              # Dashboard (placeholder)
├── photoserv/         # Django settings
├── photoserv_plugin/  # Plugin base classes
├── templates/         # HTML templates
├── static/            # CSS/JS assets
```

## Resources

* **README.md** - Installation and configuration
* **Swagger** - `https://<your-instance>/swagger` (API documentation)
* **GitHub** - https://github.com/photoserv/photoserv
