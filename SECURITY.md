# Security Policy

## Supported Versions

We actively support security updates for the latest `main` branch.

| Version | Supported |
| ------- | --------- |
| Main    | Yes       |

## Reporting a Vulnerability

Security is a top priority. If you discover a security vulnerability or credential leak issue, please do **NOT** open a public GitHub issue.

Instead, please report security issues privately:
- Contact the maintainer directly via GitHub or email.
- Provide detailed steps or proof of concept to reproduce the issue.

We will acknowledge receipt of your report promptly and provide an estimated timeline for remediation.

## API Key Security Guidelines

- **Never Commit Keys**: Do not commit `.env` files or hardcode `GEMINI_KEY` values into code or configuration files.
- **Environment Variables**: Always store API keys in local environment variables or private secret managers.
- **Git Ignore**: Ensure `.env` is listed in your `.gitignore` file before pushing commits.
