/**
 * lib/clay-api.js: Single source of truth for all api.clay.com/v3 traffic.
 *
 * All other modules import from here; never call fetch on the Clay API
 * directly.
 *
 * Public surface:
 *   API_BASE                                       constant base URL
 *   clayApi(path, options)                         low-level fetch helper
 *   getTable(tableId)                              GET /tables/{id}
 *   getRecordIds(tableId, viewId)                  GET /tables/{id}/views/{viewId}/records/ids
 *   bulkFetchRecords(tableId, recordIds, fields?)  POST /tables/{id}/bulk-fetch-records (NO cost data; slim shape)
 *   fetchRecord(tableId, recordId, fields?)        GET /tables/{id}/records/{rid} (FULL externalContent; use for cost)
 *   fetchRecordsParallel(tId, recordIds, fids, o)  bounded-concurrency fan-out of fetchRecord
 *   createField(tableId, viewId, fieldConfig)      POST /tables/{id}/fields
 *   createSource(workspaceId, tableId, sourceCfg)  POST /sources
 *   getSource(sourceId)                            GET  /sources/{id}
 *
 *   cacheExtraction(workspaceId, tableId, x)       IndexedDB write
 *   loadExtraction(workspaceId, tableId)           IndexedDB read (null if >1h)
 *   clearExtraction(workspaceId, tableId)          IndexedDB delete
 *
 * Conventions:
 *   - ES module, no top-level side effects
 *   - Console logs prefixed with [claylens:clay-api]
 *   - Throws Error on non-2xx; 401 sets err.code='SESSION_EXPIRED'
 *   - Strips heavy hiddenValue.messages before caching to IDB (saves ~80%)
 *
 * Reference: clay_client.py (proven Clay API patterns).
 */

const LOG = '[claylens:clay-api]';

export const API_BASE = 'https://api.clay.com/v3';

// X-Clay-Frontend-Version is required by Clay's edge for /v3 traffic. The real
// app sends a build hash; 'unknown' is accepted by the backend for our use.
const FRONTEND_VERSION = 'unknown';

// bulkFetchRecords paging
const BULK_PAGE_SIZE = 100;

// 429 retry
const RETRY_DELAYS_MS = [250, 500, 1000];

// IndexedDB
const DB_NAME = 'claylens';
const DB_VERSION = 1;
const STORE = 'extractions';
const FRESH_MS = 30 * 60 * 1000; // <30min → fresh
const STALE_MS = 60 * 60 * 1000; // <60min → stale, >60min → expired

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// ── Low-level fetch helper ───────────────────────────────────────────────────

/**
 * Low-level wrapper around fetch() for Clay's /v3 API.
 *
 * - Sends `credentials: 'include'` so the browser's claysession cookie is sent.
 * - Adds `X-Clay-Frontend-Version` header (Clay edge rejects requests without it).
 * - JSON-encodes body if it's a plain object.
 * - On non-2xx, parses the error body and throws Error(message).
 *   On 401, the thrown error has `.code = 'SESSION_EXPIRED'` so the side panel
 *   can show a re-login toast.
 *
 * @param {string} path  e.g. '/tables/{id}' (leading slash required)
 * @param {RequestInit & { body?: any }} [options]
 * @returns {Promise<any>}
 */
