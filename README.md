# Renewal Radar

Harbourline runs rolling 3-month retainers. The renewal date lives in a
billing export; scope and delivery history live in a separate project
export; the two share no client ID. Two brands lapsed last quarter because
no one clocked the renewal date in time.

Renewal Radar joins the two exports on client name (fuzzily — the two
systems spell the same client differently) and surfaces what's up for
renewal in the next 45 days, so an account lead can see it without
touching a spreadsheet, a script, or a terminal. Upload two CSVs, get a
table. It's a read-only view over two exports, not a CRM, and it doesn't
fix the two systems not sharing an ID at the source — it patches around
that gap.

## The three sections

1. **Lapsed / overdue** — `contract_end` has already passed. This is
   literally the failure mode from last quarter, so it's first and in red.
2. **Renewing in the next 45 days** — sorted soonest first.
3. **Needs manual check** — anything that shouldn't be silently resolved
   one way or the other: missing end dates, low-confidence name matches
   waiting on a human, and superseded contracts from a client who re-signed.

## Matching: why two confidence bands instead of one cutoff

The two exports are entered independently, so the same client shows up as
`"Acme Co."` in one and `"ACME CO"` in the other — but also, occasionally,
two genuinely *different* clients end up with superficially similar names
(`"Meridian Health Partners"` vs. `"Meridian Home Partners"`). A single
fixed similarity threshold can't tell these apart: whatever score is high
enough to catch the first case is also high enough to risk merging the
second one — silently joining two unrelated clients' billing and delivery
data together.

So the match runs in two steps:

1. **Normalize first** — lowercase, strip common legal suffixes (`Ltd`,
   `Inc`, `Co`, `LLC`, `Group`, `Company`), strip punctuation. This alone
   resolves most of the messiness before any fuzzy logic runs.
2. **Fuzzy match what's left**, scored with rapidfuzz's token-set ratio, and
   sorted into two bands rather than a single yes/no cutoff:
   - **≥ 90 → auto-match.** No review needed.
   - **70–89 → candidate, flagged for one-click confirmation.** Never
     silently merged — the "similar name, different company" case above
     scores in this band, so it gets a human's eyes instead of being folded
     in automatically.
   - **< 70 → different clients.**

These thresholds (90 / 70) are a documented starting point tuned against
the sample data, not a magic constant — they're adjustable in
[`renewal_radar/matching.py`](renewal_radar/matching.py) if real data calls
for it.

A few other judgement calls worth knowing about (each has a one-line
comment at the point of the decision in the code, for anyone defending
these in a walkthrough):

- Matching is a **global** best-pairing across every billing/project name,
  not "each billing row takes its own best guess independently" — otherwise
  a merely-similar imposter could steal the row that rightfully belongs to
  the real match.
- A confirmed match is a **session-only** override — it's not written back
  to the CSV, so re-uploading starts unconfirmed again.
- Duplicate/re-signed clients are grouped by **normalized** identity, not
  raw string equality, since a client re-signing later is exactly the kind
  of row where spelling could drift between the two data-entry passes.
- Within "Lapsed," the most-recently-expired contract sorts first — it's
  the one still worth a phone call, unlike one that lapsed months ago.
- A contract renewing more than 45 days out doesn't appear anywhere. The
  tool is scoped to what's actionable now, not a full contract register.

## Running it locally

Requires [uv](https://docs.astral.sh/uv/).

```bash
uv sync
uv run streamlit run app.py
```

Then open the local URL Streamlit prints (typically
http://localhost:8501) and upload the two CSVs — sample ones are in
[`data/`](data/).

### Tests

```bash
uv run pytest
```

## Deployed version

https://TODO-add-streamlit-community-cloud-url-here.streamlit.app
