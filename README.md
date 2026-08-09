# ok-ww

An image-recognition-based automation tool for Wuthering Waves, with background mode support, developed with [ok-script](https://github.com/ok-oldking/ok-script).

Documentation is available in four languages and can also be built as a static website:

- [English](docs/en/index.md)
- [简体中文](docs/zh-CN/index.md)
- [繁體中文](docs/zh-TW/index.md)
- [日本語](docs/ja/index.md)
- [Contributing guide / 贡献指南](docs/development/contributing.md)

## Documentation website

Install the documentation dependencies and run the local preview server:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-docs.txt
.\.venv\Scripts\python.exe -m mkdocs serve
```

To generate the static HTML site in `site/`:

```powershell
.\.venv\Scripts\python.exe -m mkdocs build --strict
```

See [docs/README.md](docs/README.md) for the documentation layout and publishing details.
