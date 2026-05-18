import json
import re

files = [
    "/Users/sumitsadhu/Library/Application Support/Code/User/workspaceStorage/27ad86a7af99e270ae77eba77b89d930/GitHub.copilot-chat/chat-session-resources/a4223659-83f2-4358-9b60-b6cae5759951/toolu_vrtx_01R4tGCgjR6aM52Bt4x2fUdP__vscode-1779064392397/content.json",
    "/Users/sumitsadhu/Library/Application Support/Code/User/workspaceStorage/27ad86a7af99e270ae77eba77b89d930/GitHub.copilot-chat/chat-session-resources/a4223659-83f2-4358-9b60-b6cae5759951/toolu_vrtx_01EmWwEyba9oKNCqxdvmugf6__vscode-1779064392398/content.json",
    "/Users/sumitsadhu/Library/Application Support/Code/User/workspaceStorage/27ad86a7af99e270ae77eba77b89d930/GitHub.copilot-chat/chat-session-resources/a4223659-83f2-4358-9b60-b6cae5759951/toolu_vrtx_014EkhbwJxUxMhUCGDuePE2x__vscode-1779064392399/content.json"
]

keywords = [
    r"50 licenses", r"50 combined", r"50\+", r"benchmarks", r"sentiment", 
    r"intelligent summaries", r"Agent Dashboard", r"delegation", r"trendlines", 
    r"All license type", r"Copilot Studio", r"agent active users", r"agent actions", 
    r"agent sessions", r"agent retention", r"top agents", r"agent satisfaction", 
    r"credit usage", r"autonomous agents", r"declarative agents", r"Agent 365", 
    r"Agent SDK", r"Agent Builder", r"Agent Store", r"Agent Catalog", r"PAYG", r"Copilot Credits"
]

pattern = re.compile("|".join(keywords), re.IGNORECASE)

for i, file_path in enumerate(files):
    print(f"--- File {'ABC'[i]} ---")
    try:
        with open(file_path, 'r') as f:
            data = json.load(f)
            results = data.get('results', [])
            for obj in results:
                title = obj.get('title', 'N/A')
                content = obj.get('content', '')
                url = obj.get('contentUrl', 'N/A')
                if pattern.search(content) or pattern.search(title):
                    snippet = content[:500].replace('\n', ' ')
                    print(f"Title: {title}")
                    print(f"Snippet: {snippet}...")
                    print(f"URL: {url}")
                    print("-" * 20)
    except Exception as e:
        print(f"Error reading {file_path}: {e}")
