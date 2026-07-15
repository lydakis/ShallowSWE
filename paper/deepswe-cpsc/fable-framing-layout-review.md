# Fable Framing and Layout Review

Model invocation: `claude -p --model fable --effort high --tools Read --permission-mode dontAsk`

Prompt: `paper/deepswe-cpsc/fable-framing-layout-prompt.md`

Date: 2026-07-14

## Response

I've read all four files: the paper, the funding brief, the frozen preanalysis spec, and the chart
map. Here is my independent review.

### 1. Which organizing question is the real one?

**A is the right organizing question, and it is the only one this analysis actually supports.** But
it needs to be stated with its empirical payload attached, not as the generic "we applied our
framework to someone else's data."

The concrete news for a DeepSWE-aware reader is a sentence the paper never quite says out loud:
*the capability leaderboard leader (Sol max) costs 2.6x more per verified success than a same-
provider, same-harness peer (Luna max) whose solve-rate deficit is statistically unresolved, and the
gap survives footprint matching, difficulty stratification, and an adversarially Sol-favorable
failure-pricing test.* That is decision-relevant information genuinely invisible in the aggregates,
which is exactly question A's promise.

B is a real finding but a bad identity. "A cost ratio is not a decision rule without a reliability
constraint and a failure price" is quasi-obvious once stated; what's non-obvious is the *empirical
demonstration*, the 65% floor winner being reselected in only 57% of replicates, the lower-bound rule
flipping to Sol max, the point-minimum moving with the failure charge. Those are strong results
*within* A. Organized *as* B, the paper becomes an argumentative essay whose thesis most readers
will grant before page 2, and the Luna/Sol result gets demoted to an illustration.

C is explicitly unanswerable here. The paper itself says DeepSWE cannot identify the routine-work
regime, budgets, or substitutability construct. Organizing around C would be overclaiming, and the
author is right that it belongs to the eventual ShallowSWE paper.

**Note versus paper:** honestly, this sits between the two, closer to "strong working paper" than
"standalone research paper." It is a descriptive reanalysis of public data, with the most
interesting robustness analyses added as result-informed amendments, and one headline pairwise
contrast. That's below the bar for a standalone conference research contribution. But the
accounting rigor puts it clearly above a technical note. "Working paper" is the correct self-
assessment.

### 2. The title

**The current title is the weakest part of the paper's framing, and it is misleading in a specific
way.** The paper itself demotes the reliability tax: Section 3.1 says the tax share "is a composition
statistic, not an independent efficiency rank," and Section 4.2 shows Sol max has a *lower* failure
share than Luna max while being far more expensive. Naming the paper "The Reliability Tax" headlines
the one concept the paper deflates. It also commits the paper to question B.

The earlier title is more honest and question-A-shaped, but it has two flaws: "Frontier Coding
Agents" overstates the scope, and "CPSC" is an unexplained acronym in a title.

Fable proposed:

> **What Cost per Success Reveals, and Cannot Decide: A Failure-Aware Reanalysis of DeepSWE v1.1**

### 3. Abstract and introduction

They foreground roughly the right question but in a **defensively inverted order that makes the
paper sound more trivial than it is**. The abstract's first two sentences are a disclaimer. The
introduction does the same. Modesty is a virtue in the claims; in the opening it reads as the paper
apologizing for existing.

Two specific problems:

- The abstract ends with the funding motivation for the author's own benchmark, which undercuts the
  paper's independence. Cut it or soften it to one neutral clause.
- The introduction's block of rhetorical questions delays the payload. Replace it with the headline
  numbers and a two-item contribution statement: one empirical, one methodological.

The same genre problem recurs in "What This Supports Funding For." A funding pitch inside the paper
converts a research artifact into a grant appendix. Let the paper be scholarly and let the separate
funding brief do the pitch. The paper needs only a short "What remains unidentified" section.

### 4. One column or two

**One column.** The two-column decision is worst-of-both-worlds here:

- Every substantive float is already full-width. The body snakes around double-column floats while
  the remaining single-column tables are squeezed to fit.
- Two-column 10pt with narrow margins is conference costume, and there is no conference.
- Technical evaluators and funders reading on screen are better served by one readable column.

Fable recommends single column, 11pt, approximately 1-inch margins, and 11 to 13 pages excluding
references and appendix after removing the funding section and repeated hedging. It recommends not
compressing the one-column version back to eight pages.

### 5. Strongest argument against

The Luna/Sol headline rests partly on an absence: the paired solve-rate interval is wide, and a true
5.5-point deficit would be economically meaningful. Four attempts per task may be underpowered to
resolve it. The most persuasive robustness checks are also post-hoc amendments. Fable concludes
that this does not overturn the framing because the paper does not claim substitutability and the
policy-dependence result absorbs the uncertainty.

The strongest argument for two columns is that it looks like a real CS paper and helps skimmers.
Fable rejects that argument because the double-column floats already break the reading flow and the
conference appearance misstates the artifact's genre.

### 6. Editorial prescription

- Organizing question: A, with the concrete empirical payload attached.
- Genre: empirical working paper, not a conference paper or position piece.
- Format: single column, 11pt, approximately 1-inch margins.
- Target: 11 to 13 pages excluding references and appendix.
- Lead with the Luna/Sol result, then state the aggregate identity and policy limits.
- Replace the funding section with a short account of what remains unidentified.
