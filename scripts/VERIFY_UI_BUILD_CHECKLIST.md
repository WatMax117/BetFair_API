# UI Build Verification Checklist

This checklist helps verify that UI changes are included in the Docker build.

## Prerequisites
- SSH access to the VPS
- Docker and docker-compose installed
- Project root directory: `/opt/netbet` (or your project root)

## Quick Automated Verification

Run the automated script:
```bash
# On Linux VPS:
bash scripts/verify_ui_build.sh

# On Windows VPS (PowerShell):
.\scripts\verify_ui_build.ps1
```

## Manual Step-by-Step Verification

### Step 1: Verify Updated Source Exists on VPS

From the project root on the VPS:

```bash
grep -R "back and forward from now" .
```

**Expected Output:**
```
risk-analytics-ui/web/src/components/LeaguesAccordion.tsx:117:          label="Time window (hours back and forward from now)"
```

**If no results:** The change is not present in the deployed source directory. You need to pull/update the code first.

---

### Step 2: Confirm Docker Build Context

Run:

```bash
docker compose config | grep -A 5 "risk-analytics-ui-web"
```

**Check for:**
```yaml
build:
  context: ./risk-analytics-ui/web
  dockerfile: Dockerfile
```

**Verify:** The `context` path should point to `./risk-analytics-ui/web` relative to where you run `docker compose`.

**Also check:**
```bash
# Verify the directory exists and contains the source
ls -la risk-analytics-ui/web/src/components/LeaguesAccordion.tsx
```

---

### Step 3: Rebuild with Visible Confirmation

From the project root:

```bash
docker compose -p netbet build --no-cache risk-analytics-ui-web
```

**Watch for:**
- ✓ TypeScript compilation (should show no errors)
- ✓ Vite build process (should show "built in Xms")
- ✓ No unexpected cached layers (--no-cache ensures fresh build)

**Example successful output:**
```
[+] Building 45.2s (15/15) FINISHED
 => [risk-analytics-ui-web builder 6/7] RUN npm run build
 => [risk-analytics-ui-web builder 7/7] RUN npm run build
vite v5.x.x building for production...
✓ 123 modules transformed.
dist/index.html                   0.45 kB
dist/assets/index-abc123.js       245.67 kB
```

---

### Step 4: Restart Container

```bash
docker compose -p netbet up -d risk-analytics-ui-web
```

Wait a few seconds for the container to start:
```bash
docker ps | grep risk-analytics-ui-web
```

---

### Step 5: Verify Built Bundle Contains the Change

```bash
docker exec -it risk-analytics-ui-web sh
```

Inside the container:
```bash
grep -R "back and forward from now" /usr/share/nginx/html
```

**Expected Output:**
```
/usr/share/nginx/html/assets/index-abc123.js:...back and forward from now...
```

**If no results:** The built image does not include the updated code. Possible causes:
- Build context is wrong
- Source files weren't copied during build
- Build used cached layers despite --no-cache

**Exit the container:**
```bash
exit
```

---

### Step 6: Optional - Definitive Test

Temporarily modify a visible UI string to confirm the build process:

1. Edit `risk-analytics-ui/web/src/components/LeaguesAccordion.tsx`:
   ```tsx
   <Typography variant="h5" sx={{ mb: 2 }}>
     Risk Analytics — TEST BUILD
   </Typography>
   ```

2. Rebuild:
   ```bash
   docker compose -p netbet build --no-cache risk-analytics-ui-web
   docker compose -p netbet up -d risk-analytics-ui-web
   ```

3. Check in browser - the title should show "TEST BUILD"

4. If it doesn't appear: The build context or source path is incorrect.

5. Revert the test change after verification.

---

## Troubleshooting

### Issue: grep finds source but not in container

**Possible causes:**
1. Build context is wrong - check `docker compose config`
2. Files weren't copied - check Dockerfile `COPY` commands
3. Build used cache - ensure `--no-cache` flag

**Solution:**
```bash
# Verify build context
docker compose config | grep -A 3 "risk-analytics-ui-web"

# Check Dockerfile
cat risk-analytics-ui/web/Dockerfile

# Force rebuild everything
docker compose -p netbet build --no-cache --pull risk-analytics-ui-web
```

### Issue: Build succeeds but UI doesn't update

**Check:**
1. Browser cache - hard refresh (Ctrl+Shift+R or Cmd+Shift+R)
2. Container actually restarted: `docker ps --format "table {{.Names}}\t{{.Status}}" | grep risk-analytics-ui-web`
3. Nginx serving correct files: `docker exec risk-analytics-ui-web ls -la /usr/share/nginx/html/assets/`

### Issue: Source file not found on VPS

**Solution:**
```bash
# Pull latest code
git pull origin master

# Or if using a different deployment method, ensure files are synced
```

---

## Verification Summary

After completing all steps, confirm:

- [ ] `grep` finds "back and forward from now" in source code
- [ ] `docker compose config` shows correct build context
- [ ] Build completes without errors
- [ ] `grep` inside container finds the string in `/usr/share/nginx/html`
- [ ] Browser shows updated label (hard refresh if needed)

If all checks pass, the Docker build is correctly using the updated source code.
