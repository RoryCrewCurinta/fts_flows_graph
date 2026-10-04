"""Combine every data/<ISO3>.json into one page.
   python make_page.py [FIRST_ISO3]   -> docs/index.html"""
import sys, os, json, glob, datetime
os.chdir(os.path.dirname(os.path.abspath(__file__))); os.makedirs("docs",exist_ok=True)
data={}
for fn in sorted(glob.glob("data/*.json")):
    d=json.load(open(fn,encoding="utf-8")); data[d["iso3"]]={"country":d["country"],"years":d["years"]}
first=sys.argv[1].upper() if len(sys.argv)>1 else ("TCD" if "TCD" in data else sorted(data)[0])
today=datetime.date.today(); pulled=f"{today.day} {today.strftime('%B %Y')}"
t=open("template.html",encoding="utf-8").read().replace("__FIRST__",first).replace("__PULLED__",pulled).replace("__DATA__",json.dumps(data,ensure_ascii=False,separators=(",",":")))
open("docs/index.html","w",encoding="utf-8").write(t); print("docs/index.html",f"{len(t)/1e6:.1f} MB",list(data))
