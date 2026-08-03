# Contributing to Photoserv

# 1.0 Branch Committed Changes:

(for future changelog after squash merge)

* Rename 'core' to 'media'
* Newer API schema
    * Session Auth supported
    * Read/write endpoints for resources (admin api)
    * Write requires permission on API key
    * Public API moved to `/public/`
* Authentication is now enforced; no anonymous mode.

# 1.0 Change List (TODO):

* Implement publishing channels; publishing logic fully owned by Media
* Remove public_rest_api; apps to own APIs
* Photo calendar shall be based on publishing channels
* A photo shall not be published until all sizes are generated
* All integrations shall be python based
* Integrations subscribe to a publishing channel

## Architecture

This must be respected when contributing.

// TODO: rewrite

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

* Automatic albums based on photo data/metadata (e.g., camera model, location)
* Real implementation of a dashboard (home app)?... This is very low priority.
* Photo map
* Bulk photo editing for select actions

## Project Structure

// TODO: Rewrite

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
* **GitHub** - https://github.com/itsmaxymoo/photoserv
