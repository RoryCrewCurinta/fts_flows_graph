"""Build every country in countries.txt, then the page.
   python build_all.py 2025 2026 [--refresh]"""
import sys, os, subprocess
here=os.path.dirname(os.path.abspath(__file__)); args=sys.argv[1:] or ["2025","2026"]
failed=[]
for line in open(os.path.join(here,"countries.txt"),encoding="utf-8"):
    line=line.strip()
    if not line or line.startswith("#"): continue
    iso,name=line.split("|",1); print("==",iso,name,flush=True)
    if subprocess.run([sys.executable,os.path.join(here,"build_country.py"),iso,name,*args]).returncode: failed.append(iso)
subprocess.run([sys.executable,os.path.join(here,"make_page.py")],check=True)
print("Failed:",failed if failed else "none")