export async function clayApi(path, options = {}) {
  const url = API_BASE + path;
  const headers = {
    Accept: 'application/json',
    'X-Clay-Frontend-Version': FRONTEND_VERSION,
    ...(options.headers || {}),
  };

  let body = options.body;
  if (body !== undefined && body !== null && typeof body !== 'string' &&
      !(body instanceof FormData) && !(body instanceof Blob) &&
      !(body instanceof ArrayBuffer)) {
    body = JSON.stringify(body);
    if (!headers['Content-Type']) headers['Content-Type'] = 'application/json';
  }

  const init = {
    method: options.method || 'GET',
    credentials: 'include',
    headers,
    ...(body !== undefined ? { body } : {}),
  };

  // Carry through any unrelated fetch options (signal, mode, etc.).
  for (const k of ['signal', 'mode', 'cache', 'redirect', 'referrer', 'integrity']) {
    if (options[k] !== undefined) init[k] = options[k];
  }

  const res = await fetch(url, init);

  if (!res.ok) {
    let errBody = null;
    try {
      const text = await res.text();
      try { errBody = JSON.parse(text); } catch { errBody = text; }
    } catch { /* ignore */ }

    let message;
    if (errBody && typeof errBody === 'object') {
      message = errBody.message || errBody.error || errBody.detail ||
                JSON.stringify(errBody);
    } else if (typeof errBody === 'string' && errBody) {
      message = errBody;
    } else {
      message = `${res.status} ${res.statusText}`;
    }

    const err = new Error(`Clay API ${res.status}: ${message}`);
    err.status = res.status;
    err.body = errBody;
    if (res.status === 401) {
      err.code = 'SESSION_EXPIRED';
      err.message = 'Clay session expired. Refresh the Clay tab and try again.';
    } else if (res.status === 429) {
      err.code = 'RATE_LIMITED';
    }
    throw err;
  }

  // 204 No Content / empty body
  if (res.status === 204) return null;
  const text = await res.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

// ── High-level helpers ───────────────────────────────────────────────────────

/**
 * GET /tables/{id}: full table dict including fields, views.
 *
 * Response shape mirrors get_table() in clay_client.py. Caller may need to
 * unwrap `.table` for the inner shape (Clay sometimes wraps).
 */
export async function getTable(tableId) {
  if (!tableId) throw new Error('getTable: tableId is required');
  return clayApi(`/tables/${encodeURIComponent(tableId)}`);
}

/**
 * GET /tables/{id}/views/{viewId}/records/ids: flat list of record IDs.
 *
 * Filters out the 'search' placeholder, as clay_client.py does.
 */
export async function getRecordIds(tableId, viewId) {
  if (!tableId || !viewId) {
    throw new Error('getRecordIds: tableId and viewId are required');
  }
  const res = await clayApi(
    `/tables/${encodeURIComponent(tableId)}/views/${encodeURIComponent(viewId)}/records/ids`,
  );
  const ids = (res && res.results) || [];
  return ids.filter((rid) => rid !== 'search');
}

/**
 * POST /tables/{id}/bulk-fetch-records: fetch a single page of records.
 *
 * IMPORTANT: this fetches AT MOST one page. Caller is responsible for paging
 * (background.js:analyze handles 100-row pages, 2 in parallel). If the caller
 * passes >100 IDs we still send them all (Clay accepts up to a few hundred),
 * but we warn: staying ≤100 keeps payloads under ~1MB and 429-friendly.
 *
 * WARNING: DO NOT USE FOR COST EXTRACTION.
 *   Clay's bulk-fetch endpoint returns the SLIM cell shape used for grid
 *   rendering: `{ value, metadata: { status }, ... }`. It OMITS
 *   `externalContent.fullValue` (where totalCostToAIProvider, totalInputTokens,
 *   totalOutputTokens, actualModel, etc. live). For anything that needs cost
 *   data, use `fetchRecord()` / `fetchRecordsParallel()` (per-record GET).
 *   See clay_client.py (`fetch_all_records_full`) for the
 *   reference Python pattern.
 *
 * On 429: exponential backoff (250ms, 500ms, 1s), max 3 retries, then re-throw.
 */
export async function bulkFetchRecords(tableId, recordIds, fieldIds = null) {
  if (!tableId) throw new Error('bulkFetchRecords: tableId is required');
  if (!Array.isArray(recordIds)) {
    throw new Error('bulkFetchRecords: recordIds must be an array');
  }
  if (recordIds.length === 0) return [];
  if (recordIds.length > BULK_PAGE_SIZE) {
    console.log(LOG, `bulkFetchRecords: page size ${recordIds.length} > ${BULK_PAGE_SIZE} (caller should page)`);
  }

  const body = { recordIds };
  if (fieldIds && fieldIds.length) body.fieldIds = fieldIds;

  let lastErr = null;
  // initial attempt + RETRY_DELAYS_MS.length retries
  for (let attempt = 0; attempt <= RETRY_DELAYS_MS.length; attempt++) {
    try {
      const res = await clayApi(
        `/tables/${encodeURIComponent(tableId)}/bulk-fetch-records`,
        { method: 'POST', body },
      );
      return (res && res.results) || [];
    } catch (err) {
      lastErr = err;
      if (err.code !== 'RATE_LIMITED') throw err;
      const delay = RETRY_DELAYS_MS[attempt];
      if (delay === undefined) break; // exhausted retries
      console.log(LOG, `429: backoff ${delay}ms (attempt ${attempt + 1}/${RETRY_DELAYS_MS.length})`);
      await sleep(delay);
    }
  }
  throw lastErr || new Error('bulkFetchRecords: exhausted retries');
}

/**
 * GET /tables/{tableId}/records/{recordId}: single full record with externalContent.
 *
 * Use this (not `bulkFetchRecords`) when you need cost data. Clay's
 * bulk-fetch-records endpoint returns the slim shape used for grid rendering
 * and omits `externalContent.fullValue` where cost / token / model info lives.
 *
 * Mirrors the per-record fetch pattern in Rex's own
 * clay_client.py:fetch_all_records_full / get_cell_costs (../../clay_client.py).
 *
 * Response shape:
 *   { id, cells: { [fieldId]: { metadata, externalContent, extendedContent, value } } }
 *
 * On 429: exponential backoff (250ms, 500ms, 1s), max 3 retries, then re-throw.
 *
 * @param {string} tableId
 * @param {string} recordId
 * @param {string[]|null} [fieldIds]  optional client-side filter; server may
 *                                    not support fieldIds on this endpoint, so
 *                                    we fetch all cells and filter locally.
 * @returns {Promise<{id: string, cells: object}>}
 */
export async function fetchRecord(tableId, recordId, fieldIds = null) {
  if (!tableId) throw new Error('fetchRecord: tableId is required');
  if (!recordId) throw new Error('fetchRecord: recordId is required');

  let lastErr = null;
  for (let attempt = 0; attempt <= RETRY_DELAYS_MS.length; attempt++) {
    try {
      const res = await clayApi(
        `/tables/${encodeURIComponent(tableId)}/records/${encodeURIComponent(recordId)}`,
      );
      // Some Clay endpoints wrap as { record: {...} }; support either.
      const rec = (res && res.record && typeof res.record === 'object') ? res.record : res;
      if (!rec || typeof rec !== 'object') return { id: recordId, cells: {} };

      // Normalize id (record-level GET returns `id`; some shapes use `recordId`).
      if (!rec.id && rec.recordId) rec.id = rec.recordId;
      if (!rec.id) rec.id = recordId;

      // Optional client-side fieldIds filter.
      if (fieldIds && fieldIds.length && rec.cells && typeof rec.cells === 'object') {
        const want = new Set(fieldIds);
        const filtered = {};
        for (const [fid, cell] of Object.entries(rec.cells)) {
          if (want.has(fid)) filtered[fid] = cell;
        }
        rec.cells = filtered;
      }
      return rec;
    } catch (err) {
      lastErr = err;
      if (err.code !== 'RATE_LIMITED') throw err;
      const delay = RETRY_DELAYS_MS[attempt];
      if (delay === undefined) break;
      console.log(LOG, `fetchRecord 429: backoff ${delay}ms (attempt ${attempt + 1}/${RETRY_DELAYS_MS.length}) for`, recordId);
      await sleep(delay);
    }
  }
  throw lastErr || new Error('fetchRecord: exhausted retries');
}

/**
 * Fetch many records with bounded concurrency. Mirrors
 * `fetch_all_records_full` in clay_client.py (default 20
 * workers; ~27ms/record on a healthy connection).
 *
 * Designed to be a drop-in replacement for the bulk-fetch + paging loop in
 * background.js:handleAnalyze when cost data is needed.
 *
 * onProgress is fired periodically (every ~5% of total or every 25 records,
 * whichever is sooner) and once on completion. The fired payload contains:
 *   { completed, total, partialRecords }
 *
 * The `partialRecords` array is the running list of records fetched so far;
 * the caller can run extractPage() on it for live mid-flight aggregates.
 *
 * @param {string} tableId
 * @param {string[]} recordIds
 * @param {string[]|null} [fieldIds]
 * @param {{ workers?: number, onProgress?: Function }} [opts]
 * @returns {Promise<Array<{id: string, cells: object}>>}
 */
export async function fetchRecordsParallel(tableId, recordIds, fieldIds = null,
                                           { workers = 20, onProgress } = {}) {
  if (!tableId) throw new Error('fetchRecordsParallel: tableId is required');
  if (!Array.isArray(recordIds)) {
    throw new Error('fetchRecordsParallel: recordIds must be an array');
  }
  if (recordIds.length === 0) return [];

  const total = recordIds.length;
  const out = new Array(total);
  let completed = 0;
  let cursor = 0;
  // Snapshot of records since last onProgress fire; keeps memory flat-ish for
  // huge tables while still letting the caller compute partial aggregates.
  const partialRecords = [];

  // Progress throttle: every 5% of total or every 25 records.
  const progressEvery = Math.max(1, Math.min(25, Math.floor(total / 20) || 1));
  let nextProgressAt = progressEvery;

  async function worker() {
    while (true) {
      const idx = cursor++;
      if (idx >= total) return;
      const rid = recordIds[idx];
      try {
        const rec = await fetchRecord(tableId, rid, fieldIds);
        out[idx] = rec;
        partialRecords.push(rec);
      } catch (err) {
        // Log + record an empty placeholder so the run continues; matches the
        // ThreadPoolExecutor.as_completed pattern in clay_client.py.
        console.log(LOG, 'fetchRecord failed for', rid, '-', err?.message || err);
        out[idx] = { id: rid, cells: {}, _fetchError: err?.message || String(err) };
      } finally {
        completed++;
        if (typeof onProgress === 'function' && completed >= nextProgressAt) {
          try {
            onProgress({
              completed,
              total,
              partialRecords: partialRecords.slice(),
            });
          } catch { /* swallow listener errors */ }
          // Reset partial buffer so we don't keep growing unbounded for huge tables.
          partialRecords.length = 0;
          nextProgressAt = completed + progressEvery;
        }
      }
    }
  }

  const pool = Math.max(1, Math.min(workers, total));
  await Promise.all(Array.from({ length: pool }, () => worker()));

  // Final progress tick so callers can flush any remaining partials.
  if (typeof onProgress === 'function') {
    try {
      onProgress({
        completed,
        total,
        partialRecords: partialRecords.slice(),
      });
    } catch { /* swallow */ }
  }

  return out;
}

/**
 * POST /tables/{id}/fields: create a column.
 *
 * Mirrors clay_client.py:create_column. `viewId` is sent as activeViewId so Clay
 * scopes the new field to the right view.
 */
export async function createField(tableId, viewId, fieldConfig) {
  if (!tableId) throw new Error('createField: tableId is required');
  if (!fieldConfig || typeof fieldConfig !== 'object') {
    throw new Error('createField: fieldConfig must be an object');
  }
  const body = { ...fieldConfig };
  if (viewId) body.activeViewId = viewId;

  const res = await clayApi(
    `/tables/${encodeURIComponent(tableId)}/fields`,
    { method: 'POST', body },
  );

  const field = (res && res.field) || res;
  if (field && field.settingsError) {
    const err = new Error(
      `Clay rejected column '${fieldConfig.name}' (${field.id}): ${field.settingsError}`,
    );
    err.code = 'COLUMN_CONFIG_ERROR';
    err.field = field;
    throw err;
  }
  return field;
}

/**
 * POST /sources: create a source (e.g. Find People, CSV import).
 *
 * sourceConfig shape varies by sourceType; see clay_client.py for examples.
 */
export async function createSource(workspaceId, tableId, sourceConfig) {
  if (!workspaceId) throw new Error('createSource: workspaceId is required');
  if (!tableId) throw new Error('createSource: tableId is required');
  if (!sourceConfig || typeof sourceConfig !== 'object') {
    throw new Error('createSource: sourceConfig must be an object');
  }
  const body = {
    workspaceId: String(workspaceId),
    tableId,
    ...sourceConfig,
  };
  return clayApi('/sources', { method: 'POST', body });
}

/**
 * GET /sources/{id}: fetch a source's full config. Useful for inspecting a
 * Find People source's `include_company_filter_identifier_count`: an
 * inactive company filter (0) means the source can return unrelated people.
 */
export async function getSource(sourceId) {
  if (!sourceId) throw new Error('getSource: sourceId is required');
  return clayApi(`/sources/${encodeURIComponent(sourceId)}`);
}

// ── IndexedDB cache ──────────────────────────────────────────────────────────

/**
 * Open the claylens IndexedDB lazily. One DB, one store, keyed by
 * `${workspaceId}:${tableId}`. Records are { cacheKey, extractedAt, ... }.
 */
function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = (e) => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'cacheKey' });
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error || new Error('IndexedDB open failed'));
    req.onblocked = () => {
      console.log(LOG, 'IndexedDB open blocked: another tab holds the DB open');
    };
  });
}

