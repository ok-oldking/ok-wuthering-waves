# Documentation source

This directory is the source for the ok-ww documentation website.

## Layout

- `index.md` is the language selector and site landing page.
- `en/`, `zh-CN/`, `zh-TW/`, and `ja/` contain localized user documentation.
- `development/` contains contributor documentation shared by all languages.
- `stylesheets/` contains website-only presentation styles.

Navigation and theme settings live in `mkdocs.yml` at the repository root.

## Preview locally

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pip install ".[docs]"
.\.venv\Scripts\python.exe -m mkdocs serve
```

The `web-test` extra is only needed when testing the web interface; it is not required for normal development or documentation builds.

Open `http://127.0.0.1:8000/` in a browser. Changes are rebuilt automatically.

## Build static HTML

```powershell
.\.venv\Scripts\python.exe -m mkdocs build --strict
```

The generated website is written to `site/`. Do not edit that directory; edit the Markdown sources in `docs/` instead.

Pushes to `master` publish the site through the `docs.yml` GitHub Actions workflow after a successful strict build.
