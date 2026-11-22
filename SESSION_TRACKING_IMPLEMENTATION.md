# Photo index and client tracking

Photomatic stores the photo index, client selection state, and cache-service health
in `photomatic_cache.sqlite3` under the configured cache directory.

The cache service rebuilds the photo index at container startup and each midnight.
During each build it classifies photos matching today's month and day (across
years) separately from the general photo pool. Requests select from the completed
SQLite index; they never scan the photo directory or rebuild it. A temporary
SQLite database is used while scanning, then the index is atomically replaced.

Client state is keyed by a SHA-256 hash of Flask's `request.remote_addr`, so the
raw IP is not stored in the tracking table. Requests from one IP share selection
state, which expires after 48 hours without activity. Behind a reverse proxy,
Flask normally sees the proxy IP unless trusted proxy forwarding is configured.

The cache service writes a heartbeat, build status, and last error to SQLite.
`/healthcheck` reports whether the service is alive and the index is current.
Random-photo routes return `503` while the service is rebuilding.

`/clear_cache` clears the photo index and all client tracking state. To reset
manually, stop Photomatic and delete `photomatic_cache.sqlite3`; the entrypoint
rebuilds it before starting Gunicorn.
