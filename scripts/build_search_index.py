#!/usr/bin/env python3
"""
Generate a search index JSON from all HTML documentation files.
Extracts headings (h1-h4) and nearby paragraph text to create
a searchable index that the landing page can use for deep search.
"""
import os
import re
import json

REPO = "/Users/sumitsadhu/Projects/copilot-analytics-public"
OUTPUT = os.path.join(REPO, "assets", "search-index.json")

# Files to index (relative to repo root)
FILES = [
    ("docs/core/Copilot_Analytics_Implementation_Guide.html", "Copilot Analytics Implementation Guide"),
    ("docs/core/Copilot_Analytics_Setup_Companion_Guide.html", "Setup Companion Guide"),
    ("docs/playbooks/Copilot_Multi_Agency_Isolation_Architecture.html", "Multi-Agency Isolation Architecture"),
    ("docs/playbooks/Copilot_Multi_Agency_Default_Priority_Architecture.html", "Multi-Agency Default Priority Architecture"),
    ("docs/playbooks/Copilot_Lifecycle_Billing_Playbook.html", "Lifecycle & Billing Playbook"),
    ("docs/playbooks/Advanced_Viva_Insights_Collaboration_Guide.html", "Advanced Collaboration Analysis"),
    ("artifacts/Copilot_Analytics_FAQ.html", "FAQ"),
    ("artifacts/Copilot_Analytics_QuickStart_CheatSheet.html", "Quick-Start Cheat Sheet"),
]

def strip_tags(html):
    """Remove HTML tags and decode common entities."""
    text = re.sub(r'<[^>]+>', ' ', html)
    text = text.replace('&mdash;', '—').replace('&ndash;', '–')
    text = text.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    text = text.replace('&ldquo;', '"').replace('&rdquo;', '"')
    text = text.replace('&lsquo;', "'").replace('&rsquo;', "'")
    text = text.replace('&rarr;', '→').replace('&larr;', '←')
    text = text.replace('&ge;', '≥').replace('&le;', '≤')
    text = text.replace('&times;', '×').replace('&divide;', '÷')
    text = re.sub(r'&#x[0-9a-fA-F]+;', '', text)
    text = re.sub(r'&#\d+;', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_sections(filepath, doc_title):
    """Extract headings and nearby content as search entries."""
    with open(os.path.join(REPO, filepath), 'r', encoding='utf-8') as f:
        html = f.read()
    
    entries = []
    
    # Find all headings with optional IDs
    pattern = r'<(h[1-4])[^>]*(?:id="([^"]*)")?[^>]*>(.*?)</\1>'
    matches = list(re.finditer(pattern, html, re.DOTALL | re.IGNORECASE))
    
    for i, match in enumerate(matches):
        tag = match.group(1)
        anchor = match.group(2) or ''
        heading_html = match.group(3)
        heading_text = strip_tags(heading_html)
        
        if not heading_text or len(heading_text) < 3:
            continue
        
        # Skip style/script headings
        if heading_text.startswith('Solution Architecture') and tag == 'h3':
            continue
        
        # Get content between this heading and the next (up to 500 chars)
        start_pos = match.end()
        if i + 1 < len(matches):
            end_pos = matches[i + 1].start()
        else:
            end_pos = min(start_pos + 3000, len(html))
        
        content_html = html[start_pos:end_pos]
        content_text = strip_tags(content_html)
        
        # Limit content preview
        if len(content_text) > 300:
            content_text = content_text[:297] + '...'
        
        # Build the URL
        url = filepath
        if anchor:
            url += '#' + anchor
        
        entries.append({
            'doc': doc_title,
            'heading': heading_text,
            'content': content_text,
            'url': url,
        })
    
    return entries

# Build index
index = []
for filepath, title in FILES:
    full_path = os.path.join(REPO, filepath)
    if os.path.exists(full_path):
        sections = extract_sections(filepath, title)
        index.extend(sections)
        print(f"  {title}: {len(sections)} sections indexed")
    else:
        print(f"  {title}: FILE NOT FOUND - {filepath}")

# Write index
with open(OUTPUT, 'w', encoding='utf-8') as f:
    json.dump(index, f, ensure_ascii=False, indent=None)

print(f"\nTotal: {len(index)} search entries written to {OUTPUT}")
