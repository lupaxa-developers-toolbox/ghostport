# Usage

A Ghost Port project is data. You describe routes, state, and scenarios.
You do not write Python to answer a request.

`ghostport serve` accepts a project file or a project directory. A
directory must contain one root named `ghostport.yml`, `ghostport.yaml`,
or `ghostport.json`. JSON uses the same keys as YAML.

## Commands

```text
ghostport serve PROJECT [--host HOST] [--port PORT]
                        [--scenario ID] [--management-port PORT]
                        [--verbose]
ghostport validate PROJECT
ghostport init PATH [--single-file] [--force]
ghostport config show PROJECT [--resolved] [--format yaml|json]
ghostport scenario list [PROJECT] [--url URL]
ghostport scenario show ID [PROJECT] [--url URL]
ghostport scenario set ID [--url URL]
ghostport scenario reset [--url URL]
ghostport state show [--url URL]
ghostport state reset [--url URL]
ghostport sequence reset [ROUTE] [--url URL]
ghostport history list [--url URL]
ghostport history show REQUEST_ID [--url URL]
ghostport history clear [--url URL]
ghostport tui [--url URL] [--serve PROJECT]
```

`scenario list` and `scenario show` read the project when you pass one.
The other scenario, state, sequence, and history commands talk to a
running management interface. The default URL is `http://127.0.0.1:8081`.
Pass `--url` when the project uses another management port, as the samples
do.

`config show` prints the root file. `--resolved` prints the project after
includes and defaults. `--format json` applies only with `--resolved`.

```bash
ghostport config show samples/task-board --resolved
```

`tui` opens an inspector that polls status and history. Press `q` to quit
and `r` to refresh. `tui --serve samples/hello-api` starts that project on
an ephemeral port, opens the inspector, and stops the server when you quit.

`--verbose` logs the method and path of each API request. It does not log
headers or bodies.

## Project Files

The root may contain `version`, `api`, `server`, `routes`, `scenarios`,
`state`, `include`, `runtime`, and `management`. `version` must be `1`.
`api.name` is required. The name must not contain a host, a port, or a
mount path: no `://`, `/`, `:`, or space.

Unknown keys are errors. After includes, the project needs at least one
route. Validation reports every independent error in one run, and the
server does not listen until that run succeeds.

Includes are explicit paths. Globs are rejected, and an included file
cannot include anything else. A relative include must stay inside the
project directory. An absolute include is allowed when that file exists.
Files load in the order you list them.

An included route file contains a `routes` list. A scenario file contains
`scenarios`. A state file contains `state`. Empty route files are allowed.
An empty project, after includes, is not.

```yaml
include:
  routes:
    - routes/tasks.yml
  scenarios:
    - scenarios/normal.yml
    - scenarios/closed.yml
  state:
    - state/tasks.yml
```

> **Note:** YAML treats `yes`, `no`, `on`, and `off` as booleans. Quote
> them when the value must be a string: `text: "no"`.

## Routes

A route has an `id`, an HTTP `method`, and a `path`. It must have exactly
one of `response`, `sequence`, or `action`. Optional keys are `priority`,
`match`, `behaviour`, `after_sequence`, and `exhaustion`.

```yaml
routes:
  - id: get-user
    method: GET
    path: /users/{id}
    response:
      status: 200
      json:
        id: "{{ path.id | int }}"
        name: Ada
```

Path parameters are strings unless a template filter converts them.
`{id}` and `{user_id}` are the same path shape. Two routes with the same
method, path shape, and match are an error. Different shapes, such as
`/users/me` and `/users/{id}`, are allowed. The first match wins. Higher
`priority` is first. Equal priorities keep declaration order, including
across included files.

`match` requires every listed condition. `query` and `headers` need the
exact value. `query_present` and `headers_present` need the name only.
Names are compared without case. Header values are exact.

```yaml
match:
  query:
    status: active
  headers:
    x-shop: demo
  headers_present:
    - x-request-id
```

A request that matches nothing uses `runtime.unmatched`. The default is
status `404` and `{"error":"Not Found"}`. History stores no route id for
that request.

`HEAD`, and statuses `1xx`, `204`, and `304`, are sent with an empty body.

## Responses

A response has at most one body source: `json`, `text`, or `file`. A
response with only a status is valid. `file` is a relative path inside
the project. An absolute fixture path is rejected, and a relative path
must not leave the project root.

```yaml
response:
  status: 200
  file: fixtures/catalogue.json
  headers:
    x-source: fixture
```

The content type comes from the file extension unless a header sets it.
`template: true` renders a text or JSON fixture. A templated JSON fixture
keeps its JSON types. Fixtures are read-only. Changes belong in state.

JSON responses use `application/json; charset=utf-8` unless you set
`Content-Type`.

## Templates

Templates are lookups. They are not Jinja, and they do not run Python.
They cannot read the filesystem, the environment, or the network.

A value that is only `{{ ... }}` keeps the looked-up JSON type. A value
that mixes text and `{{ ... }}` becomes a string.

```yaml
id: "{{ path.id | int }}"
label: "user {{ path.id }}"
verbose: "{{ query.verbose | default(false) }}"
scenario: "{{ scenario.id | default(\"normal\") }}"
```

Paths are `name` or `name.child`. Segments may contain letters, digits,
`_`, and `-`, and must start with a letter or `_`. Lookups walk mappings.
They do not index lists. A collection in `state` is a list of records, so
`{{ state.tasks }}` can be a whole value, and `{{ state.tasks.0 }}` is
not a valid path.

Filters are `int`, `float`, `str`, and `default`. `default` takes one JSON
literal and applies only when the path is missing. JSON `null` is a
present value, so `default` does not replace it.

The context is:

| Name       | Contents                                            |
| ---------- | --------------------------------------------------- |
| `path`     | Path parameters as strings                          |
| `query`    | One value, or a list when the name repeats          |
| `headers`  | Request headers                                     |
| `body`     | Parsed JSON, text, or `null` when the body is empty |
| `state`    | Current collections and values                      |
| `scenario` | `id` and `description` of the active scenario       |

A body is JSON when `Content-Type` contains `json`. Otherwise it is text.
A missing path with no default is a rendering error. A bad request body
template returns 400. Other template errors return 500.

## Actions

An action reads or changes state. `resource` names a collection or a
value.

```yaml
- id: create-task
  method: POST
  path: /tasks
  action:
    type: collection.create
    resource: tasks
    input: "{{ body }}"
```

`collection.create` needs `input`, and that input must be an object with
the collection key. A duplicate key returns 409. `collection.update` with
`merge: true` copies new fields onto the existing record and keeps the
key. Keys are compared as strings, so path id `"2"` matches a record
stored as `"2"`.

`collection.list` returns the records in declaration order, then creation
order. `collection.get` and `collection.update` return 404 when the key is
absent. `collection.delete` returns 204 when the record existed.

`state.get` returns the value. `state.set` stores `input` and returns
`{"updated": "<resource>"}`.

A collection shorthand is a non-empty list of objects that all have `id`.
An empty list is a value. Use the explicit form when the key is not `id`
or the list starts empty:

```yaml
state:
  tasks:
    - id: "1"
      title: Write the guide
  audits:
    type: collection
    key: id
    records: []
  board:
    type: value
    value:
      open: true
```

## Sequences

A sequence returns the next response on each request to that route.
`after_sequence` is `repeat_last`, `loop`, or `error`. The default is
`repeat_last`. `error` uses `exhaustion`, which defaults to status `410`
and `{"error":"Sequence exhausted"}`.

```yaml
- id: take-payment
  method: POST
  path: /payments
  after_sequence: error
  exhaustion:
    status: 410
    json:
      error: Sequence exhausted
  sequence:
    - status: 503
      json:
        error: busy
    - status: 200
      json:
        paid: true
```

Counters belong to the route, not to a client. Two concurrent requests
cannot take the same position. `sequence reset` clears one route, or every
route when you omit the id, and does not change other state. `state reset`
clears the counters as well. Counters live in memory. They start again
when the process starts again, including when state is stored in SQLite.

## Scenarios

A scenario overrides routes by id. Each override has exactly one of
`response`, `sequence`, or `action`. Switching scenario does not reset
state or sequence counters.

`runtime.scenario` selects the scenario at startup. The default id is
`normal`. `normal` may be omitted; it is then an empty scenario. Any other
id must exist. `--scenario` on `serve` selects one for that process.

```yaml
scenarios:
  - id: closed
    description: The board rejects task lists
    overrides:
      - route: list-tasks
        response:
          status: 503
          json:
            error: closed
```

`ghostport scenario set closed --url http://127.0.0.1:8091` activates it.
`scenario reset` restores `runtime.scenario`.

Duplicate scenario ids, an override of an unknown route, and two overrides
of the same route in one scenario are errors.

## State

The default store is memory. Records disappear when the process exits.

```yaml
runtime:
  state:
    persistence: sqlite
    path: .ghostport/state.sqlite
```

A relative SQLite path stays inside the project. The file is seeded once.
Later processes open the same file and see the committed records.
`state reset` deletes that data and seeds it again. The documents in the
project are copied at load time and are not mutated in place.

SQLite state is independent of request history and of sequence counters.
A successful write is visible to the next request only after it commits.

## Behaviour

`behaviour.delay_ms` waits before the response. When it is omitted, the
server uses `runtime.behaviour.default_delay_ms`, which defaults to `0`.
`behaviour.failure_status` returns that status and
`{"error":"Simulated failure"}` without running the action or changing
state.

If the wait is longer than `server.request_timeout`, the response is `504`.
The timeout default is 30 seconds.

`runtime.behaviour.random_seed` is accepted and stored. This version does
not use it to vary responses.

CORS is off. When `server.cors.enabled` is true, responses include
`Access-Control-Allow-Origin: *`. An `OPTIONS` request with no matching
route then returns `204`.

A `Content-Length` above `server.max_request_body` returns `413` before
the body is read. The default limit is 1048576 bytes.

## The Management Interface

Management is enabled by default. Its host must be `127.0.0.1`,
`localhost`, or `::1`. The default port is `8081`. It does not share the
simulated API's routes.

```text
GET    /status
GET    /scenario
PUT    /scenario
POST   /scenario
POST   /scenario/reset
GET    /state
POST   /state/reset
POST   /sequence/reset
GET    /history
GET    /history/{id}
DELETE /history
GET    /config
```

`PUT` or `POST /scenario` accepts `{"id":"closed"}`.
`POST /sequence/reset` accepts `{}` or `{"route":"take-payment"}`.

```bash
curl -s http://127.0.0.1:8091/scenario
curl -s -X POST http://127.0.0.1:8091/scenario \
  -H 'Content-Type: application/json' \
  -d '{"id":"closed"}'
```

## Recorded Requests

History is enabled by default and keeps the last 1000 entries. Bodies are
captured up to 65536 bytes. `Authorization`, `Cookie`, `Set-Cookie`,
`X-Api-Key`, and `Proxy-Authorization` are stored as `[redacted]`.
`runtime.history.redact_fields` redacts those keys in JSON object bodies.

```yaml
runtime:
  history:
    enabled: true
    max_entries: 1000
    capture_bodies: true
    max_body_bytes: 65536
    redact_fields:
      - card
```

A failure while recording history does not change the API response.
`ghostport history clear` deletes the recorded requests. It does not
change API state.
