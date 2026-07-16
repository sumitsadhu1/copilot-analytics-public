# Entra Hierarchy Validation — Copilot Dashboard scope rollup

A small, self-contained PowerShell tool to **extract the Microsoft Entra ID manager
hierarchy to CSV**, so it can be validated for the most common cause of a Microsoft
Copilot Dashboard whose hierarchy "collapses" or rolls up incorrectly. Validation is done
downstream with the **Microsoft 365 Copilot Analyst Agent** — this tool only produces the
extract.

Use this when Microsoft Entra currently owns the Viva Insights / Copilot Dashboard
**`ManagerId`** source, either because the tenant uses Entra for organizational data or
because **parallel ingestion** explicitly selects Entra for `ManagerId`. The fact that a
file was uploaded at some point does not determine the current source.

Before interpreting the export, record the tenant's source state:

1. In the Viva Insights organizational-data admin experience, review **Configure Entra
  connection** and record whether Entra is selected for `ManagerId` and `Organization`.
2. Review active **Organizational Data in Microsoft 365** connections and the apps/fields
  they supply.
3. Check the latest tenant-specific Message Center migration notice and the actual controls
  present in both admin surfaces. Current Microsoft Learn pages conflict about whether Viva
  web-app add/edit uploads remain supported, so do not infer state from a date or missing tile.
4. If Entra is not the current `ManagerId` source, use the export only as a comparison against
  the authoritative uploaded/connector hierarchy; do not diagnose the dashboard solely from it.

---

## How the dashboard rollup actually works (grounded in Microsoft Learn)

- The dashboard's **Scope** filter that produces **"Your company"** and **"Your group"**
  is, by default, based on the Microsoft Entra ID manager attribute. The dashboard page
  refers to this attribute as **`ManagerID`**; the Viva Insights organizational-data
  field it maps to is **`ManagerId`** (and the Entra source field is
  `Manager/UserPrincipalName`). Same concept, three spellings — cite the one that matches
  the surface you are in.
- The **senior-leader list** (the selectable groups in Scope) is taken from the
  **top second levels of the *largest* organization hierarchy tree** in the company.
- If there are **other** hierarchy trees, each one's **top leader is surfaced only if
  that tree is at least 4 percent of the overall company size**. Trees under 4% are
  effectively **dropped** from the Scope picker — which presents as a "collapsed" or
  incomplete hierarchy.
- When Entra supplies the relevant Dashboard/Viva attributes, the populated grouping attribute is **`Organization`**
  (from Entra `Department`). **`Job function`** does *not* appear unless an admin uploads
  `FunctionType` / `Microsoft_JobDiscipline`.

The dashboard's own FAQ confirms the failure mode: *"Why can't I see my senior leadership
members as a selectable option within the Scope dropdown menu? Your Entra data isn't
reliable, or it doesn't accurately reflect the reporting structure at your company."*

So the validation target is: **one connected intended tree (or documented side-trees), no
broken/cyclic links, and intended branches large enough to clear 4%.** Treat the
"one top leader" rule as the target for a single-tree design, not a universal requirement
for a tenant that intentionally has multiple valid organizations.

---

## What's in this folder

| File | Purpose |
|---|---|
| `Export-EntraOrgHierarchy.ps1` | Microsoft Graph PowerShell export of users + managers to CSV |

---

## Prerequisites

- **PowerShell 7+** (recommended) *or* **Windows PowerShell 5.1** (built into Windows),
  with the Microsoft Graph SDK:
  ```powershell
  Install-Module Microsoft.Graph -Scope CurrentUser
  ```
- A sign-in that can consent to / has been granted the **`User.Read.All`** Graph scope
  (admin consent may be required). This is the least-privilege permission that
  `Get-MgUser` and `Get-MgUserManager` need to read the manager chain.

> **No app registration required.** Omit `-ClientId` and the script uses the built-in
> **Microsoft Graph PowerShell** app, which already has the redirect URIs configured for
> interactive sign-in. A custom app reg without a redirect URI causes `AADSTS500113`.

### Windows quickstart

On Windows, do this first in the folder containing the scripts:

```powershell
# 1. Allow this session to run the local script (no machine-wide change)
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# 2. If the .ps1 was downloaded/copied from elsewhere, clear Mark-of-the-Web
Unblock-File .\Export-EntraOrgHierarchy.ps1

# 3. Sign in ONCE (built-in app, opens a browser), then run the export
Connect-MgGraph -Scopes "User.Read.All"
.\Export-EntraOrgHierarchy.ps1 -OutputPath .\entra-org-hierarchy.csv

# 4. Validate the CSV downstream with the Microsoft 365 Copilot Analyst Agent
#    (see artifacts/Org_Data_Validation_Prompt.html in this repo)
```

