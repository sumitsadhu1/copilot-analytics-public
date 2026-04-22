#!/bin/bash
# Generate PDFs for all Copilot Analytics documentation
# Requires Google Chrome installed at /Applications/Google Chrome.app
# Usage: ./scripts/generate_all_pdfs.sh

set -e

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PDF_DIR="$REPO_DIR/artifacts/pdfs"

mkdir -p "$PDF_DIR"

echo "Generating PDFs..."
echo "Output: $PDF_DIR"
echo ""

# Document list: input_path -> output_name
declare -a DOCS=(
  # Layer Cake structure (new)
  "1-strategy/executive-briefing.html|Executive_Briefing.pdf"
  "1-strategy/data-strategy.html|Data_Strategy.pdf"
  # 1-strategy/multi-agency-decision.html is now a redirect — PDF from decide/architecture.html
  "decide/architecture.html|Multi_Agency_Decision_Guide.pdf"
  "explain/why-multi-agency-is-hard.html|Why_Multi_Agency_Is_Hard.pdf"
  "2-setup/admin-setup.html|Admin_Setup_Guide.pdf"
  "2-setup/data-onboarding.html|Data_Onboarding_Guide.pdf"
  "2-setup/privacy-configuration.html|Privacy_Configuration.pdf"
  "2-setup/multi-agency-setup.html|Multi_Agency_Setup.pdf"
  "3-operate/dashboard-guide.html|Dashboard_Reports_Guide.pdf"
  "3-operate/analyst-playbook.html|Analyst_Playbook.pdf"
  "3-operate/billing-operations.html|Billing_Operations.pdf"
  "3-operate/collaboration-analysis.html|Collaboration_Analysis.pdf"
  "4-reference/troubleshooting.html|Troubleshooting_Guide.pdf"
  "4-reference/faq.html|FAQ.pdf"
  "4-reference/glossary.html|Glossary_Resources.pdf"
  "4-reference/attribute-reference.html|Attribute_Reference.pdf"
  # Legacy guides (kept for backward compatibility)
  "docs/core/Copilot_Analytics_Implementation_Guide.html|Copilot_Analytics_Implementation_Guide.pdf"
  "docs/core/Copilot_Analytics_Setup_Companion_Guide.html|Copilot_Analytics_Setup_Companion_Guide.pdf"
  "docs/playbooks/Copilot_Lifecycle_Billing_Playbook.html|Copilot_Lifecycle_Billing_Playbook.pdf"
  "docs/playbooks/Advanced_Viva_Insights_Collaboration_Guide.html|Advanced_Viva_Insights_Collaboration_Guide.pdf"
  "docs/playbooks/Copilot_Multi_Agency_Isolation_Architecture.html|Copilot_Multi_Agency_Isolation_Architecture.pdf"
  "docs/playbooks/Copilot_Multi_Agency_Default_Priority_Architecture.html|Copilot_Multi_Agency_Default_Priority_Architecture.pdf"
  "artifacts/Copilot_Analytics_FAQ.html|Copilot_Analytics_FAQ.pdf"
  "artifacts/Copilot_Analytics_QuickStart_CheatSheet.html|Copilot_Analytics_QuickStart_CheatSheet.pdf"
)

SUCCESS=0
FAIL=0

for entry in "${DOCS[@]}"; do
  IFS='|' read -r input output <<< "$entry"
  INPUT_PATH="$REPO_DIR/$input"
  OUTPUT_PATH="$PDF_DIR/$output"
  
  if [ ! -f "$INPUT_PATH" ]; then
    echo "  ✗ SKIP: $input (file not found)"
    ((FAIL++))
    continue
  fi
  
  echo -n "  Generating $output..."
  "$CHROME" --headless --disable-gpu \
    --print-to-pdf="$OUTPUT_PATH" \
    --no-pdf-header-footer \
    "file://$INPUT_PATH" 2>/dev/null
  
  if [ -f "$OUTPUT_PATH" ]; then
    SIZE=$(du -h "$OUTPUT_PATH" | cut -f1)
    echo " ✓ ($SIZE)"
    ((SUCCESS++))
  else
    echo " ✗ FAILED"
    ((FAIL++))
  fi
done

# Copy Setup Companion Guide to artifacts root as well
if [ -f "$PDF_DIR/Copilot_Analytics_Setup_Companion_Guide.pdf" ]; then
  cp "$PDF_DIR/Copilot_Analytics_Setup_Companion_Guide.pdf" "$REPO_DIR/artifacts/Copilot_Analytics_Setup_Companion_Guide.pdf"
  echo "  Copied Setup Companion Guide to artifacts/"
fi

echo ""
echo "Complete: $SUCCESS succeeded, $FAIL failed"
echo "PDFs saved to: $PDF_DIR"
