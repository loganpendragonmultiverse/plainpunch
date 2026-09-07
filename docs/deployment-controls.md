# Session and request controls

Use a stable, private `PLAINPUNCH_SECRET_KEY`, HTTPS, and `PLAINPUNCH_SECURE_COOKIES=1` in production. Signed sessions expire after eight hours. Administrators also expire after 900 idle seconds by default; set `PLAINPUNCH_ADMIN_IDLE_SECONDS` to a positive deployment-specific value. The People screen can revoke all current sessions for a person without deleting their account; they can sign in again. Session revocation uses the SQLite user revision and therefore applies across app workers. Migration adds `users.session_version` with default zero and preserves existing rows. Revocation does not disable kiosk PIN access.

Place rate limits at the trusted reverse proxy for both `/login` and `/kiosk`. Example Nginx configuration fragments, to adapt and validate with `nginx -t`:

```nginx
# http context
limit_req_zone $binary_remote_addr zone=punch_auth:10m rate=10r/m;

# inside the HTTPS server block
location ~ ^/(login|kiosk)$ {
    limit_req zone=punch_auth burst=10 nodelay;
    limit_req_status 429;
    proxy_pass http://127.0.0.1:8080;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

Shared kiosk users share an IP budget, so choose capacity for the real shift-change load. Keep the app port private so clients cannot bypass the proxy. Trust forwarded client addresses only from your own proxy; never use arbitrary client headers as a limit key. These examples are deployment guidance; the application does not implement a distributed login limiter, and this release did not deploy or test an Nginx instance.

Work summaries use inclusive local dates, with Monday-start weeks. They clip intervals at local midnight in UTC, so transition days may contain 23 or 25 hours. Break intervals and duplicate work intervals are merged to avoid double counting. Original records remain unchanged. Reports include open shifts through report time. No pay, overtime, compliance or payroll-provider rules are inferred. CSV columns and comma/semicolon separators are selected explicitly; potentially executable spreadsheet strings receive a leading apostrophe.
