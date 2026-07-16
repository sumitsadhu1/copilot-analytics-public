#!/usr/bin/env python3
"""Replace duplicate legacy HTML guides with accessible canonical redirects."""

from pathlib import Path


REPO = Path(__file__).resolve().parent.parent
PAGES = {
    "docs/core/Copilot_Analytics_Implementation_Guide.html": (
        "../../index.html",
        "Implementation Guide moved",
        "The implementation guidance is now maintained as role- and task-based canonical pages in the documentation hub.",
    ),
    "docs/core/Copilot_Analytics_Setup_Companion_Guide.html": (
        "../../2-setup/admin-setup.html",
        "Setup Companion Guide moved",
        "The current setup procedure is maintained in the Admin Setup Guide.",
    ),
    "docs/playbooks/Advanced_Viva_Insights_Collaboration_Guide.html": (
        "../../3-operate/collaboration-analysis.html",
        "Collaboration Analysis Guide moved",
        "The current collaboration-analysis procedure is maintained in the Operate section.",
    ),
    "docs/playbooks/Copilot_Lifecycle_Billing_Playbook.html": (
        "../../3-operate/billing-operations.html",
        "Lifecycle and Billing Playbook moved",
        "The current licensing, billing, and consumption guidance is maintained in Billing Operations.",
    ),
    "artifacts/Copilot_Analytics_FAQ.html": (
        "../4-reference/faq.html",
        "Copilot Analytics FAQ moved",
        "The current FAQ is maintained in the Reference section.",
    ),
}


TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="robots" content="noindex,follow">
<meta http-equiv="refresh" content="0;url={target}">
<title>{title} — Copilot Analytics</title>
<link rel="stylesheet" href="{css}">
</head>
<body>
<main>
  <div class="cover">
    <h1>{title}</h1>
    <p>{message}</p>
    <p><a href="{target}"><strong>Open the current canonical guide</strong></a></p>
  </div>
</main>
</body>
</html>
"""


def main():
    for relative, (target, title, message) in PAGES.items():
        path = REPO / relative
        css = "../../assets/docs-style.css" if relative.startswith("docs/") else "../assets/docs-style.css"
        path.write_text(
            TEMPLATE.format(target=target, title=title, message=message, css=css),
            encoding="utf-8",
        )
        print(f"Retired {relative} -> {target}")


if __name__ == "__main__":
    main()