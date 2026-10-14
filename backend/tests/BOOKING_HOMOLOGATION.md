# Booking transaction homologation

## Local unit and HTTP-contract tests

These tests use in-memory collection/session fakes and never contact MongoDB:

```powershell
.\.venv\Scripts\python.exe -m unittest backend.tests.test_booking_rules_unit -v
```

They cover duration, work hours, tenant scoping, public routes without an admin
token, interval conflicts, and concurrent administrative/public requests.

## Real MongoDB replica-set tests

Use only a disposable MongoDB test replica set. Do not set this variable to the
application's `MONGO_URL`, Atlas production cluster, or any shared database.
The test module reads only `BARBERSTUDIO_TEST_MONGO_URL`; it does not fall back
to `MONGO_URL`. Before writing test data, it checks that `hello` reports a
replica-set name. Each test writes to its own random
`barberstudio_test_<uuid>` database. The suite does not drop these databases;
inspect and clean up only the disposable test databases using the test-cluster
administration process.

```powershell
$env:BARBERSTUDIO_TEST_MONGO_URL = '<URI de um replica set descartável de testes>'
.\.venv\Scripts\python.exe -m unittest backend.tests.test_booking_transactions_mongo -v
```

This suite covers simultaneous admin/admin and admin/public requests, tenant
isolation, and rollback of an uncommitted walk-in client. Transactions require
a replica set or sharded cluster; standalone MongoDB is intentionally skipped.

## Optional transaction failpoints

The retry tests require a disposable local/test replica set started with test
commands enabled and a test role permitted to run `configureFailPoint`. Do not
enable failpoints on production or shared clusters.

```powershell
$env:BARBERSTUDIO_TEST_MONGO_URL = '<URI de um replica set descartável com failpoints habilitados>'
$env:BARBERSTUDIO_TEST_MONGO_FAILPOINTS = '1'
.\.venv\Scripts\python.exe -m unittest backend.tests.test_booking_transactions_mongo -v
```

The failpoint cases inject one transient insert error and one unknown commit
result, then assert one committed appointment. Failpoints are disabled in each
test's `finally` block.

## Public link and Vercel

The React route is `/agendar/:slug`; the backend returns `/agendar/{public_slug}`
and the panel resolves it against the current browser origin. `vercel.json`
serves the SPA fallback for direct route loads, and the Vite output directory
matches the configured static build directory (`build`).

The repository does not contain a confirmed production domain or Vercel
Deployment Protection setting. Preview deployments can be protected by external
Vercel project settings; validate the public URL on the intended production
deployment without disabling protection on other projects. The panel link uses
the active origin, so copy/share it from the public deployment users should
open.