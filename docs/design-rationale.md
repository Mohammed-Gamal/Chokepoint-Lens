# Design rationale

Why Chokepoint Lens looks the way it does, and what it looked like first.

Every alternative described here was **built and rendered**, not imagined.
They are reproducible:

```bash
uv run python src/design_alternatives.py   # -> docs/mockups/alternatives.html
```

Open that file to see each rejected design beside the one that replaced it.

---

## The question everything answers to

> *"Is this week's dip a real signal, or ordinary seasonal noise?"*

That is the target user's question, and it is the test every design decision
below was put to. A choice that makes the dashboard prettier but leaves that
question harder to answer is the wrong choice.

---

## Decision A — what counts as "normal"

**First attempt: one flat pre-crisis average.** Take every day from
2022-01-01 to 2023-10-06, average it, draw a horizontal line at 69.8 ships
per day, and measure everything against that.

**Why it was rejected.** Suez traffic has a real annual rhythm. The quietest
calendar day averages 64.6 transits and the busiest 73.5 — a swing of 12.8%
that has nothing to do with any crisis. A flat line therefore sits *below*
normal every autumn and *above* it every winter, so the dashboard would
report a deficit each January and a surplus each November in years when
nothing happened at all.

The error is up to **7.5% on a single day**, and exceeds 5% on **53 of the
366 calendar days**. Against a 44% collapse that is immaterial. Against the
question this dashboard exists to answer — *is this week unusual?* — it is
decisive: 7.5% is roughly the size of the signal the user is looking for.

**Chosen instead.** A baseline per chokepoint *per calendar day*: 3 March is
compared against past 3 Marches. See `metrics.py`.

**What that cost.** Two problems the flat version never had, both solved
rather than ignored:

- The reference window is 1 year 9 months, so days from 7 October to 31
  December occur in it only once and their baseline is noisier. The baseline
  is smoothed across ±15 neighbouring calendar days, and a
  `baseline_n_years` column records where it is thin.
- 29 February has no observations at all in the window. The same neighbour
  smoothing fills it, rather than leaving a hole every four years.

---

## Decision B — where the baseline band lives

**First attempt: draw the band behind every route at once.** Strictly more
information on one frame — three routes, three baselines, all comparable.

**Why it was rejected.** On screen it is six lines and three overlapping grey
bands. The one thing the chart was built to show — the gap between actual and
normal — becomes the hardest thing in it to see. More information, less
communicated.

**Chosen instead.** Two panels with two jobs. The comparison view plots
routes bare, for *relative* movement. A second panel takes one focused route
and gives it the band to itself, for *absolute* deviation. The route picker
links them, so choosing a route is one act that changes both.

---

## Decision C — two measures, two units

RQ3 needs canal transits (ships) and Egyptian port activity (tonnes) read
against each other.

**First attempt: both on one axis.** Tonnes exceed ship counts by five orders
of magnitude, so the canal line is flattened onto the x-axis and the chart
answers nothing.

**The obvious fix, also rejected: a second y-axis.** It makes both lines
visible, and it invents a relationship. Where the two series cross, and which
appears to lead the other, depend entirely on the scales chosen — and the
reader has no way to know that. There is no dual-axis chart anywhere in this
project, and that is deliberate.

**Chosen instead.** Rebase each series so its own pre-crisis average equals
100. One honest axis, directly comparable, and the 100 line carries meaning
of its own: above it a series is running ahead of its own normal.

---

## Decision D — colour

Not sketched, but decided by rule rather than by eye.

- **Colour follows the entity, never its rank.** Suez is blue whether it is
  alone on screen or one of eight. The drawing loop iterates in fixed palette
  order, not in the order the user clicked, so filtering a route out never
  repaints the ones that remain.
- **The palette was validated, not chosen.** Worst adjacent-pair separation
  is ΔE 9.1 under protanopia against a target of 8, and 19.6 for normal
  vision against a floor of 15.
- **Three hues fall below 3:1 contrast** on the light surface. That is why
  the heatmap prints its percentage in every cell and the dashboard carries a
  searchable table: both are the required fallback, so nothing on the page is
  legible by colour alone.
- **Deviation is signed, so it gets a diverging scale** — two opposing hues
  with a neutral grey at zero, never a rainbow and never a coloured midpoint.
  Zero has to look like nothing.
- **No dark mode toggle.** The palette is validated against the light
  surface; offering a toggle would silently invalidate the contrast checks.

---

## Decision E — chart type per question

Variety was not the goal. Each form was picked for the data's job.

| View | Question | Form, and why |
|---|---|---|
| Chokepoint map | RQ1 | The story is geographic — traffic moving between routes. Position is the strongest visual channel; a ranked list throws it away. |
| Timeline + band | RQ1 | A dense daily series over eight years. The band is the comparison nobody else shows. |
| Composition area | RQ2 | 100% stacked area reads mix-change continuously across 2,876 days; grouped bars at that density are unreadable. |
| Period heatmap | RQ1/2 | Many signed cells at once, and the target of the brush interaction. |
| Substitution ratio | RQ1 | A share, so immune to world trade growing or shrinking. Its own panel, not a second axis. |
| Indexed divergence | RQ3 | Two incompatible units made comparable by rebasing. |
| Port dumbbell | RQ3 | The *gap* between two measures is the finding, so the two dots must sit on one row. Two bar charts would hide it. |

---

## Decision F — what the brush is for

The preset comparison periods ("conflict onset", "acute crisis", "since
mid-2024") are a judgement about where the interesting boundaries fall. They
could be wrong.

Dragging across the timeline recomputes every selected route against the
seasonal baseline for exactly the days selected. That is the difference
between a dashboard that presents a conclusion and one that supports
analysis: the analyst can disagree with the author's periodisation and test
their own.

---

## Known limits of these choices

- **The seasonal baseline assumes 2022–23 was itself normal.** It is the
  cleanest window available, not an objectively neutral one.
- **The port role categories are a manual classification** based on each
  port's position relative to the canal, not something in the data. They are
  listed in `prepare.py` so they can be disputed.
- **Diversion is inferred from absence**, never observed directly.
