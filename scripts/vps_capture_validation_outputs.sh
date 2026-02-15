#!/usr/bin/env bash
# Run on VPS: cd /opt/netbet && ./scripts/vps_capture_validation_outputs.sh
# Captures required validation outputs to VALIDATION_OUTPUTS.txt for pasting back.
# Execute steps in order; do not run this in one go before Step 2 wait (15–20 min).

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/netbet}"
OUT="${REPO_ROOT}/VALIDATION_OUTPUTS.txt"

cd "$REPO_ROOT"

append_section() {
  echo "" >> "$OUT"
  echo "========== $1 ==========" >> "$OUT"
  echo "" >> "$OUT"
}

# Step 1
echo "Step 1: Apply Postgres credentials..."
./scripts/vps_apply_postgres_env.sh
append_section "Step 1 — grep POSTGRES_.*_PASSWORD"
grep -E 'POSTGRES_.*_PASSWORD' /opt/netbet/.env >> "$OUT" 2>&1 || true

echo "Step 1 done. Outputs appended to $OUT"
echo "Next: Step 2 — Restart REST client and wait 15–20 min, then run:"
echo "  VALIDATE_ONLY=1 ./scripts/vps_stage1_deploy_and_validate.sh"
echo "  (Append Stage 1 full output to $OUT or paste it in your response.)"
echo ""
echo "Then run Stage 2 and Stage 3 as in VPS_DEPLOY_RUNBOOK_VALIDATION.md and paste all outputs."
