# Line Endings (LF for Unix-Deployed Files)

The repo uses **`.gitattributes`** so that shell scripts, SQL, Python, and YAML use **LF** on checkout. This avoids CRLF issues when deploying to Linux (e.g. VPS).

---

## 3. Local Git config (Windows)

Run once inside the repo so Git does not override line endings:

```bash
git config core.autocrlf false
git config core.eol lf
```

We rely on `.gitattributes` to control line endings, not global `autocrlf`.

---

## 4. Verify before deployment

**Check that tracked `.sh` files are LF:**

```bash
git ls-files --eol | grep '\.sh'
```

Expect `w/lf` and `i/lf` for working tree and index (not `crlf`).

**Optional check on VPS after deploy:**

```bash
file /opt/netbet/scripts/*.sh
```

Expected: `ASCII text executable` (not “with CRLF line terminators”).

---

## 5. No CRLF workarounds

After normalization:

- No `sed -i 's/\r$//'` or `dos2unix` in deploy scripts.
- No patching of line endings on the VPS after upload.
- `.sh` / `.sql` / `.py` / `.yml` / `.yaml` are stored and checked out as LF.
