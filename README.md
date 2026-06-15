# sideband-library-publish

Reusable GitHub composite action that **incrementally** syncs a folder of
per-part `.SchLib`/`.PcbLib` files to the Sideband library catalog.

- **new** parts → rendered (SVG + deck.gl geometry + 3D GLB) and published
- **removed** parts → deleted from the catalog
- **existing** parts → skipped (never re-rendered)

Library metadata (title / description / author / the markdown "about") is
**admin-owned** and never touched — the action only ensures `org`/`repo`.

One file == one part: split merged libraries upstream before calling this.

```yaml
- uses: Fermium/sideband-library-publish@v1
  with:
    slug: my-library
    org: acme
    repo: parts
    source-dir: out/parts        # folder of per-part .SchLib/.PcbLib
    api-url: ${{ secrets.SIDEBAND_API_URL }}
    catalog-url: ${{ secrets.SIDEBAND_CATALOG_URL }}
    token: ${{ secrets.SIDEBAND_PUBLISH_TOKEN }}
    max-per-run: "0"             # cap new items/run for huge first backfills
```
