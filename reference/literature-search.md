# Literature search (OpenAlex)

Keyless. No account, no API key required — OpenAlex's public pool works fine for occasional
searches; an API key or `mailto` only raises the rate limit and is never required. Omit both.

**Endpoint**: `GET https://api.openalex.org/works`

## Building the query URL

```text
search    = <the search text>, trimmed                                    (always set)
per-page  = clamp(requested, 1, 50), default 20                            (always set)
filter    = "publication_year:<from>-<to>"        both yearFrom and yearTo given
          | "publication_year:>{yearFrom-1}"       only yearFrom given
          | "publication_year:<{yearTo+1}"         only yearTo given
          , plus ",is_oa:true" appended             if open-access-only was requested
          (omit the filter param entirely if none of the above apply)
sort      = "cited_by_count:desc"      if sorting by citation count
          | "publication_date:desc"    if sorting by recency
          (omit the sort param entirely for relevance, the default)
select    = "id,doi,title,display_name,publication_year,publication_date,primary_location,
             open_access,authorships,cited_by_count,abstract_inverted_index,type"   (always set)
```

Example: `https://api.openalex.org/works?search=cross-modal%20localization&per-page=20&select=id,doi,title,display_name,publication_year,publication_date,primary_location,open_access,authorships,cited_by_count,abstract_inverted_index,type`

Fetch it with `WebFetch` and parse the JSON response — no custom headers are needed for this one
(unlike full-text download, see `paper-fulltext-download.md`).

## Mapping a result

For each item in `results[]`, extract:

- `id` → the OpenAlex work URL (keep it — `paper-fulltext-download.md` and manifest entries use it)
- `title` → `display_name` (fall back to `title`, or `"(untitled)"`)
- `year` → `publication_year`
- `doi`
- `venue` → `primary_location.source.display_name`
- `authors` → first 4 of `authorships[].author.display_name`
- `citedByCount` → `cited_by_count`
- `openAccessUrl` → `open_access.oa_url`
- `openAccessStatus` → `open_access.oa_status`
- `landingPageUrl` → `primary_location.landing_page_url`
- `pdfUrl` → `primary_location.pdf_url`
- `type`
- `abstract` → reconstruct from `abstract_inverted_index` (a word → [positions] map): place each
  word at every listed position, then join by position order with spaces. Truncate the result to
  600 characters + `…` if longer.

Total hit count is `meta.count` — if it's larger than how many you actually pulled back, say so
("N total matches, showing the top 20") rather than implying the list is exhaustive.

## After a search

The search itself doesn't write anything to disk — it's a pure lookup. When a result is worth
keeping as part of the research record, log it as evidence (see `research-assets.md`) with a
`citation` noting where it came from, or — if the paper's actual content is needed, not just its
metadata — fetch the full text (see `paper-fulltext-download.md`) using the `pdfUrl`/
`openAccessUrl`/`doi`/`landingPageUrl` fields this search just returned.

Never fabricate a citation, DOI, or abstract that didn't come back from this search.
