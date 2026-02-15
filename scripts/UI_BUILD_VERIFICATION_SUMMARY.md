# UI Build Verification Summary

## Local Verification (Completed)

✅ **Source Code Verified:**
- The string "back and forward from now" exists in `risk-analytics-ui/web/src/components/LeaguesAccordion.tsx` at line 117
- Local grep confirms: `label="Time window (hours back and forward from now)"`

✅ **Docker Build Context Verified:**
- Build context is correctly set to: `./risk-analytics-ui/web`
- Dockerfile exists and copies source files correctly

## What to Do on VPS

### Option 1: Automated Verification (Recommended)

Run the automated script from the project root on the VPS:

**Linux:**
```bash
bash scripts/verify_ui_build.sh
```

**Windows PowerShell:**
```powershell
.\scripts\verify_ui_build.ps1
```

This script will:
1. Verify the source code contains the change
2. Check Docker build context
3. Rebuild with `--no-cache`
4. Restart the container
5. Verify the built bundle contains the change
6. Provide a summary report

### Option 2: Manual Step-by-Step

Follow the detailed checklist in `scripts/VERIFY_UI_BUILD_CHECKLIST.md`

## Quick Manual Commands

If you prefer to run commands manually, here are the key steps:

```bash
# 1. Verify source exists
grep -R "back and forward from now" .

# 2. Check build context
docker compose config | grep -A 5 "risk-analytics-ui-web"

# 3. Rebuild
docker compose -p netbet build --no-cache risk-analytics-ui-web

# 4. Restart
docker compose -p netbet up -d risk-analytics-ui-web

# 5. Verify in container
docker exec risk-analytics-ui-web sh -c "grep -r 'back and forward from now' /usr/share/nginx/html"
```

## Expected Results

### Step 1 Output:
```
risk-analytics-ui/web/src/components/LeaguesAccordion.tsx:117:          label="Time window (hours back and forward from now)"
```

### Step 2 Output:
Should show:
```yaml
build:
  context: ./risk-analytics-ui/web
  dockerfile: Dockerfile
```

### Step 3 Output:
Should show successful Vite build:
```
vite v5.x.x building for production...
✓ 123 modules transformed.
dist/index.html                   0.45 kB
dist/assets/index-abc123.js       245.67 kB
```

### Step 5 Output:
Should find the string in the built JavaScript bundle:
```
/usr/share/nginx/html/assets/index-abc123.js:...back and forward from now...
```

## If Verification Fails

### Source Not Found
- Pull latest code: `git pull origin master`
- Verify you're in the correct directory
- Check file permissions

### Build Context Wrong
- Verify you're running `docker compose` from the project root
- Check `docker-compose.yml` and `risk-analytics-ui/docker-compose.yml`
- Ensure paths are relative to where you run the command

### String Not in Container
- Ensure `--no-cache` flag was used
- Check Dockerfile `COPY` commands
- Verify build completed successfully (no errors)
- Check container actually restarted: `docker ps | grep risk-analytics-ui-web`

### UI Doesn't Update in Browser
- Hard refresh: Ctrl+Shift+R (Windows/Linux) or Cmd+Shift+R (Mac)
- Clear browser cache
- Check container is running: `docker ps`
- Verify nginx is serving files: `docker exec risk-analytics-ui-web ls -la /usr/share/nginx/html/assets/`

## Files Created

1. `scripts/verify_ui_build.sh` - Automated bash script for Linux VPS
2. `scripts/verify_ui_build.ps1` - Automated PowerShell script for Windows VPS
3. `scripts/VERIFY_UI_BUILD_CHECKLIST.md` - Detailed manual checklist
4. `scripts/UI_BUILD_VERIFICATION_SUMMARY.md` - This summary document

## Next Steps

1. **On VPS:** Run the automated script or follow manual steps
2. **Report back:** Share the outputs from each step
3. **If issues:** Check troubleshooting section or run definitive test (Step 6 in checklist)

The verification process will conclusively determine whether:
- ✅ The correct source code is being used
- ✅ Docker build context is correct
- ✅ The built image contains the updated code
- ✅ The container is serving the updated files
