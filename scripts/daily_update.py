#!/usr/bin/env python3
"""Daily pipeline step: fetch new Form 4 days, verify each against SEC, keep only passing days.

  python3 scripts/daily_update.py --ua "Name email" [--dates D ...] [--lookback 10] [--force]

- Target dates: every weekday in the last --lookback calendar days (America/Los_Angeles)
  that is not yet in data/days/ (or exactly --dates when given; --force refetches those).
- Runs scripts/form4_sector.py into work/new/, then scripts/verify.py on each new file.
  A day is added to data/days/ only if verify prints "0 problem(s)" for it.
- Writes work/added.txt (dates added), work/problems.md (withheld days, missing dates)
  and a summary to $GITHUB_STEP_SUMMARY when set. Exit code is always 0 unless the
  scripts themselves crash; the workflow decides what to do from the files.
"""
import argparse, datetime as dt, glob, os, re, shutil, subprocess, sys
from zoneinfo import ZoneInfo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAYS = os.path.join(ROOT, "data", "days")
WORK = os.path.join(ROOT, "work")
NEW = os.path.join(WORK, "new")
PY = [sys.executable, "-I"]


def run(args, timeout):
    p = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    out = (p.stdout or "") + (p.stderr or "")
    print(out, flush=True)
    return p.returncode, out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ua", required=True)
    ap.add_argument("--dates", nargs="*")
    ap.add_argument("--lookback", type=int, default=10)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--sample", type=int, default=30)
    a = ap.parse_args()

    shutil.rmtree(WORK, ignore_errors=True)
    os.makedirs(NEW)
    have = {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(DAYS, "*.json"))}
    today = dt.datetime.now(ZoneInfo("America/Los_Angeles")).date()
    if a.dates:
        targets = [d for d in a.dates if a.force or d not in have]
    else:
        targets = []
        for i in range(a.lookback, -1, -1):
            d = today - dt.timedelta(days=i)
            if d.weekday() < 5 and d.isoformat() not in have:
                targets.append(d.isoformat())

    added, problems, log = [], [], []
    if not targets:
        log.append("No new dates to fetch.")
    else:
        print("Target dates:", " ".join(targets), flush=True)
        rc, out = run(PY + ["scripts/form4_sector.py", "--ua", a.ua, "--out", NEW, "--force", "--dates"] + targets,
                      timeout=150 * len(targets) + 300)
        no_index = set(re.findall(r"^(\d{4}-\d\d-\d\d) no index", out, re.M))
        for d in targets:
            f = os.path.join(NEW, f"{d}.json")
            if not os.path.exists(f):
                age = (today - dt.date.fromisoformat(d)).days
                why = "no EDGAR index yet (holiday or not published)" if d in no_index else "fetch failed"
                log.append(f"{d}: not fetched, {why}.")
                # a recent date is normal (index not out yet); an older weekday still missing is worth a look
                if age >= 3 and d not in no_index:
                    problems.append(f"- {d}: {why}")
                continue
            rc, vout = run(PY + ["scripts/verify.py", "--ua", a.ua, "--sample", str(a.sample), f],
                           timeout=600)
            line = next((l for l in vout.splitlines() if l.startswith(f"{d}.json:")), "")
            if rc == 0 and line.endswith(" 0 problem(s)"):
                shutil.copy(f, os.path.join(DAYS, f"{d}.json"))
                added.append(d)
                log.append(f"{d}: PASS: {line.split(': ', 1)[1]}")
            else:
                bad = [l.strip() for l in vout.splitlines() if l.strip().startswith("!")][:15]
                problems.append(f"- {d}: withheld, failed SEC verification. {line.split(': ', 1)[-1] if line else 'verify crashed (exit %d)' % rc}"
                                + "".join(f"\n    - `{b}`" for b in bad))
                log.append(f"{d}: FAIL (withheld)")

    open(os.path.join(WORK, "added.txt"), "w").write("\n".join(added) + ("\n" if added else ""))
    if problems:
        open(os.path.join(WORK, "problems.md"), "w").write("\n".join(problems) + "\n")
    summary = "### Fetch and verify\n\n" + "\n".join(f"- {l}" for l in log) + "\n"
    if problems:
        summary += "\n### Problems\n\n" + "\n".join(problems) + "\n"
    print(summary)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        open(os.environ["GITHUB_STEP_SUMMARY"], "a").write(summary)


if __name__ == "__main__":
    main()
