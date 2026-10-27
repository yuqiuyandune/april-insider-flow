#!/usr/bin/env python3
"""Create a Buttondown email from a weekly.py JSON. bd_post.py FILE.json [--status draft|about_to_send] ; key in $BUTTONDOWN_API_KEY"""
import json, os, sys, urllib.request
f = sys.argv[1]; status = sys.argv[sys.argv.index("--status") + 1] if "--status" in sys.argv else "draft"
w = json.load(open(f, encoding="utf-8"))
payload = {"subject": w["subject"], "body": w["body"], "status": status}
req = urllib.request.Request("https://api.buttondown.com/v1/emails", data=json.dumps(payload).encode(), method="POST",
                             headers={"Authorization": "Token " + os.environ["BUTTONDOWN_API_KEY"], "Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.loads(r.read()); print("created", j.get("status"), j.get("id"), j.get("subject"))
except urllib.error.HTTPError as e:
    print("HTTP", e.code, e.read().decode()[:500]); sys.exit(1)
