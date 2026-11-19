<p align="center">
  <a href="https://github.com/lupaxa-developers-toolbox">
    <img src="https://raw.githubusercontent.com/the-lupaxa-project/brand-assets/master/logos/organisations/developers-toolbox/readme-logo.png" alt="Developers Toolbox" />
  </a>
</p>

<h1 align="center">Ghostport</h1>

Ghost Port simulates HTTP APIs from declarative YAML or JSON. A project can
be one file or a directory of routes, fixtures, and scenarios. The same
project and the same requests produce the same responses.

The PyPI name is `lupaxa-ghostport`. The import path is `lupaxa.ghostport`.
The console script is `ghostport`.

## Install

```bash
pip install lupaxa-ghostport
```

Python 3.11 or newer is required.

## Quick Start

The repository has three ready-to-run projects under `samples/`. This is
the smallest:

```bash
ghostport validate samples/hello-api
ghostport serve samples/hello-api
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/users/7
```

`samples/task-board` adds stored records and a scenario. It listens on
port `8090`. `samples/checkout` adds a fixture, a response sequence, and
SQLite. It listens on port `8100`.

## Documentation

The guide lives in `mkdocs/` and publishes to
<https://ghostport.thelupaxaproject.org/>.
It has install steps, the project format, a key reference, and a
walkthrough of each sample with commands you can paste.

```bash
pip install -r requirements.txt
mkdocs serve
```

## Development

```bash
make init
make python-install-dev
make python-check
```

<a href="https://github.com/the-lupaxa-project">
    <img src="https://raw.githubusercontent.com/the-lupaxa-project/brand-assets/master/logos/components/footer-for-child-orgs.svg" alt="The Lupaxa Project Footer" width="100%" />
</a>