function tx(db, mode) {
  const t = db.transaction(STORE, mode);
  return { t, store: t.objectStore(STORE) };
}

function cacheKey(workspaceId, tableId) {
  return `${workspaceId}:${tableId}`;
}

/**
 * Strip heavy `hiddenValue.messages` arrays from cell payloads before caching.
 *
 * Messages arrays are ~80% of bulk-fetch
 * payload weight and we never need them for cost/aggregation. Operates on
 * extraction.cells (Array<extractCostFields output>): also strips full_value
 * if it carries a `messages` field by accident.
 */
function lightenForCache(extraction) {
  if (!extraction || typeof extraction !== 'object') return extraction;
  // Only operate on the bulky shape; totals/byColumn/byRow are already small.
  if (!Array.isArray(extraction.cells)) return extraction;

  const cells = extraction.cells.map((cell) => {
    if (!cell || typeof cell !== 'object') return cell;
    if (cell.full_value && typeof cell.full_value === 'object') {
      const fv = { ...cell.full_value };
      if (fv.messages) delete fv.messages;
      return { ...cell, full_value: fv };
    }
    return cell;
  });
  return { ...extraction, cells };
}

/**
 * Persist an extraction to IndexedDB. Stamps `extractedAt: Date.now()`.
 *
 * Strips hiddenValue.messages before write.
 */