Notes for Windows:
- **Avoid `-UseDeviceCode`** — the Graph SDK device-code flow has a known token bug on
  current builds; plain `Connect-MgGraph` (interactive browser) is the reliable path.
- On **Windows PowerShell 5.1**, `Export-Csv -Encoding UTF8` writes a UTF-8 BOM; Excel and
  the Copilot Analyst Agent read that correctly.

---

## Step 1 — Extract the directory data to CSV

Sign in once with the built-in Graph app (interactive browser), then run the script —
it reuses that connection:

```powershell
Connect-MgGraph -Scopes "User.Read.All"
./Export-EntraOrgHierarchy.ps1
# or choose an output path / use the reliable per-user manager lookup:
./Export-EntraOrgHierarchy.ps1 -OutputPath ./entra-org-hierarchy.csv -UsePerUserManagerLookup
```

Output columns map onto the Viva Insights organizational-data concepts. The extract is a
diagnostic snapshot; do not upload it without separately confirming the tenant path,
required schema, selected apps, data classification, and rollback plan:

| CSV column | Entra source | Viva Insights field |
|---|---|---|
| `PersonId` | `userPrincipalName` | `PersonId` |
| `ManagerId` | manager's `userPrincipalName` | `ManagerId` |
| `Organization` | `department` | `Organization` |

By default only **enabled** accounts are exported; add `-IncludeDisabled` to keep
disabled ones.

> The export reads the directory **non-destructively**. It does not change Entra, and it
> does not upload anything to Viva Insights / the Copilot Dashboard.

---

## Step 2 — Validate the hierarchy with Copilot Analyst

Hand the exported CSV to the **Microsoft 365 Copilot Analyst Agent** for validation —
attach the file and use the **Org Data Validation prompt** in this repo
(`artifacts/Org_Data_Validation_Prompt.html`). Ask it to check the reporting chain for
the issues that distort the Copilot Dashboard **Scope** rollup:

- multiple top leaders (more than one blank `ManagerId`)
- broken manager links (a `ManagerId` that isn't anyone's `PersonId`)
- cycles / self-managers in the chain
- fragmented side-trees (each tree under ~4% of the company is dropped from Scope)
- blank `Organization` (Entra `Department`) values that collapse the grouping filter

Tell the Analyst Agent which source-state evidence you recorded in Step 0. A header pattern
identifies a file schema; it does not prove which tenant portal or data source is active.

This tool deliberately stops at extraction — no local analysis is performed.

---

## What to check (and why)

| Check | What a failure means | Remediation |
|---|---|---|
| **Reporting-link integrity** — blank-manager rows | Multiple roots can indicate intentional side-trees or broken hierarchy; the Dashboard bases senior-leader selection on the largest tree and applies the documented 4% rule to other trees | Confirm every root is intentional. For a single-tree design, ensure exactly one top leader; otherwise document valid side-trees and test their Dashboard visibility |
| **Broken manager links** | A `ManagerId` points to someone who isn't in the directory; that branch can't connect to the top | Fix the manager value in Entra (or re-enable / re-create the missing manager account) |
| **Cycle detection** | A loops to B loops to A; the chain never reaches a top leader | Break the loop; correct whichever manager assignment is wrong |
| **Hierarchy trees / 4% rule** | Side-trees under 4% of the company are dropped from Scope → "collapsed" view | Reconnect side-trees into the main tree, or grow/merge them above the 4% threshold |
| **Depth / layer consistency** | People whose chain hits an orphan/cycle before the top | Same fixes as above — every person must have an unbroken path to the single top leader |
| **Organization attribute** | Blank `Department` collapses the only Entra-only grouping filter | Populate `Department` consistently in Entra/HR sync |

After the underlying Entra data is corrected, allow time to propagate — the senior-leader
identification is recomputed on a **weekly** cadence, so the Scope picker won't update
instantly.

---

## Symptom → likely cause → check

| Symptom | Likely cause when Entra owns `ManagerId` | What to look for |
|---|---|---|
| Hierarchy "collapses" to one level | Many small trees under 4%, or broken links | tree fragmentation, broken manager links |
| Only "Your company" shows, no groups | No clean second level under one root / fragmented chain | multiple roots, tree fragmentation |
| A whole division is missing from Scope | That division's top leader sits in a side-tree under 4%, or an orphaned link severs it | tree fragmentation |
| Senior leaders not selectable | Multiple roots / unreliable manager data | multiple roots, unreliable manager data |
| Can't group by job role | Expected on Entra-only — `Job function` needs an upload | (by design — see caveats) |

