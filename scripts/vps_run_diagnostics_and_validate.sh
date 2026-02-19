#!/bin/bash
# Run market inventory diagnostics on VPS and print validation evidence.
# Execute on VPS: cd /opt/netbet && ./scripts/vps_run_diagnostics_and_validate.sh 2026-02-16

set -e
DATE="${1:-2026-02-16}"
cd /opt/netbet

echo "========== EXACT COMMAND EXECUTED =========="
echo "./scripts/run_diagnose_market_inventory_docker.sh $DATE"
echo ""

./scripts/run_diagnose_market_inventory_docker.sh "$DATE"

echo ""
echo "========== DIRECTORY LISTING =========="
ls -lah /opt/netbet/data_exports/diagnostics/

echo ""
echo "========== FULL CONTENTS: diagnostics_report_${DATE//-/_}.txt =========="
cat "/opt/netbet/data_exports/diagnostics/diagnostics_report_${DATE//-/_}.txt"

echo ""
echo "========== FIRST 20 LINES: market_type_inventory_${DATE//-/_}.csv =========="
head -n 20 "/opt/netbet/data_exports/diagnostics/market_type_inventory_${DATE//-/_}.csv"
