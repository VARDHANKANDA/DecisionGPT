# Decision record: who manages identity? (application-managed vs a hosted OIDC provider)

Status: **DECISION NEEDED before any internet-facing launch. Nothing is migrated by this record.** Date: 2026-10-21. It extends section 3 of
`PRODUCTION_SECURITY_REVIEW.md`, which explains why a provider was not integrated in the hardening pass.

## 1. What exists today (verified, not assumed)

| Aspect | Current state |
|---|---|
| Accounts | email + password held in the application database; public sign-up creates business accounts only; administrators and password resets are operator actions (`scripts/create_admin.py`, `scripts/reset_password.py`) |
| Passwords | Argon2id (RFC 9106), length 10–128, screened against very common choices; no breached-password lookup |
| Sessions | HS256 JSON Web Token (PyJWT) with `iss`, `aud`, `exp`, `iat`, `nbf`, `jti`; lifetime 12 h by default (60 s – 24 h enforced in hardened environments); **no refresh token** |
| Revocation | per token (`jti` list, written by `POST /auth/logout`) and per user (`token_version`: password change, sign-out of all sessions, operator reset, deactivation). Verified to survive restarts and to be shared by two server processes |
| Authorization | role and active flag read from the database on every request; tenants resolved from the URL and checked against `owner_user_id` |
| Abuse protection | database-backed rate limits on sign-in, sign-up and password change; nothing locks an account |
| Browser storage | the token is stored in `localStorage` |
| Not present | MFA, self-service password reset, email verification, social/enterprise sign-in, account-recovery channel, breached-password check, device/session list |

## 2. The two options

**A. Keep application-managed identity** and add the missing pieces ourselves (email verification, reset by email, MFA with TOTP/WebAuthn, session list,
breach check), optionally moving the token to an HttpOnly cookie.

**B. A maintained, hosted OpenID Connect provider** (a managed service or a self-hosted server such as Keycloak), using the authorization-code flow with
PKCE; the application verifies the provider's signed tokens and maps the provider's subject to a local user row that still owns businesses.

## 3. Comparison

| Criterion | A. Application-managed | B. Hosted OIDC provider |
|---|---|---|
| Operational complexity | Lowest *today* (already built and tested); grows with every feature added (mail delivery, reset tokens, MFA enrolment, lockout policy, audit trail) and each is security-critical code this team owns | One more dependency to configure and keep available (managed: a vendor and its availability; self-hosted: another service to patch, back up and secure). The application's auth code shrinks to token verification and subject mapping |
| Account recovery | Operator-only today. Self-service recovery needs a verified email channel, reset-token storage with expiry and single use, and abuse limits, all to be built and tested | Provided and maintained by the provider (email verification, reset, often recovery options); the application never handles reset tokens |
| MFA | Must be built (TOTP at minimum; WebAuthn better); enrolment, backup codes and recovery are the hard parts | Usually a configuration setting (TOTP, WebAuthn/passkeys, sometimes SMS); administrators can be required to use it |
| Revocation and logout | Strong for this application: instant, per token and per user, shared across replicas (tested) | Depends on the flow: short-lived access tokens plus provider-side session revocation; instant revocation of an already issued self-contained token needs introspection or short lifetimes. The existing `token_version`/`jti` mechanism could remain as a local second layer |
| Browser token exposure | `localStorage`: any script running in the page can read the token. A CSP limits where it could be sent but does not stop reading it. An HttpOnly, SameSite cookie removes script access but adds CSRF protection and a same-site deployment requirement | The protocol does not by itself fix this. Tokens obtained by a single-page app are again in script-reachable memory or storage. The strong pattern is a backend-for-frontend: the server holds the tokens and gives the browser an HttpOnly session cookie. That is possible with either option |
| Cost | No licence fee; engineering and maintenance time for every added feature | Licence or per-user/per-active-user fees for a managed service (verify current vendor pricing; not estimated here) or hosting and operations for self-hosted; plus integration time |
| Migration impact | None | Moderate: add a provider subject column, a first-login linking rule for existing accounts (email match is unsafe unless the provider has verified the email), password-hash import or forced reset, mapping administrators (the `admin` role must come from a provider group/claim or stay local), replacing sign-in/sign-up/change-password/logout in the frontend, and keeping tenant ownership (`owner_user_id`) stable |
| Data location / compliance | Credentials stay in the application database | Credentials and sign-in metadata live with the provider: check data residency and the privacy obligations that apply to the businesses' and their customers' data before choosing |
| Lock-in | None | Moderate for a managed service (user store, flows, tenant configuration); lower for self-hosted standards-based servers |
| Offline / local development | Works as is | Needs a local provider or a development bypass; the current "authentication off" local mode would need an equivalent that can never be enabled in a hardened environment |
| Security track record of the code | Home-grown flows over maintained libraries; reviewed and tested here only | Flows maintained, tested and monitored by specialists; the integration code (token verification, subject mapping) is still ours |

## 4. Assessment

* **For a controlled, internal, or small-pilot deployment**, option A is defensible as hardened today, with its gaps stated: no MFA, no self-service
  recovery, script-readable token storage.
* **For an internet-facing product with outside customers**, the missing capabilities (MFA, verified-email recovery, breached-password screening)
  are the ones most expensive and risky to build in-house, and are the ones a provider supplies. **Option B, with a backend-for-frontend session, is
  the recommended direction.** That is a recommendation for the decision-makers, not a decision.
* Do **not** describe `localStorage` as protected from XSS in any customer-facing material. Today's mitigation is partial (CSP, short lifetime,
  server-side revocation).

## 5. What a migration would require (an explicit plan, not started)

No authentication change or storage-model change may start until each of these exists and is agreed:

1. The chosen provider (managed or self-hosted), its availability target, and a data-residency review.
2. A written mapping: provider subject to local user, administrators, the first-login linking rule for existing accounts, and the fate of existing password hashes.
3. A session design: BFF with HttpOnly cookie (CSRF protection, same-site hosting, cookie flags verified over TLS) or another documented pattern.
4. A regression plan: the existing suites that prove tenant isolation, administrator separation, throttling, revocation and logout must pass unchanged, plus new tests for token verification (issuer, audience, signature, expiry, key rotation), linking, and provider outage behaviour.
5. A rollback path and a period where both sign-in methods work, with the old one removable by configuration.
6. A decision on the local development mode.

## 6. Triggers to revisit this record

Revisit before: the first launch to users outside the team; the first administrator account held by someone outside the team; any request for MFA,
single sign-on or an audit of sign-ins; any incident involving account takeover or token theft; the introduction of any feature that stores a
credential-equivalent in the browser; a change in the data the product holds that raises its sensitivity.
