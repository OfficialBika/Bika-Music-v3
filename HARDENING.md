# V4 production hardening

V4 is built from the Bika-Music-v3 codebase, with AnonMusic's production-hardening patterns ported while retaining Bika's UI and data fields.

## Safety controls
- `ENABLE_EVAL=False` by default; owner eval/exec requires explicit opt-in.
- `PLAYBACK_RETRY_LIMIT` and `PLAYBACK_SKIP_LIMIT` bound recovery work.
- YouTube IDs are validated, TLS certificate checking remains enabled, concurrent downloads of one track are serialized, and output files are checked.
- Broadcast retries FloodWaits within a bounded limit, reports failures, and only auto-leaves groups when `BROADCAST_AUTO_LEAVE=True`.
- Legacy Mongo migration defaults to dry-run, validates identifiers, writes a migration plan and never drops/replaces live collections. Staging is blocked unless `MIGRATION_CONFIRM_APPLY=I_HAVE_VERIFIED_BACKUP`.

## Mongo migration limitations
The migration plan is not a MongoDB backup. Before staging, take and verify an external backup using `mongodump` and test restoring it. The migration writes only to `users_migration_new` and `chats_migration_new`; it intentionally does not cut over live collections and does not claim automatic rollback. Inspect and validate staged data before any manual cutover.

## Verification status
Unit tests cover queue safety, config defaults and migration guards. CI additionally compiles the code, performs an import smoke test, and builds the Docker image. Live Telegram group-call, real YouTube download, disposable MongoDB integration, race/concurrency stress and backup-restore tests are still required before production deployment.
