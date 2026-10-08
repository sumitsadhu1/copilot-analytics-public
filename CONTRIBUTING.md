# Contributing to the Copilot Analytics Hub

## Before you write a new page, answer one question

Which surface does this page belong to?

- **Decide** — a decision tool. The reader has a choice to make and needs a recommendation. Interactive where possible. Prose-lean.
  Example: [/decide/architecture.html](decide/architecture.html).

- **Do** — a how-to. The reader is executing a deployment or procedure and needs step-by-step instructions. Preconditions stated up front.
  Example: [/2-setup/multi-agency-setup.html](2-setup/multi-agency-setup.html).

- **Reference** — a lookup. The reader already knows what they're looking for (a metric definition, an attribute name, an error code) and needs findability. Tables over prose.
  Example: [/4-reference/troubleshooting.html](4-reference/troubleshooting.html).

- **Explain** — narrative context. The reader is studying, not working. Prose. Opinions allowed. Diagrams earn their place.
  Example: [/explain/why-multi-agency-is-hard.html](explain/why-multi-agency-is-hard.html).

If your page answers more than one of these, split it. Do not merge.

## Writing conventions per surface

### Decide

- Lead with the question, not the background. The reader already knows they have a choice.
- Use interactive elements (progressive disclosure, collapsible details) when there are branching paths.
- Keep prose under 300 words outside the decision mechanism itself. If you're writing more, you're leaking explanation in.
- Output a concrete recommendation: which path, what to read next, what to skip.
- Always include a static fallback for readers with JS disabled.

### Do

- State preconditions before step 1. The reader should know what they need before they start.
- Use numbered lists for sequential steps. Do not bury steps in prose paragraphs.
- One action per step. If a step has sub-steps, use a nested list.
- Include verification after each major milestone ("you should now see…").
- Link to Reference pages for lookup details; don't inline attribute tables in a how-to.

### Reference

- Tables over prose. A reference page that reads like an essay is a failed reference page.
- Each row should be independently useful — the reader is scanning, not reading top to bottom.
- Sort by the dimension the reader is most likely searching on (symptom, attribute name, error code).
- Include the search terms readers would use. If they'd search "VFAM not working", make sure that string appears near the answer.
- Do not add explanatory context beyond what's needed to use the lookup. Link to Explain pages for background.

### Explain

- Write for someone who has time to read — but don't waste it. 400–800 words is typical.
- Opinions and recommendations are welcome. This is where "we recommend X because Y" belongs.
- Diagrams earn their place only if they communicate something prose cannot. Do not add diagrams for decoration.
- End with a clear handoff: "Ready to decide? → [link]" or "Ready to implement? → [link]".
- Do not repeat procedural steps from Do pages. Link instead.

## Tone

Australian English. Direct. Assume the reader is technical and time-poor. No marketing language. No filler preambles. Lead with the answer.

## Voice and evidence

This hub explains how to operate Microsoft products. It doesn't retell Microsoft Learn. Keep the evidence and the prose separate: the evidence proves a claim, and the prose tells the reader what to do with it.

- **Write in the hub's own voice.** Speak to the reader ("you"), lead with the action or answer, and use the imperative for steps. State each fact directly and cite its source once, as a link in the text or a row in the page's sources table.
- **Don't narrate sources.** Don't use "Microsoft states…", "Microsoft says…" or "The article says…" to carry a fact. Name a source in the text only when the reader needs to know which article says it, for example when two Microsoft articles conflict.
- **Quote only when the exact words matter.** Put UI labels, setting names and metric names in bold, not in quotation marks. Keep verbatim quotes for wording that can't be paraphrased without changing its meaning, and keep them short. More than two or three quotes on a page usually means the page is retelling its sources.
- **Keep the evidence trail out of the prose.** Verbatim quotes, URLs and retrieval dates belong in review ledgers, the fact catalogue (`scripts/fact-check/facts.json`) and the page's sources table, not in every sentence.
- **Paraphrase without changing strength.** Keep the source's level of certainty:
  - "might take three hours" isn't "up to three hours"
  - "not documented" isn't "not required"
  - "listed for X" isn't "only works in X"

  Avoid absolutes such as *only*, *never*, *all*, *can't* and *nobody* unless the source states them.
- **Consolidate uncertainty.** Put documentation gaps and Microsoft-versus-Microsoft conflicts in one section of the page, such as "Known Gaps and Conflicts". For each, link both sources, don't choose a winner or rank them by date, and say what to test in the tenant. In the body, point to that section in a few words instead of repeating the conflict. Don't paste the same conflict paragraph into several pages; link to the page that covers it.
- **Add operational value.** Every section should help the reader decide or act: what to check, what to watch, what order to do things in, and what to avoid. If a paragraph only restates Learn, link to Learn instead.
- **Follow the basics of the [Microsoft Writing Style Guide](https://learn.microsoft.com/style-guide/top-10-tips-style-voice).** Get to the point fast, be brief, start statements with a verb where you can, and use contractions. Keep the hub's own conventions where they differ, such as Title Case headings, so pages stay consistent with each other.

### Sources and dates

- A printed "Last updated" date next to a Microsoft Learn link is the date Learn displays on that page.
- When a cited page changes, re-check the claim it supports before you update the printed date. Microsoft splits, moves and rewrites articles, so a fresh date can sit beside a claim the page no longer makes. For example, in October 2026 the usage-based billing article was split in two and the organizational data overview was rewritten.
- Re-check `#anchors` and link titles as well as dates when a source changes.

### Rewriting a published page

When you rewrite a page for style, its meaning must not change:

1. List every factual claim in the old version.
2. Confirm that each claim is still present, intentionally removed, or corrected against its source.
3. Check that no claim became stronger or weaker in the rewrite.

Have someone other than the author review the rewrite before you publish it.

## Diagrams

- Decision trees for branching choices.
- C4-style layered architectural diagrams for structural content (Context → Container → Component). One diagram per level; do not cram.
- Tables for lookup and comparison.
- Numbered lists for procedures.
- Do not draw a "map of the whole product."

## Before you commit a new page

- Does it fit on exactly one surface?
- Does it lead with the answer in the first viewport?
- Have you linked out to Microsoft Learn for anything that changes more often than quarterly?
- Have you added the page to the appropriate scenario card (if it's the primary destination for a scenario) and to [/browse.html](browse.html)?
- Is it written in the hub's voice? Run `python3 scripts/maintenance/check_voice.py <page>`. Aim for no source narration ("Microsoft states/says") and at most a few verbatim quotes, and keep the average sentence length to about 20 words or fewer.
- Do the printed "Last updated" dates match what Learn displays, and does each cited page still support the claim it's cited for?
