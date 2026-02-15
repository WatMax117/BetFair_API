# VPS Environment Validation - Manual Commands

Run these commands **step by step** on the VPS from the project root and share the raw outputs.

## Step 1: Confirm current working directory

```bash
pwd
```

**Expected:** Should show the project root (e.g., `/opt/netbet` or your project root path)

**Verify:** `docker-compose.yml` should exist in this directory:
```bash
ls -la docker-compose.yml
```

---

## Step 2: Verify the updated source exists on the VPS

```bash
grep -R "back and forward from now" .
```

**Expected Output:**
```
risk-analytics-ui/web/src/components/LeaguesAccordion.tsx:117:          label="Time window (hours back and forward from now)"
```

**If no output:** The VPS source is not updated. You need to pull/update the code first.

---

## Step 3: Confirm Docker build context

```bash
docker compose config | grep -A5 risk-analytics-ui-web
```

**Expected Output:**
```yaml
  risk-analytics-ui-web:
    build:
      context: ./risk-analytics-ui/web
      dockerfile: Dockerfile
    container_name: risk-analytics-ui-web
```

**Verify:** The `context:` should point to `./risk-analytics-ui/web` (or equivalent relative path)

---

## Step 4: Confirm container currently running

```bash
docker ps | grep risk-analytics-ui-web
```

**Expected Output:**
```
CONTAINER ID   IMAGE                    STATUS         PORTS                    NAMES
abc123def456   netbet-risk-analytics... Up 5 minutes   0.0.0.0:3000->80/tcp    risk-analytics-ui-web
```

**If no output:** Container is not running. You can check if it exists:
```bash
docker ps -a | grep risk-analytics-ui-web
```

---

## Step 5: Verify whether the running container contains the updated string

```bash
docker exec -it risk-analytics-ui-web sh -c "grep -R 'back and forward from now' /usr/share/nginx/html || echo NOT_FOUND"
```

**Expected Output (if found):**
```
/usr/share/nginx/html/assets/index-abc123.js:...back and forward from now...
```

**Expected Output (if NOT found):**
```
NOT_FOUND
```

**If NOT_FOUND:** The current image does not include the updated code. A rebuild is needed.

**If container is not running:** Skip this step or start it first:
```bash
docker compose -p netbet up -d risk-analytics-ui-web
```

---

## What to Share

After running all steps, please share the **raw outputs** of:

1. **Step 2** (source grep) - The grep output showing where the string was found
2. **Step 3** (build context) - The docker compose config output for risk-analytics-ui-web
3. **Step 5** (container grep) - Either the grep result or "NOT_FOUND"

---

## Quick Copy-Paste (All Steps)

```bash
# Step 1
pwd

# Step 2
grep -R "back and forward from now" .

# Step 3
docker compose config | grep -A5 risk-analytics-ui-web

# Step 4
docker ps | grep risk-analytics-ui-web

# Step 5
docker exec -it risk-analytics-ui-web sh -c "grep -R 'back and forward from now' /usr/share/nginx/html || echo NOT_FOUND"
```

---

## Alternative: Run Automated Validation Script

If you prefer, you can run the automated validation script which performs all these checks:

**Linux:**
```bash
bash scripts/validate_vps_environment.sh
```

**Windows PowerShell:**
```powershell
.\scripts\validate_vps_environment.ps1
```

The script will output all the information needed for validation.
