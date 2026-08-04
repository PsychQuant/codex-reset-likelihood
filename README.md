# codex-reset-likelihood

A measurement instrument for a rumour-driven event: OpenAI's occasional **bonus resets** of the Codex weekly usage cap.

Existing community tools infer these from tweets. A tweet is a claim *about* an event, not the event — when a rollout is staged, or when nothing is announced, a tweet-based detector is blind and cannot know it. This project reads the event off account state instead, which makes its own error rate measurable.

> **Status: pre-data.** No observations have been collected yet. Every figure currently on the site is synthetic and labelled as such.

## The discriminant

Every `/wham/usage` response carries the weekly window's announced `reset_at`. An ordinary rollover is therefore predictable. A bonus reset is not:

```
quota rises  AND  now <  previous reset_at   →  BONUS RESET
quota rises  AND  now ≥  previous reset_at   →  ordinary rollover, ignored
```

Deterministic. No language model reads a tweet to produce this.

## Two tracks, two scorecards

| | Question | Nature | Scored by |
|---|---|---|---|
| **Track A** | Did a bonus reset happen, and when? | measured | detection lag, recall |
| **Track B** | Risk of one in the next 24 h, given *t* days elapsed? | inferred | Brier score, calibration curve |

The site keeps these visually and statistically separate, and the separation never depends on colour alone.

Track B is a **Weibull** hazard, not exponential: an exponential hazard is memoryless, so "days elapsed" could not move the number at all. Shape and scale are estimated from the observed gaps by method of moments *inside the page*, so a printed parameter cannot drift from the number computed beside it.

Below three observed events no risk figure is published — the field reads `INSUFFICIENT DATA`.

## Architecture

```
[local collector] ×N            credentials never leave the machine
  ~/.codex/auth.json → GET /wham/usage → apply discriminant → sign
        │ POST /observations
        ↓
[ingest]  verify → dedupe → append-only JSONL, tracked in git
        ↑
[social watcher]  advisory indicator only, never part of the discriminant
        │
        ↓
[decision core]   pure function: event log → verdict + hazard, no I/O
        ↓
[web]  facts, inference, both scorecards, public archive
```

The decision core does no I/O, so a backtest is just re-running the same function over the historical log. The log is committed to this repo: **anyone can clone it and check that the scorecards are not inflated.**

The server never holds anyone's OAuth token. That is also what makes crowd-sourcing a zero-architecture change later — it is the same collector, run by more people.

## Deploy

Live: **https://codex-reset-likelihood-f5iyx8nxm-psych-quant.vercel.app**

```shell
make check      # pre-deploy gate
make preview    # preview URL
make deploy     # production, then verify
make verify     # confirm an anonymous visitor gets 200
make unprotect  # disable Vercel Authentication
```

Hosted on Vercel under the PsychQuant team. `make check` refuses to ship if the synthetic-data disclosure is missing, if a stale owner link survives, or if you are not logged in.

`make verify` exists because of a real failure: a Vercel team project ships with Deployment Protection on, so the CLI reports `READY` while every anonymous visitor is bounced to an SSO login. **A deployment can be green and invisible at the same time.** `deploy` now runs `verify` automatically and fails loudly on a 302/307.

## Running the instrument

The collector is one stdlib-only file. One invocation = one poll; drive it with cron or launchd:

```shell
python3 codex_reset_collector.py            # reads ~/.codex/auth.json locally
python3 -m pytest tests/ -v                 # the full boundary-case suite

# every 30 minutes via cron (interval width = detection-lag floor):
*/30 * * * * cd /path/to/codex-reset-likelihood && python3 codex_reset_collector.py >> .collector-state/collector.log 2>&1
```

Exit codes: `0` ok · `2` schema drift recorded (inference halts) · `3` auth · `4` network · `5` corrupt state.

Re-run the decision core over the public log — this is the reproducibility claim made executable:

```shell
python3 -m core.decision_core data/observations.jsonl
```

`data/observations.jsonl` is committed **empty**: no real observation has been collected yet, and the deployed page stays synthetic until the log holds ≥ 3 real events.

## Documents

- [`PRODUCT.md`](./PRODUCT.md) — product truth, principles, honesty boundaries
- [`docs/superpowers/specs/`](./docs/superpowers/specs/) — the design record

## What is not claimed

Detection lag, recall, and calibration are claimed and published. **Advance warning of any particular reset is not.** The upstream endpoints are undocumented and will change; when the response stops matching its expected shape, every inference halts and the site says so rather than quietly serving numbers over a drifted schema.

At n=1 collector, a staged rollout is invisible to this instrument. That limit is structural and is not fixed by polling harder.

Not affiliated with OpenAI.
