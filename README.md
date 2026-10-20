# Factual Daily

A quiet, responsive news directory with attributed publisher headlines and official releases. Published at https://toddmac12.github.io/factual-daily/ once deployment succeeds.

## Editorial rules

- Preserve the original publisher's headline, publication timestamp, and article link. Clearly label publisher reports versus agency releases. Official releases represent the issuing institution's account.
- No generated summaries, invented facts, political commentary, truth scores, or claims of guaranteed neutrality.
- Exclude items whose titles, categories, or URL paths identify opinion, editorial, analysis, commentary, sponsored content, reviews, podcasts, and related formats. Also exclude question headlines and several explainer/live formats. This conservative heuristic can omit reporting and miss unlabeled opinion. Inclusion is **not independent verification**.
- Only use configured open publishers. Check every article’s public HTML for readable article-body content, paywall wording, and structured metadata that marks access as paid. Omit failures, restricted pages, and pages whose free access cannot be confirmed. Recheck every day; hide links after 36 hours without a new check. Never log in, bypass a gate, use an archive proxy, or copy article text to work around access restrictions. Access checks reflect the collector’s region and time, not a guarantee of future worldwide access.
- Keep only dated articles published in the preceding seven days. Reject unknown dates, future dates, insecure URLs, and URLs outside the configured publisher domains. Deduplicate canonical article URLs and sort by publication time; the lead item is the newest item, not an editorial ranking.
- Publish no article bodies, descriptions, photos, or logos. Article HTML is inspected transiently for access checks and never saved or republished. Link prominently to each original publisher. No ads or tracking. Review publisher feed terms before commercial reuse; this project does not grant reuse rights.
- Current coverage is limited to PBS News and Al Jazeera reporting, NASA releases, and Federal Reserve press releases. BBC News has been removed because article access can be restricted. It is not comprehensive or a balance assessment. Edit `sources.json` to change the source selection.

## Run locally

Python 3.13+; no third-party dependencies or API keys.

```sh
python -m unittest discover -s tests -v
python scripts/collect.py
python -m http.server 8000 --directory site
```

Visit http://localhost:8000. Search and topic/source filters run locally in the browser. All news requests run in the collector; no RSS CORS proxy is needed. External article links open in a new tab.

## Daily collection and deployment

`.github/workflows/daily.yml` runs on pushes to `main`, manual dispatch, and daily at **10:17 UTC** (6:17 a.m. Eastern during daylight time; 5:17 a.m. during standard time). GitHub schedules can be delayed. Public repository schedules may be disabled after 60 days without repository activity; check Actions if refreshes stop. See [GitHub schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

The workflow tests the collector, collects live feeds, commits `site/data/news.json`, checks the public article pages, uploads only `site/`, then deploys that artifact to Pages in the same workflow. A commit made by `GITHUB_TOKEN` does not need to trigger another workflow. Repository settings must have Pages source **GitHub Actions**; this was configured during setup. Job permissions grant collection write access to repository contents and deployment write access to Pages with an OIDC token. No personal tokens or paid APIs are required.

Each feed gets three attempts with a timeout and size cap. If one feed fails, its still-recent previously accepted headlines can remain, and the site displays the failure. If all feeds fail, collection fails and the previous deployment remains. If no article passes the access checks, publish an empty briefing rather than keeping unchecked links. Previously accepted headlines from failed feeds are also rechecked for access before reuse. The browser marks collections older than 36 hours and hides articles older than seven days even if scheduling stops.

## Attribution, corrections, and maintenance

Source feed documentation: [PBS News](https://www.pbs.org/newshour/about/pbs-news-rss-feeds), [Al Jazeera](https://www.aljazeera.com/xml/rss/all.xml), [NASA](https://www.nasa.gov/rss-feeds/), [Federal Reserve](https://www.federalreserve.gov/feeds/feeds.htm). These publishers are not affiliated with or endorsing Factual Daily.

Report a correction through this repository's Issues tab, including the article URL and issue. Fix the source configuration or filtering code, remove the affected record when appropriate, and run the workflow again. Publication dates are feed timestamps, not verification timestamps. Headlines and sources can change after collection.
