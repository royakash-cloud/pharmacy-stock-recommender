# Monthly Retrain Routine

1. Copy the new month's purchase export (`.xlsx` or `.xls`) into
   `data/raw/`. Keep the older files there too — `generate.py`
   reloads and recombines every file in that folder each run.
2. Run:
   ```
   .\retrain.ps1
   ```
3. Review the log output it prints: confirm the anchor month matches
   the most recent month in your new export, the product count looks
   reasonable, and there are no `WARNING` lines (e.g. a file that
   wasn't loaded because of an unsupported extension).
4. If it looks correct, publish it yourself:
   ```
   git add docs/schedule.json
   git commit -m "Retrain -- <month> <year> data"
   git push
   ```
   GitHub Pages auto-redeploys within a minute — refresh the phone page.

If `retrain.ps1` reports that `generate.py` failed, stop there — fix
the underlying issue first. Nothing gets committed on a failed run.

## Why the git push step isn't automated

`retrain.ps1` stops after showing the log instead of committing and
pushing for you. A retrain can finish with exit code 0 and still have
used the wrong data — that happened once already, when a new export
was silently skipped because of a file-extension mismatch (see
`ENGINEERING_LOG.md` §4). A clean exit code doesn't catch that kind
of mistake; a human glancing at the anchor month and product count
does. Once `git push` runs, GitHub Pages redeploys within a minute
and the new schedule is what's live on your phone — that's worth
keeping as a deliberate, manual "yes, I checked this" action rather
than something a script does silently on your behalf.
