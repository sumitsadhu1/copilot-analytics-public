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
