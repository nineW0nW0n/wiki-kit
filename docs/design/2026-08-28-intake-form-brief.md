# Design handoff: the intake form

For Claude Design. Date: 2026-08-28.
Everything needed is in this document — you do not need the repository to design.

## The job

Design eight screens of a single-purpose web form. It has no navigation, no
dashboard, no account area and no second page. One form, its error state, its
confirmation, and five small supporting screens.

The whole thing is one self-contained HTML document with inline CSS. That is the
production medium, not a compromise: whatever you can express in one HTML file
with system fonts and inline SVG ships exactly as designed, with no build step
between your artboard and production.

## The person, and the moment

A colleague who does not use git and never will. They have just finished dealing
with something — a server outage, a vendor call, a meeting with three decisions in
it — and someone has sent them a link and said "put it in the wiki". They are
already signed in. They will do this maybe six times a year, and will not remember
anything they learned last time.

What they are actually doing, underneath the form: writing a Markdown file into a
private knowledge base and opening a pull request against it. They will never be
told those words. The design's job is to make that feel like *filing a note* while
still being honest that it becomes a specific file someone will review.

If they hesitate, they close the tab and the knowledge stays in their inbox
forever. That is the failure mode this design exists to prevent.

## The four design problems

These are the interesting parts. Everything else is form layout.

**1. The receipt.** Before submitting, the form shows exactly what will be
committed: the file path, and the metadata generated on their behalf.

```
This will be committed as raw/notes/2026-08-28-<slug>.md

type: Source
kind: note
author: human:abcollado.28
date: 2026-08-28
classification: P1
status: new
```

Today this is a grey monospace block that looks like an error log. It is doing the
most important job on the page — earning trust from someone who cannot read the
repository — and it looks like debug output. It should read as a receipt, or a
label on a filing envelope: *this is where your note is going, here is what we
filled in for you.* Six generated values, one of which (`<slug>`) is a placeholder
because it derives from a title they have not typed yet.

Latitude: this can stop being a code block entirely. It could be a definition
list, a card, a labelled envelope, an inline sentence with the details tucked into
a `<details>`. The **values** are generated and fixed; the **presentation** is
entirely yours. Whether a non-technical person needs to see `type: Source` at all
is a fair question to answer with the design.

**2. The rejected submission.** If validation fails, the same form comes back with
every typed value still in it, plus one error message. Someone who just pasted 900
words of incident history has to know within one second that their text survived.
Today: a red-bordered box above the form, and nothing else. This is the highest-stakes
moment in the product and currently the least designed.

**3. The unstyled half.** Five of the eight screens are bare HTML — no styling at
all, not even a viewport meta tag. Bundle picker, "nothing to file into", "not
allowed", "invalid configuration". They need to look like the same product as the
form.

**4. The dry-run preview and the confirmation.** The preview shows the generated
Markdown file before anything is filed — it is what every submitter sees until the
service goes live. The confirmation is one sentence and a link to the pull request.
Both are currently afterthoughts; the confirmation is the moment a first-time user
decides whether this was worth doing.

## Direction

Recommended, unless you have a better argument: **quiet, documentary, text-first**.
Closer to a well-set form in a government digital service or a good technical
document than to a SaaS product. Generous line length control, real hierarchy from
type rather than from boxes and shadows, one accent colour used sparingly, and
whitespace doing the structural work.

The reason: the content is someone's careful account of something that went wrong.
Visual enthusiasm reads as trivialising. And this page sits on the same hostname as
the knowledge base itself — a static documentation site — so it should not look
like a different company's product.

Two alternatives worth a mockup if you disagree: **paper/receipt** — lean into the
filing metaphor, the whole page as a form being filled and stamped; or **terminal-adjacent** —
own the monospace, make it deliberate rather than accidental, for an audience that
is at least adjacent to engineers. Show one artboard of whichever you prefer
alongside the recommended direction and make the case.

Dark mode is required and gets equal attention, via `prefers-color-scheme`. There is
no toggle and nowhere to persist one.

## Artboards to produce

