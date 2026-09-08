# Power Hour Replay Automation

Auto-posts each Friday's Power Hour replay link to bianutrition.com/ph-replays.

## How it works

1. `replays.json` is the source of truth (seeded with all links from the old page)
2. A GitHub Action runs Fridays at 18:30, 19:00, 19:30, and 20:30 UTC (covers 2:30 PM ET
   year-round regardless of daylight saving, plus built-in retries). Power Hour itself
   runs Fridays 1:00 PM ET (~70 min), so the first slot lands after it ends.
3. The script POSTs to the Grain v2 API for a recording from the **most recent Friday
   (ET)** whose title contains "Power Hour" (the real title is "Coach Chelley's Power
   Hour"), pulls its `recording_url` share link, and appends `{date, url}` to the JSON.
   "Most recent Friday" rather than "today" because GitHub fires cron on low-traffic
   repos hours late — the 4:30 PM slot has landed at 11 PM ET, and could land on Saturday.
4. The workflow commits the change; the Squarespace code block fetches the raw JSON
   and renders the list. Page updates within ~5 minutes of the commit (GitHub raw CDN cache)

The script is idempotent: if that Friday's entry already exists, later runs exit quietly.
Extra cron slots are free retries in case Grain hasn't finished processing by 2:30.

## Stream Deck button (manual run)

`workflow_dispatch` runs (the Stream Deck button in `../streamdeck-actions`, or
"Run workflow" in the Actions tab) set `MANUAL=true`, which changes two things:

- It looks for the newest Power Hour in the **last 6 days** instead of the most
  recent Friday, so a press any time from Friday afternoon through the weekend works.
- "Nothing found" is a **failure** (exit 1, Slack `:hourglass:` note) instead of a
  quiet no-op. That's deliberate: the `check-manual-run` job makes the scheduled
  slots stand down when a *successful* manual run happened in the last 12 hours,
  so a press that came before Grain finished processing must not count.

Every run ends with a `RESULT: …` line; the button shows that line in its notification.

## Setup (one time)

Repo, push, workflow write-permissions, and the embed's `REPO` value are already
done — it lives at **https://github.com/MattBia/power-hour-replays** (public). Two
steps remain, both requiring secrets only you have:

1. Add the Grain token secret (repo → Settings → Secrets and variables → Actions):
   - `GRAIN_API_TOKEN_V2` — the exact same token value BIA's onboarding
     automation uses (it reads `GRAIN_API_TOKEN_V2` too). **Required.**
   - `SLACK_WEBHOOK_URL` — optional; posts success/failure notes to Slack.
2. Paste the whole `squarespace-embed.html` into a Code Block on the /ph-replays
   page, replacing the old manual list. `REPO` is already set to
   `MattBia/power-hour-replays`.

Then test: Actions tab → "Power Hour Replay Updater" → Run workflow. It reports
"Already posted" if the last 6 days' replay is on the page, posts it if not, and
fails with "No new recording in Grain yet" if there's nothing from the last 6 days.

## Notes / failure modes

- If the recording title doesn't contain "Power Hour", nothing posts and (if Slack is
  configured) you get pinged after the final 4:30 PM attempt. Manual fallback: add a
  line to `replays.json` and commit.
- If the recording isn't shared publicly in Grain, the script fails with a clear
  message rather than posting a dead link.
- The repo must be public for the Squarespace fetch to work. The JSON contains only
  share links that are already public on the website, so nothing sensitive is exposed.
  If you want a private repo, front it with a tiny Vercel endpoint instead.
