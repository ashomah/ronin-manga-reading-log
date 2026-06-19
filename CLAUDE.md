# CLAUDE.md — Rōnin manga tracker

Context for resuming work on this project with Claude Code. Read this first.

## What this is

A single-file manga reading tracker (`index.html`) for a French/English reader
who is new to manga and leans seinen / sci-fi / cyberpunk / dark. It tracks an
owned collection plus a curated suggestions list, with per-series edition
choice, owned-vs-read progress, ratings, a buy list with budget, and
cross-device sync via a private GitHub Gist. Hosted on GitHub Pages.

The app UI is in **English**. Manga edition data (publishers, formats) is
factual and may reference French editions by name.

## Repo contents

- `index.html` — the entire app (HTML + CSS + JS in one file). Must stay named
  `index.html` at repo root for GitHub Pages.
- `README.md` — user-facing setup/usage.
- `CLAUDE.md` — this file.
- `digest.py` — monthly Slack digest (NOT part of the web app). Parses the SEED
  catalog from `index.html` and your synced Gist progress, diffs against last
  month's snapshot, and posts new suggestions / release-date changes / newly
  released volumes / reading progress to Slack. Run `python digest.py --dry-run
  --html index.html --state <data.json> [--snapshot <prev.json>]` to preview.
- `requirements.txt` + `.github/workflows/monthly-digest.yml` — the monthly cron
  that runs `digest.py`.

The **web app** has no build step, no dependencies, no framework — open
`index.html` in a browser and it runs. The **digest** is the only Python: it
depends on the private `ashomah/automation-core` lib (shared with the `level-up`
project) for generic Slack/GitHub/Gist plumbing; all manga-specific logic
(SEED parsing, diffing, wording) stays in `digest.py`. See the
`automation-core-shared-repo` memory.

### Monthly digest specifics
- Snapshot is stored as `ronin-digest-snapshot.json` inside the **same private
  Gist** as `ronin-data.json` (via `automation_core.github.update_gist`), so the
  repo stays clean and there's no last-write-wins conflict with the app (which
  only ever writes `ronin-data.json`).
- "Available volumes" per series = the **recommended** edition's `vols` (else the
  first edition's). A bump month-over-month = "new volume released".
- Required Action secrets: `SLACK_WEBHOOK_URL`, `RONIN_GIST_ID`,
  `RONIN_GIST_TOKEN` (classic PAT, `gist` scope; add `repo` only if this repo is
  ever made private), `AUTOMATION_CORE_TOKEN` (read access to the private
  automation-core repo — can be the same PAT if it has `repo`).

## Architecture (important)

**Code vs. data separation is the core design principle.**

- **Catalog** (which series exist, their editions, prices, blurbs, release
  dates) is hard-coded in the `SEED` array inside `index.html`. Editing the
  catalog = a code change = a commit.
- **User data** (per-series: edition index, owned count, read count, rating,
  buy flag, custom image URL) lives in browser `localStorage` and syncs to a
  private GitHub Gist named `ronin-data.json`. Never committed to the repo.
- Everything is keyed by a stable series `id`. **Never rename or reuse an
  existing `id`** — it orphans that series' user data. Add new ids, deprecate
  old ones.

Catalog edits (adding/fixing series) never disturb the user's progress, because
progress is keyed by id and stored separately.

## Key code regions in index.html

- `<style>` — design tokens at `:root` (ink/washi/cinnabar/jade/gold palette,
  Japanese woodblock-print feel). Cards, progress bars, sync bar, started-series
  panel, buy-list styles.
- `SEED = [ ... ]` — the catalog. Two sections via `section:"shelf"` (owned) or
  `section:"wishlist"` (suggestions). Each entry: `id, section, t (title), a
  (author), g (genres[]), status ("read"|"reading"|"todo"), series
  ("complete"|"ongoing"), blurb, art ([color1,color2] for the generated cover
  motif), editions[], optional nextDate, optional verify:true (release date
  needs live check)`.
  - Each edition: `{name, vols, price, mins (read minutes/vol), optional
    recommended:true, optional note}`.
- Schema & migrations: `CURRENT_SCHEMA`, `MIGRATIONS{}`, `migrate()`,
  `restoreBackup()`. Data carries `__schema`; migrations run on load, on gist
  pull, and on JSON import, writing a reversible backup before mutating.
  **To change the data shape: bump `CURRENT_SCHEMA` and add a `MIGRATIONS[n]`
  function (vN-1 → vN).** Current schema = 2 (added `rating`).
