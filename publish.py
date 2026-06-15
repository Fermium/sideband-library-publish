#!/usr/bin/env python3
"""Incrementally sync a folder of per-part .SchLib/.PcbLib files to the Sideband
catalog. Diffs by item id (derived from filename, matching the publish endpoint):

  new      -> rendered + published   (POST <api>/api/library-publish-source, additive)
  removed  -> deleted                (DELETE <catalog>/api/libraries/<slug>/items/<id>)
  existing -> skipped                (never re-rendered)

Library metadata (title/description/author/about_md) is admin-owned and preserved
— publish-source only ensures org/repo. One .SchLib/.PcbLib == one part (split
merged libraries upstream before calling this).
"""
import os, re, sys, glob, json, time
import requests

API     = os.environ["SIDEBAND_API_URL"].rstrip("/")       # sideband-app (renders via monkey)
CATALOG = os.environ["SIDEBAND_CATALOG_URL"].rstrip("/")   # website catalog
TOKEN   = os.environ["SIDEBAND_PUBLISH_TOKEN"]
SLUG    = os.environ["SLUG"]
ORG     = os.environ.get("ORG", "")
REPO    = os.environ.get("REPO", SLUG)
SRC     = os.environ["SOURCE_DIR"]
MAX_PER_RUN = int(os.environ.get("MAX_PER_RUN", "0") or 0)   # 0 = no cap
GLB     = os.environ.get("GLB", "true").lower() != "false"
BATCH   = int(os.environ.get("BATCH", "40") or 40)
AUTH    = {"Authorization": f"Bearer {TOKEN}"}

def slugify(s: str) -> str:  # MUST match the publish endpoint's slugify
    return re.sub(r"-+$", "", re.sub(r"^-+", "", re.sub(r"[^a-z0-9]+", "-", s.lower())))[:80]

def item_id(path: str) -> str:
    stem = os.path.splitext(os.path.basename(path))[0]
    return ("fp-" if path.lower().endswith(".pcblib") else "sym-") + slugify(stem)

def list_source():
    return sorted(f for f in glob.glob(os.path.join(SRC, "**", "*"), recursive=True)
                  if f.lower().endswith((".schlib", ".pcblib")))

def existing_ids():
    ids, cursor = set(), ""
    while True:
        u = f"{CATALOG}/api/libraries/{SLUG}/items?limit=500" + (f"&cursor={cursor}" if cursor else "")
        r = requests.get(u, timeout=120)
        if r.status_code == 404:   # library not created/published yet
            return ids
        r.raise_for_status()
        j = r.json()
        ids.update(it["id"] for it in j.get("items", []))
        cursor = j.get("nextCursor")
        if not cursor:
            return ids

def publish(files):
    for i in range(0, len(files), BATCH):
        chunk = files[i:i + BATCH]
        meta = {os.path.basename(f): {"category": os.path.basename(os.path.dirname(f))} for f in chunk}
        spec = {"baseUrl": CATALOG, "token": TOKEN, "slug": SLUG, "org": ORG, "repo": REPO,
                "glb": GLB, "clear": False, "items": meta}
        mp = [("spec", (None, json.dumps(spec)))]
        for f in chunk:
            mp.append(("files", (os.path.basename(f), open(f, "rb").read(), "application/octet-stream")))
        for attempt in range(3):
            try:
                r = requests.post(f"{API}/api/library-publish-source", files=mp, timeout=2400)
                if r.ok:
                    j = r.json()
                    print(f"  + batch {i//BATCH+1}: +{j.get('symbols',0)+j.get('footprints',0)} "
                          f"(skipped {len(j.get('skipped',[]))})", flush=True)
                    break
                print(f"  ! batch {i//BATCH+1}: {r.status_code} {r.text[:200]}", flush=True)
            except Exception as e:
                print(f"  ! batch {i//BATCH+1} attempt {attempt+1}: {e}", flush=True)
            time.sleep(5)
        else:
            sys.exit(f"batch {i//BATCH+1} failed after 3 attempts")

def delete(ids):
    for iid in ids:
        r = requests.delete(f"{CATALOG}/api/libraries/{SLUG}/items/{iid}", headers=AUTH, timeout=60)
        print(("  - " if (r.ok or r.status_code == 404) else f"  ! del {r.status_code} ") + iid, flush=True)

def main():
    by_id = {item_id(f): f for f in list_source()}
    have = existing_ids()
    new = [i for i in by_id if i not in have]
    removed = [i for i in have if i not in by_id]
    print(f"[{SLUG}] source={len(by_id)} catalog={len(have)} new={len(new)} removed={len(removed)}", flush=True)
    if MAX_PER_RUN and len(new) > MAX_PER_RUN:
        print(f"  capped: publishing {MAX_PER_RUN}/{len(new)} new this run; rest next run", flush=True)
        new = new[:MAX_PER_RUN]
    if new:
        print("publishing new…", flush=True); publish([by_id[i] for i in new])
    if removed:
        print("deleting removed…", flush=True); delete(removed)
    print(f"[{SLUG}] done", flush=True)

if __name__ == "__main__":
    main()
