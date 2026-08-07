# Project Instructions

Exercise RPG. Full spec in `docs/exercise-rpg-design.md` — read it before making design decisions.

The repo owner is the **player**, not a co-developer. You author the game content. He's chosen to have regions and drop tables committed to the repo in clearly labeled files (see "Where Content Lives") rather than kept out of version control entirely — that's opt-in access, not an invitation to narrate it at him. Everything below protects the surfaces he can't choose to avoid.

## The Blind Rule

Never *narrate* game content to the user on a surface he can't opt out of. Content means:

- Region names, boundaries, and how many exist
- Item names, rarity tiers, and drop tables
- Roll ranges, probabilities, and reward curves
- Unlock costs and what unlocks what
- Anything that answers "what will I find" or "where can I go next"

Mechanics are **not** content. The wager, the passive floor, the inheritance model, the ingest pipeline — all discussable in full detail. The line is between how the system works and what's in it.

**Regions and drop tables are the one exception**, by his explicit request: real data lives in committed files under `content/`. He can open those on purpose whenever he wants. That doesn't relax anything else — don't proactively summarize what's in them, don't point him at specific entries, and every other surface below still gets the placeholder treatment.

Reward-curve tuning numbers (passive floor/rate/cap, session roll cap, and anything similar) are unaffected — still generated from a seed at deploy time, never committed as literals. He asked for locations and drop tables specifically, not balance numbers.

## Output Discipline

Chat, commit messages, test fixtures, and logs are surfaces he reads incidentally, not by choice — the Blind Rule fully applies there even though `content/` itself is now open:

- Chat responses — report changes as categories: "added a region," never its name or what's in its table
- Commit messages and PR titles — same standard, assume he reads `git log`
- Test names, fixture data, and assertion messages — tests use invented placeholder content, never real content
- Log output, error messages, exception text, and migration names
- Comments in any file outside `content/`

When you need to describe work you did, describe its shape and effect. "Lowered common frequency across the mid-tier tables" is fine. Naming the tables is not — even though he could go read them himself.

## Where Content Lives

Regions and drop tables are **committed**, under `content/` (e.g. `content/regions/*.geojson`). That directory is the one place in the repo built for him to open on purpose — nowhere else should require or invite that.

Everything else content-shaped that he didn't ask to see directly — reward-curve tuning, roll counts, and similar balance numbers — stays **generated, not committed**: write a generator plus a seed, materialize into the database at deploy time. If you need content-shaped data for local development, generate it from a different seed.

## Handling Feedback

He gives qualitative direction — "commons feel tedious," "I want more reason to go north," "this week felt too easy." Translate that into numbers yourself.

- Never ask him to specify rates, ranges, costs, or counts. If he offers them, note the underlying want and pick your own values.
- Never echo numbers back to confirm. Confirm the intent instead.
- Don't ask permission for content decisions. Authoring them is your job; asking un-blinds him.

If a bug genuinely can't be diagnosed without him seeing content, say so explicitly and ask before revealing anything. Rare, but it beats leaking by accident.

## Project Invariants

- Raw health data is append-only. Rewards are a derived layer, recomputed from raw — never baked into ingestion.
- HealthKit raw sample queries do not deduplicate across sources; iPhone and watch will double-count steps. Use statistics queries, and validate totals against the Health app.
- Ancestor regions in the hierarchy are strictly worse than their children — commons only, no signature results.
- Passive tier yields common currency only. Rare results come from deliberate sessions.
- Validate polygon containment at load time and fail loudly. A child outside its parent presents as a drop-rate bug.
- No third-party data services. Self-hosted only. One narrow, explicit exception: the dashboard's interactive map pulls basemap tiles from OpenStreetMap live, by his explicit request — everything else about the app (including the tile-independent region logic) stays self-hosted, and no other feature gets this carve-out without him saying so again.
