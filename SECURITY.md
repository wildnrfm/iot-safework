# Security

## Reporting

Do not publish credentials or sensitive camera data in public issues.
Report security problems privately to the repository maintainer.

## Local deployment

SAFEWORK binds to `127.0.0.1` by default. Set `SAFEWORK_ADMIN_TOKEN` before allowing profile changes or
indicator tests. The token is read by the process and must not be committed to source files.

Do not expose the unencrypted dashboard to a network or the internet. It does not provide user authentication,
TLS, multi-user authorization, or audit-grade tamper protection.