- Sync engine: `gh()`, `schedulePush()`, `pushNow()`, `pullNow()`,
  `setupSync()`. Classic GitHub token with **only `gist` scope**; token + gistId
  in localStorage per device. Timestamp-based (`__updatedAt`) last-write-wins
  with a "local is newer" warning.
- `rec(id)` — gets/creates a user-data record with defaults
  `{ed, owned, read, img, rating, buy}`. Read defensively here when adding
  fields.
- Helpers: `owned(m)`, `read(m)` (read is clamped ≤ owned), `curEd(m)`.
- `render()` — builds cards, injects section headers in "all" view. Each card:
  cover motif, badges, blurb, rating stars, buy tickbox, edition `<select>`,
  recommended-edition note, owned bar (+/-), read bar (read vs owned, +/-),
  series-journey bar (read vs full series, with owned "ghost"), meta grid.
- `renderStats()` — header: volumes read / owned, collection value
  (owned × price), time spent reading (read × mins), buy budget (ticked series:
  (vols-owned)×price). Then calls `renderStarted()`.
- `renderStarted()` — "Series in progress" panel: series with read>0 and
  read<total, sorted by % read.
- Seed IIFEs at the bottom:
  - `seed()` guarded by `__seededV2` — fills initial real inventory from the
    `INV` map.
  - `seedBerserk()` guarded by `__seedBerserk` — example of an **additive**
    one-time seed that runs after initial seeding without overwriting edits
    (only sets values if the record is still untouched). Use this pattern to
    add a series with known owned/read state without disturbing existing data.

## User's current inventory (as seeded)

Shelf (owned): Dragon Ball (digital colour, read), Ghost in the Shell (EN 2nd
ed, 3 vols, read), Gantz (Perfect Ed, 24 owned), Blame! (Master Ed, 1 owned),
One Piece (classic Glénat, 1 owned), Akira (large B&W, 6, read), Berserk
(classic Glénat, 42 owned / 41 read), FMA (user was moving this to wishlist).

Suggestions/wishlist: Dragon Ball Super, Naruto, Vagabond, Vinland Saga,
Monster, Pluto, Biomega/NOiSE, Dorohedoro, Blade of the Immortal (L'Habitant de
l'infini).

Buy list pre-ticked: fma, naruto, dbsuper.

**Known TODO:** real read counts for Gantz, Blame!, One Piece were left at 0 and
the user still needs to set them (or tap the read +/- in the app). The user was
mid-edit moving FMA from shelf to wishlist.

## Verified facts (as of mid-2026, may need re-checking)

- Vinland Saga: completed, 29 vols, final vol 13 May 2026 (Kurokawa).
- One Piece: ongoing, 112 vols out FR, vol 113 on 23 Sep 2026, ~150 targeted.
- FMA best edition: Kurokawa Perfect Edition, 18 vols, ~€11.95/vol (~€215).
- Dragon Ball Super: ~24 vols, publication on pause.
- Naruto: complete, 72 vols.
- Berserk: ongoing, continued by Studio Gaga post-2021, slow release.
- Vagabond: on hiatus since 2015.

Series flagged `verify:true` (release dates to re-check live): berserk,
onepiece, dbsuper, vagabond, and any ongoing additions.

## Conventions / gotchas

- Pure vanilla JS, no framework. Keep it single-file.
- Watch for nested double-quotes inside JS string literals when editing
  blurbs/notes (broke the build once — use single quotes inside, e.g.
  `'next DB series'`).
- Section headers render only in "all" view with no search active. Keep shelf
  entries before wishlist entries; `SEED` is stable-sorted by section.
- After any structural edit, sanity-check the `<script>` parses before
  committing.
- Don't add real copyrighted cover art to the catalog; use the generated `art`
  motif and let the user paste their own image URLs.

## Likely next tasks

- Set real read counts for Gantz / Blame! / One Piece.
- Finish/verify the FMA shelf→wishlist move (and decide if it stays buy-list
  ticked).
- Periodic "release date pass" on `verify:true` series (live search, update
  `nextDate`).
- Add/correct series as the collection grows (use the additive-seed pattern for
  known owned/read state).
- Optional: app icon + manifest for "Add to Home Screen" on phone.