| # | Artboard | What it is |
|---|---|---|
| 1 | **The form** | The main event. Full width, all fields, empty. |
| 2 | **The form, rejected** | Same form, values preserved, one error. Problem 2. |
| 3 | **The form, minimum** | One title, one textarea. Some bundles configure nothing else. |
| 4 | **The form, long** | 10+ fields, a 900-word paste in the textarea. It must not fall apart. |
| 5 | **Bundle picker** | `Add to the wiki`, then a list of 1-6 bundle names as links. |
| 6 | **Dry-run preview** | The generated Markdown file, shown back. Problem 4. |
| 7 | **Filed** | Confirmation + pull request link. Problem 4. |
| 8 | **The four dead ends** | One artboard, four small states: nothing to file into / not allowed / invalid configuration / not signed in. |
| 9 | **Dark mode** | Artboards 1 and 6 in dark. |
| 10 | **Mobile** | Artboard 1 at 390px. People file notes from phones. |

Ten artboards; 1, 2, 6 and 7 are the ones that matter.

## Real content to lay out

Do not invent copy for the generated parts — this is verbatim what the code emits.

**The form** (artboard 1), in exactly this order:

- H1: `Add to work` (the bundle owner sets this string; assume 2-6 words)
- Line: `Filing into **work** as human:abcollado.28`
- The receipt block (problem 1), containing, below the path line:
  `type: Source` · `kind: note` · `author: human:abcollado.28` ·
  `date: 2026-08-28` · `classification: P1` · `status: new`
- Then, still inside the receipt today: `Reserved — cannot be used as field names
  in intake.yml:` followed by `type kind author date classification status`, and
  `ticket is allowed, and must match ^(OPS|INC)-\d+$`.
  *This is configuration guidance aimed at the bundle owner, sitting on a page for
  a non-technical submitter. Deciding it does not belong here is a legitimate
  design outcome — say so and it gets moved.*
- `Title` — required, single-line
- `Kind` — select: `note` / `meeting` / `ticket` (sometimes a fourth, `vendor`;
  sometimes hidden entirely when the bundle allows only one)
- `Ticket (optional)` — single-line, present only when the bundle defines a pattern
- `What happened, in your own words?` — required, textarea, this is where the
  substance goes
- `Which system is this about? (optional)` — single-line
- Button: `Submit`

Field labels are written by whoever owns the knowledge base, so they are sentences,
not nouns — design for labels up to about 60 characters. Field count and field types
are configuration: between 1 and a dozen, drawn from single-line text, textarea,
dropdown, date and checkbox. Order is fixed by configuration; you cannot regroup
fields into sections, because nothing tells you which fields belong together.

**Error messages** (artboard 2), verbatim examples:

- `A title is required.`
- `What happened, in your own words? is required.`
- `Ticket 'FOO-1' does not match ^(OPS|INC)-\d+$.`
- `Could not file this right now: 401 Unauthorized. Your text is still here — try again in a minute.`

Note the last one: an infrastructure failure, phrased to reassure. And note the
second — an error built from the owner's label text, so it can be a full sentence
with a question mark in the middle of it. There is one error at a time, at the top;
the code does not currently attach errors to individual fields. If your design wants
per-field errors, say so — it is a small code change and a good one.

**Dry-run preview** (artboard 6). Heading `Preview`, then
`Nothing was filed — this service is in dry-run mode.`, then the path
`raw/notes/2026-08-28-mail-server-fell-over.md`, then the whole generated file:

```
---
type: Source
kind: note
author: human:abcollado.28
date: 2026-08-28
classification: P1
status: new
system: "mail-01"
---

# Mail server fell over

## What happened, in your own words?

Postfix stopped accepting connections at about 09:15. Restarting it cleared
the symptom but the disk was at 100% and that is the actual cause.
```

**Filed** (artboard 7). Heading `Filed`, then
`Opened https://github.com/owner/brain-work/pull/42. It appears on the wiki once
merged.` The URL is long and must wrap gracefully.

**The four dead ends** (artboard 8), verbatim:

- `Nothing to file into` / `Your account has no bundle it may write to. Ask the wiki owner.`
- `Not allowed` / `No bundle 'eng' you may write to.`
- `Not allowed` / `This form needs a signed-in person, not a service token.`
- `<bundle> cannot accept submissions` / `Its intake.yml is invalid: <parser message>`

