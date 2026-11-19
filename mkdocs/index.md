# Ghostport

Ghost Port simulates an HTTP API from a YAML or JSON project. A project can
be one file or a directory of routes, fixtures, and scenarios. The server
checks the project before it listens. The same project and the same
requests produce the same responses.

The package name is `lupaxa-ghostport`. The import path is
`lupaxa.ghostport`. The command is `ghostport`.

## What it Does

- Serves `GET`, `POST`, `PUT`, `PATCH`, `DELETE`, `HEAD`, and `OPTIONS`
- Returns static JSON, text, or a fixture file
- Fills responses from a small lookup language
- Stores collections and values in memory or SQLite
- Switches scenarios without clearing that state
- Plays a route's responses in order
- Records requests on a separate localhost management port
- Opens a Textual inspector with `ghostport tui`

## Samples

The repository includes three projects you can validate and serve as they
stand.

| Sample               | What it Shows                                 | API              |
| -------------------- | --------------------------------------------- | ---------------- |
| `samples/hello-api`  | One file, a static route, and a path template | `127.0.0.1:8080` |
| `samples/task-board` | Includes, stored tasks, and a closed scenario | `127.0.0.1:8090` |
| `samples/checkout`   | A fixture, a payment sequence, and SQLite     | `127.0.0.1:8100` |

Each sample uses its own management port: `8081`, `8091`, and `8101`.
Run one sample at a time, or keep those ports.

## The Guide

[Getting Started](getting-started.md) installs the package and serves
`samples/hello-api`. [Usage](usage.md) explains the project format.
[Reference](reference.md) lists the keys, defaults, and endpoints.
[Examples](examples.md) walks through all three samples with commands you
can paste.
