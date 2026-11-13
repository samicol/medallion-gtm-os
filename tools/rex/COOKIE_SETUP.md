# Cookie Setup Guide

> **2026-10-15:** Clay renamed the cookie to **`__Host-claysession`** and it may only show under `https://api.clay.com` (or not at all in Application → Cookies). Fastest: DevTools → Network → filter `api.clay.com` → any request → Request Headers → copy the `__Host-claysession=` value. Store the value as `{"claysession": "<value>"}`; Rex sends it under both names.


Clay's internal API authenticates with the session cookie your browser already has. You do not need a token or an OAuth app. Rex reuses your existing browser session.

---

## Step 1: Log in to Clay

Go to [app.clay.com](https://app.clay.com) and log in normally.

---

## Step 2: Open DevTools

Press **F12** (Windows/Linux) or **Cmd + Option + I** (Mac) to open Chrome DevTools.

---

## Step 3: Find the session cookie

**Option A: Application tab (easiest)**

1. Click the **Application** tab in DevTools
2. In the left sidebar, expand **Storage**, then **Cookies**
3. Click **`https://clay.com`** (or **`https://app.clay.com`**)
4. In the cookie list, find the row named **`claysession`**
5. Copy the full value from the **Value** column

**Option B: Network tab**

1. Click the **Network** tab in DevTools
2. Refresh the page or click anything in Clay
3. Click any request to `api.clay.com`
4. Open the **Headers** tab and find **Request Headers**
5. Find the `Cookie:` header
6. Copy the `claysession=...` portion (everything from `claysession=` to the next `;`)

---

## Step 4: Create `clay-session.json`

In the same directory as `clay_client.py`, create a file called `clay-session.json`:

```json
{
  "claysession": "s%3Ayour-full-cookie-value-here..."
}
```

The value typically starts with `s%3A` (URL-encoded `s:`).

---

## How long it lasts

The session cookie expires after a few weeks. When requests start returning 401 errors, repeat Steps 2 to 4 to refresh it.

---

## Security note

`clay-session.json` is listed in `.gitignore`. **Never commit it to a repository.**
