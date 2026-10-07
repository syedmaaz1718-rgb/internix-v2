# Internix · Internship Hunter

Real feed-backed internship discovery with a Python + SQLite backend, responsive multi-page UI, accounts, saved internships and a self-reported application tracker. Built October 7, 2026. Brand selected by the owner. Trademark/domain availability has not been cleared. No fake job seeds, AI scores, invented salaries or fabricated counts.

## Start on your laptop
1. Install Python 3.11 or newer from python.org.
2. Extract the ZIP into a folder. Open that folder in VS Code.
3. Open Terminal → New Terminal.
4. Run `python server.py` (Windows) or `python3 server.py` (Mac/Linux).
5. Open http://localhost:8000 in Chrome.
6. Wait a few seconds for the first real API sync. No API keys are needed.

SQLite is created in `data/internix.sqlite3`. That file is the database, including real user accounts. Keep it private and back it up. The delivered package contains no user database, credentials or test accounts.

## What actually works
- Search roles/companies/skills; title-based domain labels; India/international/location/remote filters; pagination.
- Original-source job detail and application links. Users submit on the employer/source website, NOT through this server. No automatic application or resume upload.
- Hourly source refresh while the server runs. Successful refresh removes closed listings from search. Failed refresh retains cached listings, exposes source error and last successful refresh.
- Email/password accounts, real server-persisted signups, PBKDF2-SHA256 salted password hashes, HttpOnly session cookie, CSRF checks, login rate limiting, per-user data isolation.
- Server-backed saved roles and tracker notes/statuses. Guest items migrate into the account on signup/signin.
- Visible signup data notice, self-service account deletion, owner-only CLI for database stats, private account CSV export and backup. No unauthenticated public admin endpoint.
- All interface counts derive from the actual database. Missing salary/deadline is not invented.

## Current sources and limits
- Stripe employer board through the public Greenhouse job-board API.
- Groww employer board through the public Greenhouse job-board API.
- Rubrik, InMobi, Tower Research Capital, HackerRank, Databricks, Coinbase and Samsara employer boards through the same API.
- Arbeitnow free jobs API, mostly Europe, not an India-wide feed.
- Only titles explicitly containing `intern` or `internship` count. Domains use keyword rules, not an AI recommendation engine.
- Naukri/LinkedIn not scraped or integrated. Adzuna not connected (credentials required). Remotive not included (403 at feed check).
- Expanded checked snapshot: 459 internship titles, 21 in India (53 active sources: Greenhouse, Lever, Ashby public job boards plus Arbeitnow). Counts will change. A job in a current feed is not a guarantee it remains open or that a student is eligible. Check the original application page.
- Remote does not mean eligible from India. Read location/work-authorization requirements at the source.
- Selected sources only. Never claims to index every internship.

Source docs: https://docs.greenhouse.io/job-board.html and https://www.arbeitnow.com/blog/job-board-api . Public job-board GET endpoints are available without authentication. Before a commercial launch, independently review source terms/branding and any employer redistribution restrictions; public API availability is not a blanket legal certification.

## Beginner Render deployment
You deploy it yourself. These steps do not buy or provision a service automatically.

1. Create a NEW GitHub repository for Internix. Upload `server.py`, `manage.py`, `public/`, `requirements.txt`, `README.md`, `Dockerfile` and `.gitignore`. Do NOT upload `data/`, `.env`, exports or `node_modules`.
2. In Render choose New → Web Service → connect that repository.
3. Choose Python runtime. Build command: `python -m compileall -q server.py manage.py`. Start command: `python server.py`.
4. Add environment variable `HOST=0.0.0.0`. Render supplies `PORT`; the app reads it. Add `COOKIE_SECURE=1` for the HTTPS deployment.
5. For a quick UI test, a disposable free service can run the app, BUT IT WILL NOT KEEP A RELIABLE USER DATABASE after redeploy/restart. Do not accept real signups on disposable storage.
6. To keep actual signup data, choose a Render service that supports a persistent disk (this may cost money; inspect Render's current pricing yourself). Add a disk mounted at `/var/data` and set `DATABASE_PATH=/var/data/internix.sqlite3`. No priced plan is purchased by this package. An alternative is deploying on your own machine/server with a persistent local directory.
7. Deploy. Open your HTTPS URL. In Live sources verify all feed status/refresh dates. Try filters, save a role, create a disposable test account, log out/in, check that the save persists, then delete that test account.
8. Restart/redeploy and confirm the test data survives on the configured disk before inviting real users.

Scale/security note: this is a tested first build, NOT a public-startup security certification. It uses Python's standard HTTP server, suitable for local/review and limited beta behind hosting TLS, not a hardened public production server. Before a public launch, move request serving to a production WSGI/ASGI stack and review deployment security, multi-worker scheduling, distributed rate limiting and database scaling. Run one instance/worker with this SQLite build. Persistent storage is essential.

## Owner user database access
Use your server's private shell, not a public URL:
```
python manage.py stats
python manage.py export-users --output /var/data/users.csv
python manage.py backup --output /var/data/internix-backup.sqlite3
python manage.py delete-user --email someone@example.com
python manage.py sync
```
`export-users` exports email, account creation date and saved/tracked counts, NOT password hashes or private notes. Database backups contain private account data. Keep backups/exports out of GitHub and public links. Users should know your owner contact and privacy/deletion process before public launch.

## Tests
`python tests.py` runs backend tests in a temporary isolated database with explicitly fictional test-only fixtures. Tests never add jobs to the real runtime database. `npm ci && npm run test:browser` runs Chrome desktop/mobile UI smoke checks with Playwright (install Chrome or set CHROME_PATH). NPM packages are test-only. The deployed app does not need Node.

## Remaining launch work
- Email verification and password reset are NOT implemented; the UI says so. No OAuth.
- No admin dashboard UI; the owner CLI works.
- No native in-app third-party application submission, recruiter status sync, personalized ML matching, notifications or resumes.
- Persistent hosting setup, legal/privacy owner contact and terms, backup retention policy, external security review, production web serving, accessibility audit, Safari and real-device validation remain.
- Selected sources produce limited India coverage; adding more public employer feeds requires explicit board configuration, validation and terms review. No fake fallback when feeds are empty.

Hosting references verified October 7, 2026: https://render.com/docs/free , https://render.com/docs/disks , https://render.com/docs/web-services .

## Separate page routes
`/` Home, `/discover` Discover, `/saved` Saved, `/tracker` Application tracker, `/sources` Feed status and coverage, `/account` Signup/signin/account, `/internship/<source:id>` role details. These are distinct URL routes and direct reloads work; navigation is client-routed with shared header/sidebar, not separate server-rendered HTML templates.

Icons pop on mouse/touch press and Enter/Space. Reduced motion uses an outline instead of movement.

## Optional: Adzuna (India) listings

Off by default. To turn it on, add two environment variables on Render: `ADZUNA_APP_ID` and `ADZUNA_APP_KEY` (free key from https://developer.adzuna.com/signup). The app then fetches Adzuna India results (titles containing "intern") at most once every 6 hours (4 API calls per refresh, free limit is 250 per day). Without the keys nothing changes.
Adzuna's terms require a "Jobs by Adzuna" label on each listing; the app shows a text badge linked to adzuna.in. Swap in Adzuna's official logo image from their press page before launching publicly. A public app may need a licence from Adzuna later. Check https://developer.adzuna.com/docs/terms_of_service.
