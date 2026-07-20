# Power Hour Replay Automation

Auto-posts each Friday's Power Hour replay link to bianutrition.com/ph-replays.

## How it works

1. `replays.json` is the source of truth (seeded with all links from the old page)
2. A GitHub Action runs Fridays at 18:30, 19:00, 19:30, and 20:30 UTC (covers 2:30 PM ET
   year-round regardless of daylight saving, plus built-in retries). Power Hour itself
   runs Fridays 1:00 PM ET (~70 min), so the first slot lands after it ends.
3. The script POSTs to the Grain v2 API for a recording from today whose title contains
   "Power Hour" (the real title is "Coach Chelley's Power Hour"), pulls its
   `recording_url` share link, and appends `{date, url}` to the JSON
4. The workflow commits the change; the Squarespace code block fetches the raw JSON
   and renders the list. Page updates within ~5 minutes of the commit (GitHub raw CDN cache)

The script is idempotent: if today's entry already exists, later runs exit quietly.
Extra cron slots are free retries in case Grain hasn't finished processing by 2:30.

## Setup (one time)

1. Create a repo (public is easiest — raw.githubusercontent.com fetch requires no auth)
   and push these files
2. Repo Settings → Secrets and variables → Actions:
   - `GRAIN_API_TOKEN_V2` — the exact same token value BIA's onboarding
     automation uses (it reads `GRAIN_API_TOKEN_V2` too)
   - `SLACK_WEBHOOK_URL` — optional; posts success/failure notes to Slack
3. Repo Settings → Actions → General → Workflow permissions → "Read and write permissions"
4. In `squarespace-embed.html`, set `REPO` to your `username/repo`, then paste the whole
   file into a Code Block on the /ph-replays page (replacing the manual list)
5. Test: Actions tab → "Power Hour Replay Updater" → Run workflow. On a non-Friday it
   just won't find a recording and exits cleanly; on a Friday after 2 PM it should post

## Notes / failure modes

- If the recording title doesn't contain "Power Hour", nothing posts and (if Slack is
  configured) you get pinged after the final 4:30 PM attempt. Manual fallback: add a
  line to `replays.json` and commit.
- If the recording isn't shared publicly in Grain, the script fails with a clear
  message rather than posting a dead link.
- The repo must be public for the Squarespace fetch to work. The JSON contains only
  share links that are already public on the website, so nothing sensitive is exposed.
  If you want a private repo, front it with a tiny Vercel endpoint instead.