export async function cacheExtraction(workspaceId, tableId, extraction) {
  if (!workspaceId || !tableId) {
    throw new Error('cacheExtraction: workspaceId and tableId are required');
  }
  const key = cacheKey(workspaceId, tableId);
  const lightened = lightenForCache(extraction);
  const record = {
    cacheKey: key,
    workspaceId: String(workspaceId),
    tableId: String(tableId),
    extractedAt: Date.now(),
    ...lightened,
  };
  const db = await openDb();
  try {
    await new Promise((resolve, reject) => {
      const { t, store } = tx(db, 'readwrite');
      store.put(record);
      t.oncomplete = () => resolve();
      t.onerror = () => reject(t.error || new Error('IndexedDB put failed'));
      t.onabort = () => reject(t.error || new Error('IndexedDB put aborted'));
    });
    console.log(LOG, 'cached extraction', key);
  } finally {
    db.close();
  }
}

/**
 * Read a cached extraction.
 *
 * Returns null if missing or older than 1h. If older than 30min but younger
 * than 1h, returns the record with `isStale: true` so the UI can show a
 * "refresh recommended" hint.
 */
export async function loadExtraction(workspaceId, tableId) {
  if (!workspaceId || !tableId) {
    throw new Error('loadExtraction: workspaceId and tableId are required');
  }
  const key = cacheKey(workspaceId, tableId);
  const db = await openDb();
  try {
    const record = await new Promise((resolve, reject) => {
      const { t, store } = tx(db, 'readonly');
      const req = store.get(key);
      req.onsuccess = () => resolve(req.result || null);
      req.onerror = () => reject(req.error || new Error('IndexedDB get failed'));
      // ignore tx complete: single get
      t.onerror = () => reject(t.error || new Error('IndexedDB tx failed'));
    });
    if (!record) return null;

    const age = Date.now() - (record.extractedAt || 0);
    if (age > STALE_MS) {
      console.log(LOG, 'cache expired (age=', age, 'ms) for', key);
      return null;
    }
    return { ...record, isStale: age > FRESH_MS };
  } finally {
    db.close();
  }
}

/**
 * Delete a cached extraction (called by analyze with force=true).
 */
export async function clearExtraction(workspaceId, tableId) {
  if (!workspaceId || !tableId) {
    throw new Error('clearExtraction: workspaceId and tableId are required');
  }
  const key = cacheKey(workspaceId, tableId);
  const db = await openDb();
  try {
    await new Promise((resolve, reject) => {
      const { t, store } = tx(db, 'readwrite');
      store.delete(key);
      t.oncomplete = () => resolve();
      t.onerror = () => reject(t.error || new Error('IndexedDB delete failed'));
    });
    console.log(LOG, 'cleared extraction', key);
  } finally {
    db.close();
  }
}
