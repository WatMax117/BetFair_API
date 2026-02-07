#!/usr/bin/env python3
"""Fix broken POSTGRES_* env in docker-compose.yml (values lost in heredoc)."""
import re
path = "/opt/netbet/docker-compose.yml"
with open(path) as f:
    c = f.read()
# Replace broken "POSTGRES_DB: \n" (and similar) with proper defaults
c = re.sub(r'(POSTGRES_DB):\s*\\\s*$', r'\1: ${POSTGRES_DB:-netbet}', c, flags=re.MULTILINE)
c = re.sub(r'(POSTGRES_USER):\s*\\\s*$', r'\1: ${POSTGRES_USER:-netbet}', c, flags=re.MULTILINE)
c = re.sub(r'(POSTGRES_PASSWORD):\s*\\\s*$', r'\1: ${POSTGRES_PASSWORD:-netbet}', c, flags=re.MULTILINE)
with open(path, "w") as f:
    f.write(c)
print("Fixed")
