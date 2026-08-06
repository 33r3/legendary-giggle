# Exercise RPG — Design Document

Status: pre-build. Paper playtest scheduled. No code written.

---

## 1. Premise

A self-hosted game that turns real physical activity into progression, loot, and exploration.

The diagnosis this is built on: existing fitness games don't fail because exercise is repetitive. Repetitive action is fine — WoW proved that. They fail because their *mechanisms and story* are repetitive. The activity is a fixed, low-bandwidth input, so designers pad with numbers going up and call it progression. Any design here has to generate its variety somewhere other than the exercise itself.

The second diagnosis: acquisition loops are easy and get shipped; **sinks** are hard and don't. Loot without something to spend it on is a spreadsheet that increments. The sink is the design, not a feature to add later.

## 2. Constraints

These are hard requirements, not preferences. Each one has killed a previous approach.

| Constraint | Consequence |
|---|---|
| Not visible to others | No gyms, no classes, no social accountability. Home and open country only. |
| No special trips | Anything requiring a dedicated drive won't happen. Must attach to property or existing routes. |
| Cheap | No subscriptions, including for data access. Rules out Strava's API tier. |
| Self-hosted | Existing VPS. No third-party aggregation — this is why Pokémon Go was abandoned despite working. |
| Mechanical gate | Rewards derive from device data, never self-report. Player cannot also be referee. |

Note: the visibility constraint is expected to decay as fitness improves. Re-evaluate in ~6 months rather than treating it as permanent architecture. Watch for it becoming a deferral excuse.

## 3. Core Loop

Two tiers with different data requirements and different roles.

**Passive tier — currency.**
Ambient step counts above a fixed daily floor generate Fragments. No location data required, therefore no GPS, no ambient tracking, no mobile app. Incidental movement counts; walking the building at work is a small win and should register as one. Output is strictly common.

**Session tier — content.**
A deliberate outdoor walk started on the watch. Produces an `HKWorkoutRoute`, which supplies both the effort signal and the spatial context in one artifact. Rolls against region drop tables. This is where meaningful rewards live.

The split matters: **passive accrues, sessions spend and produce.** If passive can yield rare results, the walk becomes optional and the whole thing degrades into a pedometer.

## 4. The Wager

Fixed floor for passive, player-declared set point for sessions.

Rejected: trailing-average baselines. They punish improvement (your best week raises next week's bar) and reward sandbagging (a lazy week lowers it). Any baseline computed from recent behavior has this property.

The set point is declared in advance, locked for the period, and changes take effect on a lag. Modest targets are easy to clear and pay modestly; ambitious ones pay better and can be missed. That's the decision space the reward curve alone can't provide — a real choice with a real downside.

Missing the set point forfeits the bonus roll. No punishment beyond the forgone reward.

## 5. Regions

Location-seeded drop tables are the primary novelty engine and the reason to go somewhere new. Initial set: home property, Fredericksburg loop, the 281/Stone Oak corridor, Enchanted Rock.

**Hierarchy.** Regions nest: Texas → Hill Country → specific named places. Full tiling, no dead space, so every location yields something.

**Inheritance, not replacement.** A child table declares only what's distinctive about it; unmatched rolls fall through to the parent and up the chain. Root always resolves. Rationale is authoring effort — Hill Country commons get defined once instead of re-listed in every descendant. Table maintenance is what kills content-heavy hobby projects.

**Ancestors are strictly worse.** Commons only above the leaf level, no Signatures. If the generic table pays well, there's no reason to travel, and travel was the point.

## 6. Sink

**Phase one: unlock regions.** Spend Fragments to open new drop tables. Loot buys access, access produces better loot, and choosing which region to open first is a decision you can get wrong. Single-player, closes the loop with no second person required.

**Deferred: token-gated group encounters.** Collect quantity X of token Y to trigger an encounter. Compatible with the visibility constraint — trading with people who never watch you walk isn't the objectionable part. But it needs population density to feel like anything, and it drags in accounts, real anti-cheat, and uptime obligations. Not until single-player works.

## 7. Data Architecture

**Ingest.** HealthKit → export app webhook → FastAPI endpoint on the VPS. Nothing leaves owned infrastructure.

Strava rejected: as of June 2026 new Standard-tier developers require a paid subscription, and third-party intermediary routing is no longer supported. Paying monthly to read your own step count fails the cheap constraint and reintroduces exactly the dependency that killed Pokémon Go.

Fallback if ambient tracking is ever wanted: Overland or OwnTracks already post background location to a self-hosted HTTP endpoint. No app development required. Note iOS backgrounding only lets you *suggest* collection intervals — adequate for region detection, inadequate for precise traces.

**Known gotcha — source duplication.** iPhone and watch both record steps. HealthKit statistics queries deduplicate across sources; raw sample queries do not and will silently run ~2x. Validate ingest totals against the Health app before building anything on top.

**Storage.** Raw steps and routes append-only. Rewards computed as a derived layer. The reward curve *will* be retuned several times in the first month; if it's baked into ingestion, history is corrupted every time.

## 8. Geospatial

Start with GeoJSON polygons loaded at startup and point-in-polygon via Shapely. Four shapes and a few hundred points a week don't justify PostGIS — a spatial database earns its keep on index-exploiting query load. Migration later won't change the polygon definitions.

**Region attribution is time-weighted.** A route isn't a point and can cross boundaries. Start-point attribution is gameable (begin the walk just inside the good region); majority-of-points is biased by sampling density, which varies with speed and signal. Bucket route minutes by region and allocate rolls proportionally. Composes cleanly with the per-15-minutes roll rule.

**Depth is an explicit column,** not derived from polygon area — area ordering goes nondeterministic when two regions are near-identical in size.

**Validate containment at load, loudly.** A child polygon not actually inside its parent breaks the hierarchy silently and presents as a drop-rate bug.

**If prototyping in SQL Server:** `geography` polygons are ring-orientation sensitive. A clockwise ring selects everything on Earth *except* the intended area, validates fine, and returns confidently wrong results. `ReorientObject()` exists for this.

## 9. Phases

1. **Paper playtest** — one week, manual rolls, hand-logged. Set point: Standard. Answers whether the rates feel right and, more importantly, whether the walking actually happens.
2. **Minimal ingest** — HealthKit webhook, append-only raw storage, verify against Health app.
3. **Passive tier** — fixed floor, Fragment accrual. No location logic at all.
4. **Session tier** — route ingestion, region polygons, time-weighted attribution, drop tables.
5. **Region unlocks** — the sink.
6. **Hierarchy** — nesting and inheritance. Schema decision; needs real data first.

## 10. Risks

**The build substitutes for the activity.** This is the primary risk and it has precedent — the design is more fun to work on than the walking is to do. The paper week exists specifically to test this before any code is written. If the manual week doesn't happen, that is the finding, and no amount of good architecture fixes it.

**Reward becomes toll booth.** If the game gets good enough, exercise becomes the obstacle standing between you and it, and gets resented or routed around. Watch for resentment of the workout specifically. Loosen the gate rather than white-knuckling it.

**Rates frontloaded.** The instinct is to reward heavily early to build the habit. It inverts: the interesting acquisitions burn off in three weeks and month two is barren — precisely how the existing apps went stale.

**Self-authored referee.** Every rule here is one you wrote and can edit at 9pm on a bad day. Mechanical data ingestion handles part of it; lagged set-point changes handle the rest. The remainder is handled by the collection being worthless to you if it's fraudulent, which is the same thing that makes shiny hunting work.
