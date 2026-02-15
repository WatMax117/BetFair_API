#!/usr/bin/env bash
# Run all three staged deploy+validate steps on the VPS in order.
# Does not proceed to the next stage unless the current stage validation passes.
# Run on VPS: cd /opt/netbet && ./scripts/vps_run_all_stages.sh
#
# Note: Stage 1 validation requires at least one snapshot cycle (15–20 min) after deploy.
# If Stage 1 validation fails only on "recent rows with non-null impedance", wait and re-run:
#   ./scripts/vps_stage1_deploy_and_validate.sh   # re-run validation only after waiting (or run validate block manually)
# Or run stages individually: vps_stage1_deploy_and_validate.sh, then after 15–20 min re-run its validation, then stage2, then stage3.

set -euo pipefail

REPO_ROOT="${REPO_ROOT:-/opt/netbet}"
cd "$REPO_ROOT"

echo "Running staged deploy and validation (VPS). Do not proceed between stages unless validation passes."
echo ""

echo "========== STAGE 1 =========="
"$REPO_ROOT/scripts/vps_stage1_deploy_and_validate.sh"
echo ""
read -r -p "Stage 1 passed? Proceed to Stage 2? [y/N] " REPLY
if [[ ! "$REPLY" =~ ^[yY]$ ]]; then
  echo "Stopping. Run vps_stage2_deploy_and_validate.sh when ready."
  exit 0
fi

echo ""
echo "========== STAGE 2 =========="
"$REPO_ROOT/scripts/vps_stage2_deploy_and_validate.sh"
echo ""
read -r -p "Stage 2 passed? Proceed to Stage 3? [y/N] " REPLY
if [[ ! "$REPLY" =~ ^[yY]$ ]]; then
  echo "Stopping. Run vps_stage3_deploy_and_validate.sh when ready."
  exit 0
fi

echo ""
echo "========== STAGE 3 =========="
"$REPO_ROOT/scripts/vps_stage3_deploy_and_validate.sh"

echo ""
echo "========== All stages complete. Confirm UI in browser (hard refresh / incognito). =========="
