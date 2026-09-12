# Rōnin — manga reading log

A single-file manga reading tracker. Pick the edition you own for each series,
track **owned** and **read** volumes separately, watch your collection value and
reading time add up, keep a buy list with its own budget, and follow your
progress across the series you've started. Data syncs across devices via a
private GitHub Gist.

> *Rōnin* (浪人) — a masterless samurai who wanders and finds their own path.
> The seal reads 読 (*yomu*, "to read").

## Live app

Once GitHub Pages is enabled (see below):
`https://<your-username>.github.io/<repo-name>/`

## Features

- **My collection vs. Suggestions** — two sections: what you own, and curated
  picks to explore.
- **Edition picker** — each series lists its real editions; pick the one you own
  and price, volume count, cost and reading time adjust. A ★ marks the
  recommended edition even when it isn't the one you have.
- **Owned vs. read** — separate counters and bars. You can't mark more read than
  owned.
- **Series journey** — a third bar showing how far you've read into the *whole*
  series (e.g. 1/112 for One Piece), not just what you own.
- **Series in progress panel** — every series you've started but not finished,
  with its journey bar, sorted by progress.
- **Buy list** — tick a series to add its remaining cost to your buying budget;
  un-ticked suggestions don't count.
- **Header stats** — volumes read (vs owned), collection value, time spent
  reading, and buy-list budget.
- **Ratings** — 1–5 stars per series.
- **Cover motifs** — a generated banner per series; paste your own cover image
  URL to override it.

## How data works

- The **code** lives in this repo (served by GitHub Pages).
- Your **reading data** lives in a private GitHub **Gist**, not in this repo.
- Each device stores its token + gist id in its own browser localStorage — the
  token is **never** committed here.

This means you only commit `index.html` when the *app* changes. Your day-to-day
owned/read/rating/buy-list data never touches the repo.

## Files

- `index.html` — the app (must be named exactly this, at the repo root).
- `README.md` — this file.

## One-time sync setup (per device)

1. Create a GitHub token: **Settings → Developer settings → Personal access
   tokens → Tokens (classic) → Generate new token (classic)**.
2. Check **only** the `gist` scope. Generate and copy the token (shown once).
3. Open the app, click **⚙ Set up sync**, paste the token. The app finds or
   creates a private gist named `ronin-data.json` and syncs.

Repeat step 3 on each device (phone, laptop) with the same token. The app
auto-pulls newer data on open and pushes your changes after each edit.

## Enabling GitHub Pages

Repo **Settings → Pages → Source: Deploy from a branch → `main` / `(root)` →
Save**. Your URL appears after ~1 minute.

## Backups & data model

- **Export / Import (JSON)** buttons give you a portable backup any time.
- The data carries a schema version and self-migrates when the model changes,
  writing a reversible pre-migration snapshot first (**Restore** button undoes
  the last migration).

## Security notes

- Keep the token private and give it an expiration — anyone with it can
  read/write your gists.
- A private gist is unlisted, not encrypted. Fine for reading progress.
- The Pages URL is public (shows the app), but your data only appears in a
  browser that has your token.

## Troubleshooting

- **URL 404s** → the file isn't named `index.html` at the repo root, or Pages
  hasn't finished building.
- **Sync dot won't turn green** → the token is missing the `gist` scope;
  regenerate with that box checked.

## Incident alerts → `#incidents`

Both automations here fail quietly by nature. The digest runs **twelve times a
year**, so a broken month is invisible until the next one is due. The catalog
update is triggered from a button in the app, where the person who pressed it
never sees the Actions tab and a run that changed nothing looks exactly like a
run that worked.

Alerts go through [`automation_core.alerts`](https://github.com/ashomah/automation-core)
to the shared `#incidents` Slack channel, which this repo, `level-up`,
`career-coach` and `job-search-agent` all post into. Every alert names its
process, links the failing run, and says what to do.

### What alerts

**`Monthly digest (Slack)`** — cron `0 8 1 * *`

| Alert | Severity | Trigger | Why it is invisible otherwise |
|---|---|---|---|
| Crashed | 🔴 | Any unhandled exception in `digest.py` | Twelve runs a year — a red tick goes unseen for a month |
| `RONIN_GIST_ID` is not set | 🔴 | The secret is missing or was rotated | Exits 2 with no Slack message at all |
| Parsed zero series from the catalog | 🟠 | `parse_catalog()` returned nothing | The catalog is scraped out of `index.html`; a markup change breaks it silently and the digest reports an empty library |
| Workflow failed before the digest ran | 🔴 | checkout / pip / runner failed | Never reaches Python |

The snapshot is only advanced *after* a successful post, so a failed month
re-runs cleanly and still produces the correct diff.

**`Catalog update (Claude)`** — `repository_dispatch` from the app, or manual

| Alert | Severity | Trigger | Why it is invisible otherwise |
|---|---|---|---|
| **Ran and changed nothing** | 🟠 | Claude finished and left no edits to commit | Triggered from the app, where this is indistinguishable from success. Usually means it hit `--max-turns 60` |
| Catalog update failed | 🔴 | The Claude run or the commit step failed | `index.html` is unchanged on main and nobody is told |

### Secrets this needs

| Secret | For |
|---|---|
| `SLACK_WEBHOOK_URL` | The digest channel |
| `SLACK_ALERT_WEBHOOK_URL` | The shared `#incidents` channel. Same value in every repo |
| `AUTOMATION_CORE_TOKEN` | Reading the private `automation-core` repo from CI |
| `RONIN_GIST_ID`, `RONIN_GIST_TOKEN` | The private gist holding reading data |
| `ANTHROPIC_API_KEY` | The catalog update |

⚠️ **This repo is public.** Secrets are not exposed to forks, but keep alert
*text* free of anything private — alerts name the process and the failure, never
reading data or gist contents.
