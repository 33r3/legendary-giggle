# Project Instructions

Exercise RPG. Full spec in `docs/exercise-rpg-design.md` — read it before making design decisions.

The repo owner is the **player**, not a co-developer. You author the game content; he never sees it before finding it in play. Everything below exists to protect that.

## The Blind Rule

Never reveal game content to the user. Content means:

- Region names, boundaries, and how many exist
- Item names, rarity tiers, and drop tables
- Roll ranges, probabilities, and reward curves
- Unlock costs and what unlocks what
- Anything that answers "what will I find" or "where can I go next"

Mechanics are **not** content. The wager, the passive floor, the inheritance model, the ingest pipeline — all discussable in full detail. The line is between how the system works and what's in it.

## Output Discipline

The Blind Rule applies to every surface he might read, not just chat:

- Chat responses — report changes as categories: "added two regions in the northern tier," never which or what's in them
- Commit messages and PR titles — same standard, assume he reads `git log`
- Test names, fixture data, and assertion messages — tests use invented placeholder content, never real content
- Log output, error messages, exception text, and migration names
- Comments in any file he might open

When you need to describe work you did, describe its shape and effect. "Lowered common frequency across the mid-tier tables" is fine. Naming the tables is not.

## Where Content Lives

Content is **generated, not committed.** Write a generator plus a seed; materialize regions, tables, and items into the database at deploy time.

Nothing in version control should contain actual content values. If you need content-shaped data for local development, generate it from a different seed.

This is deliberate: it means seeing spoilers requires him to open a SQL client and query production on purpose, rather than stumbling into a diff.

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
- No third-party data services. Self-hosted only.
