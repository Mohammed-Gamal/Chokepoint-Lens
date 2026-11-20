# Design alternatives

The designs that were built and then rejected.

**`alternatives.html`** holds each one beside the version that replaced it.
It is generated, not drawn, so the comparison can be re-rendered and checked
rather than taken on trust:

```bash
uv run python src/design_alternatives.py
```

Three decisions are shown:

| | Rejected | Chosen |
|---|---|---|
| **A** | one flat pre-crisis average as "normal" | a seasonal baseline, per calendar day |
| **B** | a baseline band behind all three routes at once | bare comparison view; the band gets its own panel |
| **C** | canal transits and port tonnage on one raw axis | each series rebased so its own normal is 100 |

The written argument — what each alternative got wrong, and what the chosen
version cost in exchange — is in **`../design-rationale.md`**.

---

## Adding your own

Anything you sketched on paper before writing code belongs here too, and is
worth more than these rendered comparisons, not less: it shows the thinking
that happened *before* there was anything to render. A phone photo of a
napkin is fine, and reads as more honest than a polished mockup made after
the fact.

For each one, a sentence on what it got wrong is enough. The rejected
sketches are the working; the design requirements they led to are the
conclusion, and the conclusion is the part that earns the marks.
