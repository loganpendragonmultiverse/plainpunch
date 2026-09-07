# Changelog

All notable changes follow [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and semantic versioning.

## [1.0.0] - 2026-08-03

### Added

- Employee web sign-in, explicit shift and break punches, and personal history.
- Shared kiosk with employee code and PIN authentication.
- Correction requests with administrator approval, rejection, and before/after audit evidence.
- User creation, CSV export, UTC storage, configurable timezone display, Docker deployment, and health check.
- CSRF protection, scrypt credentials, secure-cookie controls, community files, tests, CI, CodeQL, and release automation.

[1.0.0]: https://github.com/loganpendragonmultiverse/plainpunch/releases/tag/v1.0.0


## Version 1.1.0: reviewed improvements

Add local-date daily/weekly summaries, configurable CSV exports, overlap-safe corrections and revocable administrator sessions.

Admin → Work summaries selects inclusive date ranges (maximum 366 days), daily or Monday-start weekly grouping, CSV columns and separators. UTC interval clipping handles daylight-saving days; breaks and overlapping work are counted once. Correction requests reject invalid/ambiguous wall times, overlapping shifts and duplicate pending requests, with approval-time overlap revalidation. Explicit offset ISO input resolves repeated hours. Punch and correction approval writes serialize through SQLite. Administrator idle expiry and per-user session revocation preserve accounts and audit events. A forward migration adds session_version without removing data. Deployment guidance covers HTTPS, secure cookies, trusted proxies and rate limits; no proxy deployment is claimed. This is a time summary, not a payroll rules engine.

See [deployment controls](docs/deployment-controls.md). Validation includes strict typing, the complete test suite and the 90% coverage gate.