The last one is aimed at the bundle owner, not the submitter, and the parser message
can be two lines of technical detail.

## The medium

One HTML document, inline `<style>`, served over a private tunnel. In practice:

- **System font stacks, inline SVG, `data:` URIs.** No webfonts, no CDN, no image
  files — the page cannot fetch anything external, and there is no route from which
  it could serve a local asset either.
- **CSS is where the design lives.** Custom properties, grid, flex, container
  queries, `:has()`, `accent-color`, `color-scheme` — all fair game, evergreen
  browsers only. The current stylesheet is 13 lines with no reset and no tokens;
  a real one is welcome.
- **Markup is assembled by Python string concatenation**, so favour flat structure
  and let CSS do the layout. Three levels of wrapper `div` is fine; eight is a
  maintenance problem.
- **No JavaScript in this pass.** Everything above is achievable without it. The one
  JS feature already discussed and deferred — making `<slug>` update as the title is
  typed — can be proposed separately with the exact behaviour spelled out.
- **The form is a plain POST.** No fetch, no client-side validation as a
  replacement for the server's, no multi-step wizard: one page, one submit.

## Accessibility floor

Mostly already met — do not regress it.

- Every input keeps a visible `<label>` bound to its `id`. Never placeholder-only.
- WCAG AA contrast in both schemes; colour is never the only signal for the error.
- Visible keyboard focus on every field and the button.
- The error region should be announced — `role="alert"` and a focus target are
  welcome additions.
- Text must survive 200% zoom and a 390px viewport.

## Fixed content

Two strings are asserted by the test suite and cannot be reworded: the bundle
picker's heading `Add to the wiki`, and the `human:` author prefix. Everything
inside the receipt block is generated from the same constants the server-side
validator uses, so it can be restyled or relocated freely but not rewritten.
Field names, the four status codes, and HTML escaping of every submitted value are
implementation concerns that survive any visual change.

If a design needs one of these to change, say which and why — none of them is
sacred, they just cost a code change in the same pass.

## Handback

1. **The artboards**, as the design.
2. **The stylesheet**, as one CSS block — this is what actually ships. It ends up
   inside a Python triple-quoted string, so avoid `"""` and backslashes; braces are
   fine.
3. **Markup per screen**, as literal HTML with obvious placeholders (`{title}`,
   `{bundle_id}`, `{error}`). Where a screen keeps its current structure, say so
   instead of restating it.
4. **A short change list** — per screen: markup, CSS, or both — flagging anything
   that needs a copy or behaviour change, especially per-field errors or relocating
   the reserved-names text.

## Where it lands in this repo

Nothing static ships; there is no `assets/` or `static/` directory and the container
cannot serve one. Two source files change:

| What | Lands in |
|---|---|
| The stylesheet | `intake/handlers.py`, the `CSS` constant — replace wholesale |
| Form, receipt, input, preview and confirmation markup | `intake/handlers.py` — `_page`, `_notice`, `_input`, `render_form`, `handle_submit` |
| Bundle picker and the four dead ends | `intake/app.py` — `index`, `_forbidden`, and the two config-error branches. These bypass the page shell today; route them through `_page()`. |
| This brief | `docs/design/2026-08-28-intake-form-brief.md` |
| Approved artboards, if worth keeping | `docs/design/intake/` — reference only, never served |

A proposal that needs a third source file is out of scope for this pass.

To see the current form before redesigning it, from a checkout:

```sh
open "$(python3 scripts/intake_preview.py)"
open "$(python3 scripts/intake_preview.py --error 'A title is required.')"
python3 scripts/intake_preview.py --bundle-dir tests/fixtures/good-bundle  # minimum case
```

After changes: `python3 -m pytest tests/ -q` (84 tests; the HTML assertions live in
`tests/test_intake_handlers.py`).

## Out of scope

The submit path and its GitHub API calls, the configuration schema, authentication,
which fields exist, and the rules about which metadata keys are generated. The
underlying product decisions are settled in
`docs/superpowers/specs/2026-08-27-raw-intake-design.md`; this pass is appearance only.
