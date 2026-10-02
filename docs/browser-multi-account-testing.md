# THE_X: browser multi-account verification

Tested 2026-09-29 (Asia/Bangkok), Chrome, Docker application at
`http://localhost:18080`. Flutter release build uses Flutter 3.44.2.
Browser interactions used the MCP browser tool. Database reads corroborated
persisted results; the booking transitions and chat sends were performed in UI.

## Accounts and scope

Three dedicated, persisted local QA accounts use prefix `qa-0929-680edb`:
customer, mechanic, and outsider (another customer). These are actual accounts
in the local PostgreSQL database, not mocked authentication. Existing users'
passwords were not changed. Generated credentials remain in ignored `.local`
files and are not included here.

QA shop 2, motorcycle 2, conversation 2, and booking 2 isolate test activity
from existing shops and customers. Fixtures remain for reproducibility; this
run did not delete them. The QA shop may appear in the local shop list.

## Passed browser scenarios

- Customer and mechanic signed in through Django OIDC in separate tabs of the
  same Chrome profile. Reload retained the appropriate account. A new tab
  presented login rather than inheriting another tab's Flutter session.
- Customer sent a shop message with Enter. Mechanic received an unread badge
  and in-app notification; opening it reached the correct conversation and
  cleared its unread count.
- Mechanic sent a two-line reply using Shift+Enter followed by Enter. Customer
  received and opened it. PostgreSQL contains exactly the two intended messages
  (IDs 4 and 5), with the newline preserved and no duplicate send.
- Outsider signed in independently: message list was empty, with zero unread
  notifications and no QA conversation visible. This is UI isolation evidence,
  not a complete authorization penetration test.
- Customer created booking 2 for the QA shop and motorcycle, 2026-09-30 09:00.
  Mechanic received its new-booking notification.
- Mechanic accepted, started, and completed booking 2 through confirmation
  dialogs. Customer received a notification for every transition. Final UI and
  database status are `completed`; repair notes explicitly identify a test.
- Individual notification reads and mechanic's "read all" persisted. Final
  fixture audit found all six notifications read. Reload retained zero unread
  for the mechanic.
- Customer logout returned that tab to login. Mechanic reload still showed
  the authenticated jobs page and completed booking: logout isolation passed.

## Bug found and fixed

Root cause: opening a booking notification while already at `/bookings`
retained the route's BookingViewModel, leaving the old status on screen.

Environment cause: no Docker or database fault was found for this issue.

Secondary cause: notification polling and read-state updates worked while the
booking list remained stale, creating contradictory visible states.

NotificationBell now reloads an existing BookingViewModel when opening a
booking notification. Navigation from other pages still loads via the route.
Added `frontend/test/booking_notification_test.dart` to cover opening a
notification on the same route. Rebuilt and restarted only the local web
container. Browser retest: customer remained on `/bookings` showing in-progress,
mechanic completed the job, then opening the completion notification changed
the list to completed without a manual reload.

## Validation and limits

- Targeted Flutter tests: 7 passed (booking notification and messages suites).
- `flutter analyze --no-pub`: no issues.
- Docker Flutter release web build passed; updated container is running.
- `git diff --check`: passed (Windows line-ending warnings only).
- No captured browser console errors in the mechanic tab at final check.
- This run did not test Admin UI, signup/reset, mobile hardware, load/concurrency
  at scale, external deployment, or a real Gemini response. No claim of full
  application acceptance is made.
- Notifications are in-app polling while foreground, not background Web Push.
  Booking lists require notification opening or their refresh action to fetch
  changes; this fix does not introduce continuous live status refresh.

Re-run the targeted automated checks from `frontend`:

```powershell
D:\flutter\bin\flutter.bat test --no-pub test/booking_notification_test.dart test/messages_test.dart
D:\flutter\bin\flutter.bat analyze --no-pub
```
