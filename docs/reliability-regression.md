# THE_X reliability regression — 2026-10-02

## Delivered implementation

- Restore the original internal route and query after reload and OIDC sign-in.
  Only allowlisted app paths are saved in tab-scoped auth storage; external URLs,
  callback codes, loading and unknown paths are rejected as return destinations.
  Existing role redirects still apply after restoration.
- Shop chat retries reuse a UUID for the same pending message within the current
  screen. Django migration `0011_message_request_id` adds a nullable UUID and a
  unique constraint over conversation, sender and request ID. A replay returns
  the existing message without another notification. Reusing the ID with a
  different body returns 400. Existing messages and legacy API clients remain
  compatible. This is not a persistent offline outbox: leaving/reloading the
  screen discards the pending client retry identity.
- Opt-in cursor pagination (`paged=1`, `before` or `after`) loads older shop
  messages (100/page) and AI turns (50/page). UI merges by ID, preserves older
  loaded records during refresh, and provides a load-earlier button. New shop
  arrivals are fetched after the most recent loaded ID. All pages retain the
  existing conversation ownership/membership checks. Conversation-list limits
  are unchanged; this change paginates messages within a conversation.
- When logout receives 401 for a revoked/inactive account, clear this tab's
  credentials and finish provider logout. Other server failures still surface
  as failures, rather than falsely claiming remote revocation succeeded.

## Automated evidence

- Django: 129 tests, 128 passed and 1 skipped (isolated synthetic n8n integration
  requires its explicit test environment). Executed against mounted current
  backend source with a separate test database; preserved with `--keepdb`.
- Flutter full suite: 30 passed on October 2; two additional history widget
  tests passed separately afterward (32 distinct passing tests total).
- Analyzer: no issues after implementation and style fixes.
- Backend and Flutter release Docker images built successfully. Migration 0011
  is applied; local stack restarted healthy on October 2.
- New coverage includes UUID replay/no duplicate notification, changed-body
  rejection, cursor boundaries, unauthorized history access, retry identity reuse,
  safe return paths, logout on 401, and history surviving polling/new arrivals.

## Browser evidence (September 30)

Chrome via the browser MCP tool, local Docker at `http://localhost:18080`:

- PASS: unauthenticated `/messages?conversation=2` → login/consent → same room.
- PASS: reload retains that room and query.
- PASS: shop room with 207 QA messages loads backward in two additional pages
  to the original two-line message. No earlier-load button remains at the start.
- PASS: customer profile save with backend deliberately unavailable displays
  a connection error and retains `QA Profile`. Retry after backend restart
  succeeds. Reload keeps `/profile` and the saved value.
- PASS: Flutter `/admin` loads for the QA administrator; its management button
  opens authenticated Django `/admin/auth/user/` with the new QA user visible.
- PASS: customer signup `qa-0930-signup` succeeds without an email and creates
  an active customer account. No existing user's password was changed.
- PASS: mechanic signup exposes shop fields; missing shop name and missing
  photo prevent submission.
- PASS: disabling the QA customer causes profile save to be rejected with a
  session-expired message. This exposed the logout-on-401 bug above.

## Browser evidence (October 2)

- PASS: with the QA customer temporarily inactive, clicking logout returns to
  `/login` instead of leaving the authenticated profile on screen. The QA
  customer was restored active immediately afterward.
- PASS: selecting the mechanic role reveals shop name, address, photo, and map.
  Entering `Bangkok, Thailand` in the address field places a map pin and shows
  the address-to-pin success message.
- BLOCKED: Chrome file chooser rejected the QA shop photo with `Not allowed`.
  The extension needs "Allow access to file URLs" before full mechanic signup
  and profile acceptance can proceed.
- READY FOR HANDOFF: the local password reset form is open with
  `qa-0930-signup` filled in. A browser-tool rule requires the user to enter
  and submit the new password personally.
- Route update before publication: Django Admin now owns `/admin` and `/admin/`;
  Flutter Admin moved to `/admin-dashboard` to avoid a proxy collision.

## Pending browser acceptance — do not mark complete

- Finish mechanic signup with the QA photo and map, then verify mechanic
  profile edits/reload. File chooser upload returned `Not allowed`; the Chrome
  extension needs "Allow access to file URLs". It was not bypassed.
- Finish password reset and sign-in with the new password. The reset form was
  opened for `qa-0930-signup`, but browser-tool policy requires the user to enter
  and submit a new password personally. No completion confirmation received.
  Backend reset validation/revocation tests passed; they do not replace this UI
  acceptance step.

## Fixture and operational notes

Only QA records were mutated. Existing fixture prefix is `qa-0929-680edb`;
customer signup is `qa-0930-signup`. The customer temporarily disabled for the
revocation test was restored active on October 2. The new QA administrator,
shop history, profile edit and customer signup remain for reproducibility.
Credentials and helper scripts stay in ignored `.local` files.

The outage test stopped only the local backend briefly, then restarted it.
It exercises unavailable API handling (502), not every network timeout or
browser-offline condition. Duplicate-after-timeout protection is verified by
client retry-ID tests plus server replay tests; no packet-loss claim is made.

## Debugging layers

- Root cause: route restoration discarded destinations; shop sends lacked a
  server-enforced replay key; fixed-size history omitted earlier messages;
  logout stopped before local cleanup on API 401.
- Environment cause: services were stopped between sessions; Chrome extension
  disconnected and file upload access was unavailable.
- Secondary cause: route fallback hid the intended destination, retrying after
  a lost response could create another message, and the expired-session message
  instructed logout even when logout itself could not complete.

## Reproduce automated checks

```powershell
cd D:\Project\Project_Flutter\mobiledev69\frontend
D:\flutter\bin\flutter.bat analyze --no-pub
D:\flutter\bin\flutter.bat test --no-pub --concurrency=1

cd D:\Project\Project_Flutter\mobiledev69
docker compose --env-file deploy/.env -f compose.deploy.yaml -f compose.ai.yaml run --rm --no-deps -e DB_CONN_MAX_AGE=0 -e REDIS_URL= -e LOCAL_USERNAME_RESET_ENABLED=false -v D:/Project/Project_Flutter/mobiledev69/backend:/source:ro -w /source backend python manage.py test garage --noinput --keepdb
```