---

## Important caveats

- **`company → division → business unit → team` is not a native dashboard taxonomy.**
  The dashboard hierarchy is the **reporting (manager) tree**. If the desired business
  layers don't match reporting lines, fixing the chain alone won't reproduce them.
- **Entra stores a single manager per user** — it cannot express matrix / dotted-line
  structures. A matrixed target hierarchy needs richer modelling.
- **Deeper / custom org modelling requires Viva Insights**, not Copilot alone. Building a
  custom taxonomy means uploading organizational data (and, for advanced analysis,
  custom person queries in the Viva Insights web app). Confirm the customer's licensing
  before promising that path.
- **Source precedence is surface- and attribute-specific:**
  - Microsoft 365 User Profile keeps Entra as the default unless Organizational Data in
    Microsoft 365 is prioritised; uploaded data can fill Profile gaps.
  - Copilot Dashboard / Viva Insights use the organizational attributes shared with those
    apps. Microsoft documents merged Dashboard data with the more recent upload taking
    priority when multiple uploads exist.
  - Parallel ingestion can keep or restore Entra as the default for Viva `ManagerId`
    and/or `Organization`, while uploaded files or connectors supply other attributes.
  - `FunctionType` / `Microsoft_JobDiscipline` has no documented Entra Job-function fallback.
- Do not describe an upload as universally or permanently replacing Entra. Record the
  source owner for each surface and attribute, then test Profile and Dashboard/Viva
  independently.

## Supported correction and rollback paths

- For Organizational Data in Microsoft 365 updates, upload only affected users and the
  values to change. Blank or omitted values preserve existing data.
- Use documented deletion markers when a value must be removed: `''` for a string in CSV
  (three single quotes in Excel), `-1` for an integer, a nonexistent in-tenant address for
  an email, and `01-01-0001` for a date.
- Use CSV **Historical import** with **File valid as of** for retroactive Viva Insights
  corrections.
- To return Viva `ManagerId` or `Organization` to Entra, select those attributes under
  **Configure Entra connection**, allow about 24 hours, and then remove optional uploaded
  attributes that are no longer needed.
- Do not use a one-row dummy **Replace All** file as a general rollback. For a critical
  migration failure, preserve import/source evidence and use Microsoft Support; Microsoft
  documents temporary rollback only in special cases.

---

## Microsoft Learn references

- Copilot Dashboard — Scope, "Your company"/"Your group", manager hierarchy, and 4% senior-leader rule (updated 1 July 2026):
  <https://learn.microsoft.com/en-us/viva/insights/org-team-insights/copilot-dashboard#adoption>
- How automatic access is determined (single reporting line, weekly recompute):
  <https://learn.microsoft.com/en-us/viva/insights/org-team-insights/copilot-dashboard#how-automatic-access-to-the-copilot-dashboard-is-determined>
- Organizational Data in Microsoft 365 — app requirements and Profile precedence (updated 2 December 2025):
  <https://learn.microsoft.com/en-us/viva/organizational-data>
- Parallel Entra plus uploaded data — `ManagerId`/`Organization` source control and restoration (visible date 30 June 2025; content refreshed 7 July 2026):
  <https://learn.microsoft.com/en-us/viva/insights/advanced/admin/entra-plus-csv-upload>
- Current CSV update/delete markers and Historical import (updated 2 April 2026):
  <https://learn.microsoft.com/en-us/viva/import-orgdata>
- Tenant-wave migration, Message Center control, and Support rollback (updated 5 December 2025):
  <https://learn.microsoft.com/en-us/viva/insights/advanced/admin/upload-org-data-admin-center>
- Prepare an organizational data file upload (required fields, hierarchy concepts, `Layer`, `SupervisorIndicator`):
  <https://learn.microsoft.com/en-us/viva/insights/advanced/admin/prepare-org-data>
- Manage settings — required Copilot Dashboard attributes and the Viva versus `Microsoft_*` names (updated 20 March 2026; conflicts with the parallel-ingestion page on Viva add/edit availability):
  <https://learn.microsoft.com/en-us/viva/insights/advanced/admin/manage-settings-copilot-dashboard#upload-organizational-data-for-the-copilot-dashboard-and-agent-dashboard>
- `Get-MgUser`:
  <https://learn.microsoft.com/en-us/powershell/module/microsoft.graph.users/get-mguser>
- `Get-MgUserManager` (permission `User.Read.All`):
  <https://learn.microsoft.com/en-us/powershell/module/microsoft.graph.users/get-mgusermanager>
