"""
inspect_service.py — reveal an ArcGIS service's layers, or a layer's fields.

Run this on a machine WITH internet to discover what a county GIS service calls
its fields, so you can fill in that county's "map" in config.py.

Usage:
    python3 inspect_service.py <url>

If <url> is a FeatureServer/MapServer ROOT, it lists the layers (with ids).
If <url> is a specific LAYER (…/MapServer/2 or …/FeatureServer/0, with or
without /query), it prints that layer's field names + one sample record.

Then in config.py, for that county, set:
    "url":   the layer URL with /query on the end
    "map":   canonical key -> the county's real field name (from this output)
    "where": a residential filter once you can see the land-use field
"""

import sys
import json
import requests


def _get(url, **params):
    params.setdefault("f", "json")
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    url = sys.argv[1].rstrip("/")
    if url.endswith("/query"):
        url = url[: -len("/query")]

    meta = _get(url)

    # A service root lists its layers (and has no "fields").
    layers = meta.get("layers")
    if layers and "fields" not in meta:
        print(f"Service: {meta.get('serviceDescription') or url}\n")
        print("Layers (id  name):")
        for lyr in layers:
            print(f"  {lyr.get('id'):>3}  {lyr.get('name')}")
        print("\nNext: re-run with one layer URL, e.g.")
        print(f"  python3 inspect_service.py {url}/{layers[0].get('id')}")
        return

    # A layer has "fields".
    fields = meta.get("fields")
    if fields:
        print(f"Layer: {meta.get('name')}   geometryType={meta.get('geometryType')}\n")
        print("Fields (name : type : alias):")
        for f in fields:
            print(f"  {f.get('name'):<28} {f.get('type',''):<22} {f.get('alias','')}")
        try:
            q = _get(url + "/query", where="1=1", outFields="*",
                     resultRecordCount=1, returnGeometry="false")
            feats = q.get("features") or []
            if feats:
                print("\nSample record:")
                print(json.dumps(feats[0].get("attributes", {}), indent=2)[:2500])
        except Exception as e:
            print(f"\n(could not pull a sample record: {e})")
        return

    print("Could not find layers or fields. Raw response (head):")
    print(json.dumps(meta, indent=2)[:1200])


if __name__ == "__main__":
    main()
