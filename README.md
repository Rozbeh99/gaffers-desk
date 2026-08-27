# The Gaffer's Desk

The published front end for a Fantasy Premier League team — the current XI, what
every player scored week by week, and the moves to make before the deadline.

**Open it:** https://rozbeh99.github.io/gaffers-desk/

On iPhone, open that in Safari and use Share → *Add to Home Screen*. It installs
with its own icon, opens full-screen with no browser chrome, and works offline
from the last copy it cached.

## The API

Every file the page reads is served as plain JSON at a fixed path, so anything
else can read it too — a Shortcut, a widget, a script.

| Endpoint | What it holds |
|---|---|
| [`api.json`](api.json) | index: team, gameweek, when it was last built |
| [`squad.json`](squad.json) | the 15, with market price, **selling** price, status, and the next five fixtures each |
| [`points.json`](points.json) | every score and the bonus inside it, per player per gameweek, plus team totals, rank and past seasons |
| [`advice.json`](advice.json) | this gameweek's verdict, the evidence behind it, and what could not be verified |
| [`season.json`](season.json) | the running log: every gameweek, every transfer, and the calls that were wrong |

Read-only, no auth, and CORS-open by virtue of being GitHub Pages.

## What this repo is not

This is **build output**, generated from a private repo that holds the analysis
scripts, the purchase-price ledger and the notification wiring. Nothing here is
hand-edited, and nothing here is secret — the FPL team it describes is already
public on the official site.

Two things are deliberately stripped before anything lands here: the ntfy topic
(a write endpoint — anyone holding it could push notifications to a phone) and
the scheduled-agent id. The build aborts if either survives into the bundle.
