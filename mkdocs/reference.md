# Reference

This page lists the keys the loader accepts. Unknown keys are errors.
`version` must be `1`.

## Root Keys

| Key          | Required | Purpose                                           |
| ------------ | -------- | ------------------------------------------------- |
| `version`    | Yes      | Schema version. Must be `1`.                      |
| `api`        | Yes      | `name` and optional `description`.                |
| `server`     | No       | Bind address, port, timeout, body limit, CORS.    |
| `routes`     | No       | Inline routes.                                    |
| `scenarios`  | No       | Inline scenarios.                                 |
| `state`      | No       | Inline collections and values.                    |
| `include`    | No       | `routes`, `scenarios`, and `state` file lists.    |
| `runtime`    | No       | Scenario, persistence, history, unmatched, delay. |
| `management` | No       | Localhost control port.                           |

At least one route must exist after includes.

`api.name` must be a non-empty string without `://`, `/`, `:`, or a space.

## Server Defaults

| Property           | Default     | Purpose                              |
| ------------------ | ----------- | ------------------------------------ |
| `host`             | `127.0.0.1` | Bind address. `0.0.0.0` is explicit. |
| `port`             | `8080`      | API port. `0` asks for a free port.  |
| `request_timeout`  | `30`        | Seconds before a wait becomes `504`. |
| `max_request_body` | `1048576`   | Largest accepted body, in bytes.     |
| `cors.enabled`     | `false`     | Add open CORS headers when `true`.   |

`--host`, `--port`, and `--management-port` override the file for that
process. `--scenario` overrides `runtime.scenario`.

## Management Defaults

| Property  | Default     | Purpose                                  |
| --------- | ----------- | ---------------------------------------- |
| `enabled` | `true`      | Open the control port.                   |
| `host`    | `127.0.0.1` | `127.0.0.1`, `localhost`, or `::1` only. |
| `port`    | `8081`      | Control port.                            |

## Route Keys

| Key              | Required     | Purpose                                               |
| ---------------- | ------------ | ----------------------------------------------------- |
| `id`             | Yes          | Stable route id. Unique in the project.               |
| `method`         | Yes          | `GET` `POST` `PUT` `PATCH` `DELETE` `HEAD` `OPTIONS`. |
| `path`           | Yes          | Path pattern. `{name}` captures one segment.          |
| `priority`       | No           | Higher values match first. Default `0`.               |
| `match`          | No           | Extra query and header conditions.                    |
| `response`       | One of three | Static or templated response.                         |
| `sequence`       | One of three | Ordered responses.                                    |
| `action`         | One of three | State operation.                                      |
| `behaviour`      | No           | `delay_ms` and `failure_status`.                      |
| `after_sequence` | No           | `repeat_last`, `loop`, or `error`.                    |
| `exhaustion`     | No           | Response used when `after_sequence` is `error`.       |

Exactly one of `response`, `sequence`, and `action` is required.

## Match Keys

| Key               | Match Rule                                             |
| ----------------- | ------------------------------------------------------ |
| `query`           | Name and exact value. The value may be one of several. |
| `query_present`   | The query name is present.                             |
| `headers`         | Header name, exact value.                              |
| `headers_present` | The header name is present.                            |

Names are compared without case. Header values are exact. Every listed
condition must match.

## Response Keys

| Key        | Purpose                                 |
| ---------- | --------------------------------------- |
| `status`   | Integer from 100 to 599. Default `200`. |
| `json`     | JSON body. Templates are rendered.      |
| `text`     | Text body. Templates are rendered.      |
| `file`     | Fixture path inside the project.        |
| `template` | `true` renders a text or JSON fixture.  |
| `headers`  | Extra response headers.                 |

Use at most one of `json`, `text`, and `file`. Statuses `1xx`, `204`, and
`304`, and every `HEAD` response, are sent with an empty body.

## Action Types

| Type                | Success                       | Other Results                        |
| ------------------- | ----------------------------- | ------------------------------------ |
| `collection.list`   | `200` and an array            |                                      |
| `collection.get`    | `200` and the record          | `404` when the key is missing        |
| `collection.create` | `201` and the object          | `400` bad input, `409` duplicate key |
| `collection.update` | `200` and the record          | `400` bad input, `404` missing key   |
| `collection.delete` | `204` and an empty body       | `404` when the key is missing        |
| `state.get`         | `200` and the value           |                                      |
| `state.set`         | `200` and `{"updated": name}` |                                      |

`status` on the action replaces the success status. `key` selects the
record for get, update, and delete. `input` is required for
`collection.create` and is the new value for `state.set`. `merge: true`
on update keeps fields you do not send.

## Sequence Policies

| Policy        | Behaviour                                              |
| ------------- | ------------------------------------------------------ |
| `repeat_last` | Keep returning the last response. This is the default. |
| `loop`        | Start again at the first response.                     |
| `error`       | Return `exhaustion` after the last response.           |

