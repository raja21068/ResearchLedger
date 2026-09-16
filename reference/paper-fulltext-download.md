# Downloading paper full text

No API key, no service — just HTTP requests plus file writes, driven from whatever a literature
search step already produced for a candidate paper: `title`, and whichever of `pdfUrl`,
`openAccessUrl`, `landingPageUrl`, `doi`, or an OpenAlex work id are available.

Use `Bash` + `curl`, not the `WebFetch` tool, for the actual download — `WebFetch` can't set custom
headers, inspect raw bytes for a magic number, or cap response size, all of which matter here.

## Step 1 — build an ordered candidate URL list (stop at the first that works)

1. `pdfUrl` as-is, if present.
2. `openAccessUrl` as-is, if present.
3. If any of the known URLs/ids match an arXiv id
   (`arxiv\.org/(?:abs|pdf)/([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?|[a-z\-]+/[0-9]{7}(?:v[0-9]+)?)`), try
   `https://arxiv.org/pdf/<id>`.
4. If `landingPageUrl` matches an ACL Anthology id (`aclanthology\.org/([0-9]{4}\.[a-z\-]+\.[0-9]+)`),
   try `https://aclanthology.org/<id>.pdf`.
5. `landingPageUrl` as-is, if present.
6. `https://doi.org/<doi>` (bare `10.xxx`, or extracted from a `doi.org` URL), if a DOI is known.

## Step 2 — try each candidate in order until one succeeds

```bash
curl -sSL -A "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36" \
     -H "Accept: application/pdf,text/html,*/*;q=0.8" \
     --max-time 120 --max-filesize 52428800 \
     -o "candidate.bin" "$URL"
```

Then check what actually came back (a 200 with an HTML error page is common and must not be treated
as success):

```bash
head -c 5 candidate.bin                                            # compare to "%PDF-"
head -c 2048 candidate.bin | tr '[:upper:]' '[:lower:]' | grep -qE '<!doctype html|<html'
```

- First 5 bytes are `%PDF-` → it's a real PDF, done.
- Else, first 2 KB (lowercased) contains `<!doctype html` or `<html` → it's an HTML page (often a
  paywall or landing page) — still usable in a pinch, but prefer the next candidate if one remains.
- Otherwise this candidate failed (timeout, error page, empty body, or too large) — try the next one.

## Step 3 — write the result

1. Slugify the title: strip `\ / : * ? " < > |` and control characters, collapse whitespace,
   truncate to 80 chars + `…`.
2. On success: save to `research/literature/fulltext/<seq3>_<slug>.<pdf|html>`, where `<seq3>` is a
   zero-padded 3-digit sequence number (e.g. `007_some-paper-title.pdf`).
3. If every candidate failed: write a placeholder **`.txt`** at the same seq/slug instead, containing
   the failure reason and the full candidate list, e.g.:
   ```text
   # Full text not auto-downloaded (placeholder)

   Seq: 7
   Title: <title>
   Reason: <why every candidate failed>

   ## Candidate URLs tried (download manually, then replace this file with the PDF/HTML)

   - [pdf_direct] https://...
   - [arxiv_derived] https://arxiv.org/pdf/...

   Delete this .txt once you've placed the real file at the same name with a .pdf/.html extension.
   ```

## Step 4 — update the manifest

Append/update an entry in `research/literature/fulltext/manifest.json` (the single source of truth
for the sequence counter — never reorder or reuse a seq number):

```json
{
  "version": 1,
  "nextSeq": 8,
  "entries": [
    {
      "seq": 7, "title": "...", "doi": "10.xxx",
      "filename": "007_....pdf", "path": "research/literature/fulltext/007_....pdf",
      "kind": "pdf", "placeholder": false,
      "downloadedFrom": "https://arxiv.org/pdf/2402.17753", "source": "arxiv_derived",
      "createdAt": "<ISO8601>", "bytes": 1583234
    }
  ]
}
```

A placeholder entry instead adds `"placeholder": true`, `"candidates": [{"url": "...", "source": "..."}]`,
`"reason": "..."`, and omits `downloadedFrom`/`bytes`.

Never fetch a paper's full text from anywhere other than an open-access source the paper itself
publishes (arXiv, ACL Anthology, DOI resolver, publisher's own open-access link) — don't try to route
around a paywall.
