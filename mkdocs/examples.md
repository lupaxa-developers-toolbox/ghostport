# Examples

These three directories are in `samples/`. Each one validates, and each
one can be served with the command shown below. They listen on different
ports so the curl lines work without extra flags.

Stop a server with Ctrl-C before you start the next one if you want the
printed ports to stay free.

## Hello API

`samples/hello-api` is a single file. It has a health route and a user
route that turns the path id into a number.

```yaml
--8<-- "samples/hello-api/ghostport.yml"
```

```bash
ghostport validate samples/hello-api
ghostport serve samples/hello-api
```

```bash
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:8080/users/7
```

```json
{"status": "healthy"}
```

```json
{"id": 7, "name": "Ada"}
```

A path that matches nothing returns 404:

```bash
curl -s -D - http://127.0.0.1:8080/missing -o /dev/null
```

The management status is on the other port:

```bash
curl -s http://127.0.0.1:8081/status
```

## Task Board

`samples/task-board` splits routes, scenarios, and state across files. The
root only names those files and the starting scenario.

```yaml
--8<-- "samples/task-board/ghostport.yml"
```

The initial state is one board value and one task:

```yaml
--8<-- "samples/task-board/state/tasks.yml"
```

The routes list, fetch, create, update, and delete tasks. They also read
and replace the board value. Send JSON with `Content-Type: application/json`.
A whole-value `"{{ body }}"` keeps the parsed object.

```yaml
--8<-- "samples/task-board/routes/tasks.yml"
```

```bash
ghostport validate samples/task-board
ghostport serve samples/task-board
```

```bash
curl -s http://127.0.0.1:8090/board
curl -s http://127.0.0.1:8090/tasks
curl -s -X POST http://127.0.0.1:8090/tasks \
  -H 'Content-Type: application/json' \
  -d '{"id":"2","title":"Review samples","done":false}'
curl -s http://127.0.0.1:8090/tasks/2
curl -s -X PATCH http://127.0.0.1:8090/tasks/2 \
  -H 'Content-Type: application/json' \
  -d '{"done":true}'
curl -s -X DELETE http://127.0.0.1:8090/tasks/1 -D -
```

Create returns 201 and the stored object. Update with `merge: true` keeps
`title` and changes `done`. Delete returns 204 and an empty body.

The closed scenario replaces only `list-tasks`. Tasks you already created
stay in state.

```yaml
--8<-- "samples/task-board/scenarios/closed.yml"
```

```bash
ghostport scenario set closed --url http://127.0.0.1:8091
curl -s http://127.0.0.1:8090/tasks
curl -s http://127.0.0.1:8090/tasks/2
ghostport scenario reset --url http://127.0.0.1:8091
curl -s http://127.0.0.1:8090/tasks
```

While the scenario is `closed`, `GET /tasks` returns 503 and
`{"error":"closed"}`. `GET /tasks/2` still returns the record.
`scenario reset` restores `normal`.

`state reset` puts the board back to the file's initial task and clears
sequence counters. This sample has no sequences.

```bash
ghostport state show --url http://127.0.0.1:8091
ghostport state reset --url http://127.0.0.1:8091
```

## Checkout

`samples/checkout` is the largest sample. The catalogue is a fixture file.
Orders live in SQLite. Payments follow a three-step sequence, and only
when the request has `x-shop: demo`. An audit route is configured to fail
before it writes state.

```yaml
--8<-- "samples/checkout/ghostport.yml"
```

```bash
ghostport validate samples/checkout
ghostport serve samples/checkout
```

The catalogue response is the fixture bytes:

```bash
curl -s http://127.0.0.1:8100/catalogue
```

```json
{
  "items": [
    {"sku": "mug", "name": "Blue mug", "price": 12},
    {"sku": "poster", "name": "Harbour poster", "price": 18}
  ]
}
```

Place an order. The body must be a JSON object and must include `id`.

```bash
curl -s -X POST http://127.0.0.1:8100/orders \
  -H 'Content-Type: application/json' \
  -d '{"id":"101","sku":"poster","qty":2}'
curl -s http://127.0.0.1:8100/orders
```

Stop the server and start it again. `GET /orders` still lists order `101`,
because the SQLite file is `samples/checkout/.ghostport/state.sqlite`.
Delete that file, or call `ghostport state reset --url http://127.0.0.1:8101`,
to restore the order seeded in `state/orders.yml`.

The payment sequence is `503`, then `200`, then `410`.

```yaml
--8<-- "samples/checkout/routes/payments.yml"
```

```bash
curl -s -X POST http://127.0.0.1:8100/payments \
  -H 'Content-Type: application/json' \
  -H 'x-shop: demo' \
  -d '{}'
curl -s -X POST http://127.0.0.1:8100/payments \
  -H 'Content-Type: application/json' \
  -H 'x-shop: demo' \
  -d '{}'
curl -s -X POST http://127.0.0.1:8100/payments \
  -H 'Content-Type: application/json' \
  -H 'x-shop: demo' \
  -d '{}'
```

```json
{"error": "busy"}
```

```json
{"paid": true}
```

```json
{"error": "Sequence exhausted"}
```

The same post without `x-shop: demo` does not match the route:

```bash
curl -s -D - -X POST http://127.0.0.1:8100/payments \
  -H 'Content-Type: application/json' \
  -d '{}'
```

That response is 404 and `{"error":"No checkout route matched"}`.

Reset the sequence without touching orders:

```bash
ghostport sequence reset take-payment --url http://127.0.0.1:8101
```

The next payment request is `503` again.

`POST /audit` is an action with `failure_status: 503`. The action does not
run, so the empty `audits` collection stays empty.

```bash
curl -s -D - -X POST http://127.0.0.1:8100/audit \
  -H 'Content-Type: application/json' \
  -d '{"id":"9","card":"4242"}'
ghostport state show --url http://127.0.0.1:8101
```

History keeps the request and stores the `card` field as `[redacted]`.

```bash
ghostport history list --url http://127.0.0.1:8101
ghostport history show REQUEST_ID --url http://127.0.0.1:8101
```

Replace `REQUEST_ID` with an id from the list. `random_seed` in this
project is stored with the configuration. It does not change any response.
