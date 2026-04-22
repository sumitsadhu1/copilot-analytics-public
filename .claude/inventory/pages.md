# Page Inventory — Diátaxis Classification

| File Path | `<title>` | H1 | Diátaxis | Rationale | "How This Document Fits" | Uses "Layer N" |
|---|---|---|---|---|---|---|
| `index.html` | Copilot Analytics — Documentation Hub | **Copilot Analytics** Documentation Hub | mixed | Landing page combines role filter, topic filter, task table, and card grid — four parallel indexes | No | Yes — card badges (`v4.0 • Layer N`) and layer tab labels |
| `1-strategy/index.html` | Redirecting… | *(redirect)* | — | Meta-refresh redirect to `../index.html` | No | No |
| `1-strategy/executive-briefing.html` | Executive Briefing — Copilot Analytics Strategy | Microsoft 365 Copilot | explain | Narrative overview of capabilities and decisions for CIO/exec audience; not a procedure | Yes | Yes — inline prose + "How This Document Fits" table |
| `1-strategy/data-strategy.html` | Data Strategy — Copilot Analytics | Microsoft 365 Copilot Analytics | mixed | Mixes explanation (why org data matters) with decision (which upload path) | Yes | Yes — inline prose + table |
| `1-strategy/multi-agency-decision.html` | Multi-Agency Architecture Decision — Copilot Analytics | Microsoft 365 Copilot Analytics | mixed | Mixes explanation (§1–2), decision tree (§3), and pre-study reference (§4) on one page | Yes | Yes — inline prose + table |
| `2-setup/index.html` | Redirecting… | *(redirect)* | — | Meta-refresh redirect to `../index.html` | No | No |
| `2-setup/admin-setup.html` | Admin Setup — Copilot Analytics | Microsoft 365 Copilot Analytics | do | Step-by-step setup for all 5 analytics tiers; procedural with checklists | Yes | Yes — property table + inline prose + table |
| `2-setup/data-onboarding.html` | Data Onboarding — Copilot Analytics | Microsoft 365 Copilot Analytics | do | Procedure-first: 6 upload methods, attribute mapping, verification | Yes | Yes — inline prose + table |
| `2-setup/multi-agency-setup.html` | Multi-Agency Setup — Copilot Analytics | Microsoft 365 Copilot Analytics | do | Hands-on configuration steps for multi-agency deployment | Yes | Yes — inline prose + table |
| `2-setup/privacy-configuration.html` | Privacy Configuration — Copilot Analytics | Microsoft 365 Copilot Analytics | do | Step-by-step privacy and compliance settings configuration | Yes | Yes — inline prose + table |
| `3-operate/index.html` | Redirecting… | *(redirect)* | — | Meta-refresh redirect to `../index.html` | No | No |
| `3-operate/analyst-playbook.html` | Analyst Playbook — Copilot Analytics | Microsoft 365 Copilot Analytics | do | Procedural workflow: queries → PBI templates → publishing | Yes | Yes — inline prose + table |
| `3-operate/billing-operations.html` | Copilot Lifecycle & Billing Playbook | Copilot Lifecycle & Billing Playbook | reference | Lookup-oriented: licensing models, lifecycle scenarios, checklists | No | No |
| `3-operate/collaboration-analysis.html` | Advanced Viva Insights — Collaboration Analysis Guide | Advanced Viva Insights — Collaboration Analysis Guide | do | Procedural guide for meeting/focus/wellbeing analysis templates | No | No |
| `3-operate/dashboard-guide.html` | Dashboard & Reports Guide — Copilot Analytics | Microsoft 365 Copilot Analytics | mixed | Mixes reference (metric definitions) with explanation (how to interpret) and procedure (PBI template setup) | Yes | Yes — inline prose + table |
| `4-reference/index.html` | Redirecting… | *(redirect)* | — | Meta-refresh redirect to `../index.html` | No | No |
| `4-reference/attribute-reference.html` | Attribute Reference — Copilot Analytics | Microsoft 365 Copilot Analytics | reference | Pure lookup: attribute mapping tables, data classifications | Yes | Yes — inline prose + table |
| `4-reference/faq.html` | FAQ — Copilot Analytics | Microsoft 365 Copilot Analytics | reference | Question/answer lookup format | Yes | Yes — inline prose + table |
| `4-reference/glossary.html` | Glossary & Resources — Copilot Analytics | Microsoft 365 Copilot Analytics | reference | Term definitions and link directory | Yes | Yes — inline prose + table |
| `4-reference/troubleshooting.html` | Troubleshooting — Copilot Analytics | Microsoft 365 Copilot Analytics | reference | Symptom/cause/resolution tables — pure reference | Yes | Yes — inline prose + table |
| `artifacts/Copilot_Analytics_FAQ.html` | Microsoft 365 Copilot Analytics — Frequently Asked Questions | Microsoft 365 Copilot Analytics | reference | Standalone FAQ (legacy duplicate of 4-reference/faq.html) | No | No |
| `artifacts/Copilot_Analytics_QuickStart_CheatSheet.html` | Copilot Analytics — Quick-Start Cheat Sheet | Microsoft 365 Copilot Analytics — Quick-Start Cheat Sheet | do | Compact cheat sheet for quick-start procedures | No | No |
| `artifacts/Org_Data_Validation_Prompt.html` | Org Data Validation Prompt — Copilot Analytics | Microsoft 365 Copilot Analytics | do | AI prompt template for validating org data files | No | No |
| `docs/core/Copilot_Analytics_Implementation_Guide.html` | Microsoft 365 Copilot Analytics Implementation Guide v3.1 | Microsoft 365 Copilot | mixed | Legacy monolithic guide covering strategy+setup+operate+reference | No | No |
| `docs/core/Copilot_Analytics_Setup_Companion_Guide.html` | Microsoft 365 Copilot Analytics Setup Companion Guide v3.1 | Microsoft 365 Copilot | do | Legacy setup companion — procedural | No | No |
| `docs/playbooks/Advanced_Viva_Insights_Collaboration_Guide.html` | Advanced Viva Insights — Collaboration Analysis Guide | Advanced Viva Insights — Collaboration Analysis Guide | do | Same content as `3-operate/collaboration-analysis.html` | No | No |
| `docs/playbooks/Copilot_Lifecycle_Billing_Playbook.html` | Copilot Lifecycle & Billing Playbook | Copilot Lifecycle & Billing Playbook | reference | Same content as `3-operate/billing-operations.html` | No | No |
| `docs/playbooks/Copilot_Multi_Agency_Default_Priority_Architecture.html` | Solution Architecture: Copilot Analytics with Agency-Default Views for Multi-Agency Single Tenant | Copilot Analytics with Agency-Default Views… | do | Architecture implementation playbook for Default Priority path | No | No |
| `docs/playbooks/Copilot_Multi_Agency_Isolation_Architecture.html` | Solution Architecture: Copilot Dashboard & Analytics for Multi-Agency Single Tenant | Copilot Dashboard & Analytics for Multi-Agency… | do | Architecture implementation playbook for Isolation path | No | No |

## Summary

- **Pages classified as "mixed":** 4 — `index.html`, `1-strategy/data-strategy.html`, `1-strategy/multi-agency-decision.html`, `3-operate/dashboard-guide.html`
- **Pages with "How This Document Fits":** 13 (all content pages under `1-strategy/`, `2-setup/`, `3-operate/`, `4-reference/` except billing-operations and collaboration-analysis)
- **Pages displaying "Layer N" labels:** 15 user-facing (13 content pages + index.html card badges + index.html layer tabs)
- **Redirect pages:** 4 (`1-strategy/index.html`, `2-setup/index.html`, `3-operate/index.html`, `4-reference/index.html`)
