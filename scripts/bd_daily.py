#!/usr/bin/env python3
"""Buttondown helper for the daily brief; key in $BUTTONDOWN_API_KEY. The brief goes ONLY to subscribers with the tag
"daily" (they ask for it on the site's subscribe forms, or tick it themselves in Buttondown's subscriber portal).

bd_daily.py daily.json --existing        print "STATUS ID SUBJECT" for emails already made for the same session
bd_daily.py daily.json --status draft     save a draft (filtered to the daily tag)
bd_daily.py daily.json --status send      create it as a draft filtered to the daily tag, check that Buttondown kept
                                          the filter, then send it. If the filter is not there it stops and leaves
                                          the draft, so the weekly subscribers never get a daily email by mistake.
"""
import json, os, sys, urllib.request

API = "https://api.buttondown.com/v1"
HDR = {"Authorization": "Token " + os.environ["BUTTONDOWN_API_KEY"], "Content-Type": "application/json"}
TAG = "daily"

def call(url, data=None, method="GET"):
    req = urllib.request.Request(url if url.startswith("http") else API + url, data=json.dumps(data).encode() if data is not None else None,
                                 method=method, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            b = r.read()
            return json.loads(b) if b else {}
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:500]); sys.exit(1)

def key(subject):
    # "April 早报 · 11月25日收盘：..." -> "April 早报 · 11月25日收盘"
    return subject.split(" | ")[0].split("：")[0]

def tag_id():
    url = "/tags?page_size=100"
    while url:
        j = call(url)
        for t in j.get("results", []):
            if t.get("name") == TAG: return t["id"]
        url = j.get("next")
    t = call("/tags", {"name": TAG, "color": "#2c49c9", "description": "Daily brief (April 早报)", "subscriber_editable": True,
                       "public_description": "每个交易日北京时间晚上 8 点左右的早报 / The daily brief, around 8pm Beijing time on trading days"}, "POST")
    print("created tag", t.get("id")); return t["id"]

def main():
    w = json.load(open(sys.argv[1], encoding="utf-8"))
    if "--existing" in sys.argv:
        k = key(w["subject"]); url, pages = "/emails", 0
        while url and pages < 5:
            j = call(url); pages += 1
            for e in j.get("results", []):
                if key(e.get("subject") or "") == k: print(e.get("status"), e.get("id"), e.get("subject"))
            url = j.get("next")
        return
    status = sys.argv[sys.argv.index("--status") + 1] if "--status" in sys.argv else "draft"
    tid = tag_id()
    flt = {"filters": [{"field": "subscriber.tags", "operator": "contains", "value": tid}], "groups": [], "predicate": "and"}
    e = call("/emails", {"subject": w["subject"], "body": w["body"], "status": "draft", "filters": flt}, "POST")
    got = json.dumps(e.get("filters") or {})
    print("draft", e.get("id"), e.get("subject"))
    if tid not in got:
        print("STOP: Buttondown did not keep the daily-tag filter on this email; left as a draft, nothing sent. filters =", got); sys.exit(2)
    if status == "send":
        s = call(f"/emails/{e['id']}", {"status": "about_to_send"}, "PATCH")
        print("sending", s.get("status"), s.get("id"))

if __name__ == "__main__":
    main()
