#!/usr/bin/env python3
"""Buttondown helper for the weekly digest; key in $BUTTONDOWN_API_KEY.

bd_post.py FILE.json [--status draft|about_to_send]   create the email from a weekly.py JSON
bd_post.py FILE.json --existing                       print "STATUS ID SUBJECT" for every email already in
                                                      Buttondown for the same week (nothing if none)
"""
import json, os, sys, urllib.request

API = "https://api.buttondown.com/v1/emails"
HDR = {"Authorization": "Token " + os.environ["BUTTONDOWN_API_KEY"], "Content-Type": "application/json"}
f = sys.argv[1]
w = json.load(open(f, encoding="utf-8"))


def call(url, data=None, method="GET"):
    req = urllib.request.Request(url, data=data, method=method, headers=HDR)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print("HTTP", e.code, e.read().decode()[:500]); sys.exit(1)


if "--existing" in sys.argv:
    # the subject starts with the week's date range, e.g. "本周内部人动向（10月24日 – 10月30日）"
    key = w["subject"].split("：")[0]
    url, pages = API, 0
    while url and pages < 10:
        j = call(url); pages += 1
        for e in j.get("results", []):
            if (e.get("subject") or "").startswith(key):
                print(e.get("status"), e.get("id"), e.get("subject"))
        url = j.get("next")
    sys.exit(0)

status = sys.argv[sys.argv.index("--status") + 1] if "--status" in sys.argv else "draft"
payload = {"subject": w["subject"], "body": w["body"], "status": status}
j = call(API, json.dumps(payload).encode(), "POST")
print("created", j.get("status"), j.get("id"), j.get("subject"))
