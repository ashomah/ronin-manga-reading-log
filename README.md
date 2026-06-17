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