The default exhaustion response is status `410` and
`{"error":"Sequence exhausted"}`.

## State Forms

| Form                                | Meaning                             |
| ----------------------------------- | ----------------------------------- |
| Non-empty list of objects with `id` | Collection. The key is `id`.        |
| `{type: collection, key, records}`  | Collection. `records` may be empty. |
| `{type: value, value}`              | One stored value.                   |
| Any other JSON value                | A value stored under that name.     |

Duplicate collection names and duplicate value names are errors.

## Runtime Keys

| Key                          | Default                       | Purpose                                   |
| ---------------------------- | ----------------------------- | ----------------------------------------- |
| `scenario`                   | `normal`                      | Active scenario id.                       |
| `state.persistence`          | `memory`                      | `memory` or `sqlite`.                     |
| `state.path`                 | `.ghostport/state.sqlite`     | SQLite file when persistence is `sqlite`. |
| `history.enabled`            | `true`                        | Record requests.                          |
| `history.max_entries`        | `1000`                        | Oldest entries fall away.                 |
| `history.capture_bodies`     | `true`                        | Store request bodies.                     |
| `history.max_body_bytes`     | `65536`                       | Body capture limit.                       |
| `history.redact_fields`      | empty                         | JSON object keys stored as `[redacted]`.  |
| `unmatched`                  | `404` `{"error":"Not Found"}` | Response when no route matches.           |
| `behaviour.default_delay_ms` | `0`                           | Delay used when a route omits `delay_ms`. |
| `behaviour.random_seed`      | omitted                       | Stored. It does not change responses.     |

## Management Endpoints

| Method and Path        | Body                     | Result                                           |
| ---------------------- | ------------------------ | ------------------------------------------------ |
| `GET /status`          |                          | API name, scenario, route count, persistence.    |
| `GET /scenario`        |                          | The active scenario.                             |
| `PUT /scenario`        | `{"id":"..."}`           | Switch scenario. `POST` does the same.           |
| `POST /scenario/reset` |                          | Restore `runtime.scenario`.                      |
| `GET /state`           |                          | Collections and values.                          |
| `POST /state/reset`    |                          | Restore the initial state and sequence counters. |
| `POST /sequence/reset` | `{}` or `{"route":"id"}` | Clear one sequence or all sequences.             |
| `GET /history`         |                          | `{"entries":[...]}`                              |
| `GET /history/{id}`    |                          | One entry, or `404`.                             |
| `DELETE /history`      |                          | Delete the recorded requests.                    |
| `GET /config`          |                          | The resolved project.                            |

An unknown scenario id or route id returns `400` and `{"error":"..."}`.

## History Fields

| Field            | Contents                               |
| ---------------- | -------------------------------------- |
| `request_id`     | Unique id.                             |
| `timestamp`      | Arrival time.                          |
| `method`         | HTTP method.                           |
| `path`           | URL path.                              |
| `query`          | Query parameters.                      |
| `headers`        | Request headers after redaction.       |
| `body`           | Captured body, or `null`.              |
| `body_truncated` | `true` when the capture hit the limit. |
| `route`          | Matched route id, or `null`.           |
| `scenario`       | Active scenario id.                    |
| `status`         | Response status.                       |
| `duration_ms`    | Time spent in the engine.              |
| `error`          | Template or internal error, or `null`. |

These header names are always redacted: `Authorization`, `Cookie`,
`Set-Cookie`, `X-Api-Key`, `Proxy-Authorization`.

## Template Language

A template is `{{ path | filter }}`. The path is one or more dot-separated
names. A whole-value template keeps the JSON type. Mixed text becomes a
string.

| Filter             | Result                                     |
| ------------------ | ------------------------------------------ |
| `int`              | Integer from a string or number.           |
| `float`            | Floating point number.                     |
| `str`              | String. `null` becomes an empty string.    |
| `default(literal)` | The JSON literal when the path is missing. |

`default` accepts one JSON literal, such as `false`, `0`, `null`, or
`"normal"`. There is no list index and no arithmetic.

Context names are `path`, `query`, `headers`, `body`, `state`, and
`scenario`.

## Exit Codes

| Code  | Meaning                             |
| ----- | ----------------------------------- |
| `0`   | The command finished.               |
| `1`   | An operational or system error.     |
| `2`   | A usage or configuration error.     |
| `130` | The server was stopped with Ctrl-C. |

## The Python API

```python
from lupaxa.ghostport import ApiEngine, load_project

project = load_project("samples/hello-api")
engine = ApiEngine(project)
```

`load_project` raises `ConfigError`. Its `messages` list holds every
independent error. `ApiEngine.handle` accepts one request and returns one
response without opening a socket. `set_scenario`, `reset_scenario`,
`reset_state`, and `reset_sequence` are the same operations as the
management routes.
