# Getting Started

Python 3.11 or newer is required.

## Install

```bash
pip install lupaxa-ghostport
```

From a checkout of this repository:

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

`ghostport` with no command prints help and exits 0. `ghostport --version`
prints the package version.

## Run the Hello API

The smallest sample is one YAML file.

```bash
ghostport validate samples/hello-api
ghostport serve samples/hello-api
```

`validate` prints a short report and exits 0 when the project is usable.
`serve` prints the listen URLs on stderr and keeps running until you press
Ctrl-C.

```text
Ghost Port listening on http://127.0.0.1:8080
Management listening on http://127.0.0.1:8081
```

In another terminal:

```bash
curl http://127.0.0.1:8080/health
curl http://127.0.0.1:8080/users/7
```

```json
{"status": "healthy"}
```

```json
{"id": 7, "name": "Ada"}
```

`/users/7` reads the path parameter `id` and converts it with the `int`
filter. The file is `samples/hello-api/ghostport.yml`. The same text is on
the [Examples](examples.md) page.

Stop the server with Ctrl-C. The process exits 130.

## Start a New Project

```bash
ghostport init ./my-api
ghostport validate ./my-api
ghostport serve ./my-api
```

`init` writes `ghostport.yml`, `routes/example.yml`,
`scenarios/normal.yml`, and an empty `fixtures/` directory. It refuses to
replace a file that already exists unless you pass `--force`.

```bash
ghostport init ./my-api --single-file
```

That writes only `my-api/ghostport.yml`.

## Choose a Port

The file's `server.port` is the default. The command line wins:

```bash
ghostport serve samples/hello-api --port 9000
```

`--host` overrides `server.host`. The default host is `127.0.0.1`. Use
`host: 0.0.0.0` in the project, or `--host 0.0.0.0`, when the API should
listen on every interface. The management interface stays on localhost.

## Build the Documentation

The site source is `mkdocs/`, not `docs/`.

```bash
pip install -r requirements.txt
mkdocs serve
```

`mkdocs build --strict` writes the site into `site/`. That directory is
generated and is not part of the project.
