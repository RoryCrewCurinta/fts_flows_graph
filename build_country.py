"""Build the flow-map dataset for one country.
   python build_country.py TCD Chad 2025 2026 [--refresh]
Sources: OCHA FTS flows (api.hpc.tools), HPC projects (cash share), OCHA pooled fund API (sub-grants by type),
IATI via d-portal (named implementing partners). Writes data/<ISO3>.json and review/<ISO3>.csv.
Raw pulls are kept in cache/; pass --refresh to pull again."""
import json, re, os, sys, csv, time, argparse, collections as C, requests
from concurrent.futures import ThreadPoolExecutor
UA={"User-Agent":"Mozilla/5.0 flowmap"}
def get(url,params=None,tries=4):
    for i in range(tries):
        try:
            r=requests.get(url,params=params,headers=UA,timeout=180); return r.json()
        except Exception as e:
            if i==tries-1: raise
            time.sleep(3*(i+1))
ap=argparse.ArgumentParser(); ap.add_argument("iso3"); ap.add_argument("name"); ap.add_argument("years",nargs="+",type=int)
ap.add_argument("--refresh",action="store_true"); A=ap.parse_args()
os.chdir(os.path.dirname(os.path.abspath(__file__)))
for d in ("cache","data","review","overrides"): os.makedirs(d,exist_ok=True)
ISO3=A.iso3.upper(); HPC="https://api.hpc.tools"
OV=json.load(open(f"overrides/{ISO3}.json",encoding="utf-8")) if os.path.exists(f"overrides/{ISO3}.json") else {}

# ---------- FTS ----------
def fts(year):
    fn=f"cache/fts_{ISO3}_{year}.json"
    if os.path.exists(fn) and not A.refresh: return json.load(open(fn))
    out=[]; url=f"{HPC}/v1/public/fts/flow?countryISO3={ISO3}&year={year}&limit=1000"
    while url:
        j=get(url); out+=j["data"]["flows"]; url=j["meta"].get("nextLink")
    json.dump(out,open(fn,"w")); return out

# ---------- organisation labels ----------
SHORT={"World Food Programme":"WFP","United Nations High Commissioner for Refugees":"UNHCR","United Nations Children's Fund":"UNICEF","International Organization for Migration":"IOM",
"International Committee of the Red Cross":"ICRC","Agency for Technical Cooperation and Development":"ACTED","Danish Refugee Council":"DRC","International Rescue Committee":"IRC","Norwegian Refugee Council":"NRC",
"Office for the Coordination of Humanitarian Affairs":"OCHA","World Health Organization":"WHO","United Nations Population Fund":"UNFPA","Food and Agriculture Organization of the United Nations":"FAO",
"European Commission's Humanitarian Aid and Civil Protection Department":"ECHO","Médecins Sans Frontières":"MSF","Central Emergency Response Fund":"CERF","Action Contre la Faim - France":"ACF France",
"Action Contre la Faim - Action Against Hunger International":"ACF Intl","Première Urgence Internationale":"PUI","Handicap International - Humanity & Inclusion":"HI",
"International Federation of Red Cross and Red Crescent Societies":"IFRC","Private (individuals & organizations)":"Private donors","United States of America, Government of":"United States",
"INTERSOS Humanitarian Aid Organization":"INTERSOS","Catholic Relief Services":"CRS","World Vision International":"World Vision","International Medical Corps UK":"IMC","Hebrew Immigrant Aid Society":"HIAS",
"United Nations Development Programme":"UNDP","Alliance for International Medical Action":"ALIMA","European Commission":"EC","Solidarités International":"Solidarités","Lutherian World Fund":"LWF",
"United States Department of State":"US State Dept","Korea, Republic of, Government of":"South Korea","Saudi Arabia (Kingdom of), Government of":"Saudi Arabia","Education Cannot Wait Fund":"Education Cannot Wait",
"Triangle Génération Humanitaire":"Triangle GH","Swedish International Development Agency":"Sida","Swiss Development Cooperation":"SDC"}
COMMITTEE=re.compile(r"National Committee|for UNHCR|con ACNUR|com ACNUR|Fund for UNICEF|Association for UNHCR",re.I)
def short(n):
    if n in SHORT: return SHORT[n]
    if n==f"{A.name}, Government of": return f"{A.name} government"
    m=re.match(r"(.*), Government of$",n)
    if m: return m.group(1)
    return n if len(n)<=26 else n[:24].rstrip()+"…"
def cat(o):
    n=o["name"]; t=(o.get("organizationTypes") or [""])[0]; s=(o.get("organizationSubTypes") or [""])[0]; l=(o.get("organizationLevels") or [""])[0]
    if n in OV.get("recategorise",{}): return OV["recategorise"][n]
    if n==f"{A.name}, Government of": return "hostgov"
    if n in OV.get("national",[]): return "nngo"
    if t=="Pooled Funds": return "fund"
    if s=="UN Agencies": return "un"
    if t=="Red Cross/Red Crescent Organizations": return "rc"
    if t=="NGOs": return "nngo" if ("Local and National" in l and n not in OV.get("not_national",[])) else "ingo"
    if t=="Private Organizations" or COMMITTEE.search(n): return "private"
    if t=="Governments": return "gov"
    if t=="Multilateral Organizations": return "multi"
    return "private"

# ---------- cash estimate (CALP CVA tracking pipeline rules, in-kind excluded) ----------
CASH_CLUSTERS={"Basic Needs / Multi-Purpose Cash","Cash à usage multiple","Multi Purpose Cash","Multi-cluster/Multi-Purpose Cash","Multi-Purpose Cash & Social Protection","Multipurpose Cash Assistance (MPC)","Multi-Purpose Cash Assistance (MPCA)","Multipurpose cash/ IDPs/ multisector","Multi-sector Cash/Social Protection COVID-19","Cash","Multi-purpose Cash","Multipurpose cash assistance","Multi-Purpose Cash Assistance","Multipurpose Cash Assistance COVID-19","Multi-Purpose Cash Assistance COVID-19","Multi-purpose Cash COVID-19","Multipurpose cash","Protection: Multi-Purpose Cash Assistance","Cash Transfer COVID-19"}
QUANT=set(); ML=set()
if os.path.exists("reference/cva_project_questions.csv"):
    QUANT={r["Question"] for r in csv.DictReader(open("reference/cva_project_questions.csv",encoding="utf-8")) if r["Question type"] in("quantC","quantV")}
if os.path.exists("reference/classifier_accepted_flows.csv"):
    ML={r["flow_id"] for r in csv.DictReader(open("reference/classifier_accepted_flows.csv",encoding="utf-8")) if r["iso3"]==ISO3}
PC=json.load(open("cache/projects.json")) if os.path.exists("cache/projects.json") else {}
def project(pid):
    pid=str(pid)
    if pid not in PC:
        try:
            pv=get(f"{HPC}/v2/public/project/{pid}",tries=2)["data"]["projectVersion"]
            defs={str(d["id"]):d for d in pv["plans"][0].get("conditionFields",[])}
            qa=[(defs[str(f["conditionFieldId"])]["name"],f["value"]) for f in pv["projectVersionPlans"][0]["projectVersionFields"] if str(f["conditionFieldId"]) in defs and f.get("value") is not None]
            PC[pid]={"name":pv["name"],"objective":pv.get("objective") or "","qa":qa,"code":pv.get("code") or ""}
        except Exception as e: PC[pid]={"name":"","objective":"","qa":[],"code":""}
    return PC[pid]
def pct(x):
    x=str(x).strip().lower(); m=re.search(r"[0-9]+(?:\.[0-9]+)?",x)
    return 0.0 if "less than 1" in x else float(m.group()) if m else None
def cash_share(p):
    q=[pct(v) for k,v in p["qa"] if (k in QUANT or re.search(r"% .*(transfert monétaire|coupons|cash transfer|voucher)",k,re.I))]; q=[x for x in q if x is not None]
    return min(sum(q),100)/100 if q else None

# ---------- pooled fund sub-grants (type level) ----------
SUBNAME={"INGO":"International NGOs","NGO":"National NGOs","O":"Red Cross / Red Crescent","UN":"UN agencies","OG":"Government and others","PC":"Private contractors"}; VIA={"INGO":"INGOs","NGO":"national NGOs","UN":"UN","O":"Red Cross","OG":"others","PC":"contractors"}
SRCNAME={"INGO":"international NGO","NGO":"national NGO","UN":"UN","O":"Red Cross / Red Crescent","OG":"government and other","PC":"private contractor"}; SUBCAT={"INGO":"ingo","NGO":"nngo","O":"rc","UN":"un","OG":"hostgov","PC":"private"}; CAT2CBPF={"un":"UN","ingo":"INGO","nngo":"NGO","rc":"O","hostgov":"OG"}
def cbpf_subgrants():
    try:
        import pycountry; iso2=pycountry.countries.get(alpha_3=ISO3).alpha_2
        pf=[p for p in get("https://cbpfapi.unocha.org/vo2/odata/Poolfund?$format=json")["value"] if p["CountryCode"]==iso2]
        out=[]
        for p in pf: out+=[r for r in get(f"https://cbpfapi.unocha.org/vo2/odata/AllocationFlowByOrgType?PoolfundCodeAbbrv={p['PoolfundCodeAbbrv']}&$format=json")["value"] if r["fund"]==p["Id"]]
        return out
    except Exception as e: print("pooled fund lookup failed:",e); return []

# ---------- IATI named partners (d-portal) ----------
IATI_PUBS={"XM-DAC-41122":"United Nations Children's Fund","US-EIN-13-5660870":"International Rescue Committee","XM-DAC-41121":"United Nations High Commissioner for Refugees"}
RTYPE={"10":"hostgov","11":"hostgov","15":"hostgov","21":"ingo","22":"nngo","23":"nngo","24":"nngo","40":"un","70":"private","72":"private","90":"private"}
def iati():
    fn=f"cache/iati_{ISO3}.json"
    if os.path.exists(fn) and not A.refresh: return json.load(open(fn))
    import pycountry; iso2=pycountry.countries.get(alpha_3=ISO3).alpha_2; out=[]
    for pid in IATI_PUBS:
        sql=f"""select coalesce(x.xson->'/receiver-org/narrative'->0->>'',x.xson->>'/receiver-org@ref') recv, x.xson->>'/receiver-org@type' rtype,
          substr(x.xson->>'/transaction-date@iso-date',1,4) yr, count(*) n, sum((x.xson->>'/value')::float) val, min(x.xson->>'/value@currency') cur
          from xson x join country c on c.aid=x.aid and c.country_code='{iso2}' and c.country_percent>=50
          where x.root='/iati-activities/iati-activity/transaction' and x.xson->>'/transaction-type@code' in ('3','4') and x.pid='{pid}'
          and x.xson->>'/transaction-date@iso-date' >= '{min(A.years)}-01-01' group by 1,2,3"""
        try: rows=get("https://d-portal.org/dquery",params={"sql":sql},tries=2)["rows"]
        except Exception as e: print("IATI failed",pid,e); rows=[]
        for r in rows: r["pid"]=pid
        out+=rows
    json.dump(out,open(fn,"w")); return out

# ---------- build ----------
SUBS=cbpf_subgrants(); IATI=iati(); OUT={}; review={}
for yr in A.years:
    F=fts(yr); N={}; flows=[]; sectors=[]; projects=[]; meta=C.Counter(); six={}; pix={}
    pids={o["id"] for f in F for o in f["destinationObjects"] if o["type"]=="Project"}-set(PC)
    if pids:
        with ThreadPoolExecutor(8) as ex: list(ex.map(project,pids))
    def node(o):
        if o["id"] not in N: N[o["id"]]={"id":o["id"],"name":o["name"],"label":short(o["name"]),"cat":cat(o),"self":0,"_lvl":(o.get("organizationLevels") or [""])[0],"_sub":(o.get("organizationSubTypes") or [""])[0]}
        return o["id"]
    for f in F:
        a=f["amountUSD"] or 0
        if a<=0: continue
        g=lambda side,t:[o for o in f[side] if o["type"]==t]
        so,do=g("sourceObjects","Organization"),g("destinationObjects","Organization")
        ctp=f.get("method")=="Cash transfer programming (CTP)"
        if f["boundary"]=="incoming": meta["incoming"]+=a
        if ctp: meta["ctp"]+=a
        if not so or not do: continue
        s,d=node(so[0]),node(do[0])
        if s==d: N[s]["self"]+=a; continue
        gc=[o["name"] for o in g("destinationObjects","GlobalCluster")] or ["Not specified"]
        cl=[o["name"] for o in g("destinationObjects","Cluster")]; pr=g("destinationObjects","Project")
        x=0; basis=""
        cash_cl=[c for c in cl if c in CASH_CLUSTERS]
        if ctp or (cash_cl and len(cl)==1): x,basis=a,"tag"
        elif cash_cl: x,basis=a/len(cl),"tag"
        elif pr and f["boundary"]!="outgoing":
            sh=cash_share(project(pr[0]["id"]))
            if sh:
                if f.get("contributionType")=="in kind": meta["est_inkind"]+=a*sh
                else: x,basis=a*sh,"proj"
        elif str(f["id"]) in ML: x,basis=a,"ml"
        if x: meta["est"]+=x; meta["est_"+basis]+=x
        rec={"i":f["id"],"s":s,"t":d,"a":round(a),"d":(f.get("date") or f.get("decisionDate") or "")[:10],"st":f["status"][0],
             "k":[six.setdefault(n,len(six)) for n in gc],"ds":re.sub(r"\s+"," ",f.get("description") or "")[:170]}
        if ctp or basis=="tag": rec["c"]=1
        if x: rec["x"]=round(x); rec["xb"]=basis
        if f["flowType"]=="Pass through": rec["pt"]=1
        if pr:
            p=project(pr[0]["id"]); rec["p"]=pix.setdefault(pr[0]["id"],len(pix))
        flows.append(rec)
    sectors=[n for n,_ in sorted(six.items(),key=lambda kv:kv[1])]
    projects=[{"id":pid,"name":project(pid)["name"][:140],"code":next((o.get("code") or o.get("name") for f in F for o in f["destinationObjects"] if o["type"]=="Project" and o["id"]==pid),"")} for pid,_ in sorted(pix.items(),key=lambda kv:kv[1])]
    # pooled fund + sub-grant layer
    outsum=C.Counter(); 
    for r in flows: outsum[r["s"]]+=r["a"]
    funds=[n for n in N.values() if n["cat"]=="fund" and re.search(r"Country-based|Regional UN",n["_sub"]) and outsum[n["id"]]>0]
    dash=[]; fund=None
    if funds:
        fund=max(funds,key=lambda n:outsum[n["id"]])["id"]; partners=C.defaultdict(set); alloc=dn=0
        for r in flows:
            if r["s"]==fund:
                alloc+=r["a"]; c=N[r["t"]]["cat"]
                if c=="nngo": dn+=r["a"]
                if c in CAT2CBPF: partners[CAT2CBPF[c]].add(r["t"])
        sn=stot=0
        for r in SUBS:
            if r["year"]!=yr or r["targetType"]!="2": continue
            v=round(float(r["value"])); sid=f"sub-{r['source']}-{r['target']}"; stot+=v; sn+=v if (r["target"]=="NGO" and r["source"]!="NGO") else 0
            if sid in N: N[sid]["v"]+=v; continue
            N[sid]={"id":sid,"name":f"{SUBNAME[r['target']]} sub-granted by {SRCNAME[r['source']]} partners of the pooled fund","label":f"{SUBNAME[r['target']]}, via {VIA[r['source']]}","cat":SUBCAT[r["target"]],"sub":1,"v":v,"from":SRCNAME[r["source"]],"self":0}
            dash+=[{"s":p,"t":sid} for p in sorted(partners[r["source"]])]
        first=[r for r in SUBS if r["year"]==yr and r["targetType"]=="1"]
        if first: alloc=sum(float(r["value"]) for r in first); dn=sum(float(r["value"]) for r in first if r["target"]=="NGO")
        us=sum(r["a"] for r in flows if r["t"]==fund and N[r["s"]]["name"].startswith("United States")); fin=sum(r["a"] for r in flows if r["t"]==fund)
        meta=dict(meta); meta.update(fund=fund,alloc=round(alloc),direct_nngo=round(dn),sub_nat=sn,sub_tot=stot,fund_in=round(fin),fund_us=round(us))
    # IATI named partners
    byname={n["name"]:n["id"] for n in N.values()}; alias=OV.get("iati_alias",{}); iati_edges=[]
    for pid,pname in IATI_PUBS.items():
        if pname not in byname: continue
        src=byname[pname]; rows=[r for r in IATI if r["pid"]==pid and r["yr"]==str(yr) and r.get("recv") and r["cur"]=="USD" and r["val"] and float(r["val"])>0 and r["recv"]!=pname]
        agg=C.defaultdict(lambda:[0,0,None])
        for r in rows:
            k=r["recv"].strip(); kk=re.sub(r"\s+"," ",k.upper()); agg[kk][0]+=float(r["val"]); agg[kk][1]+=int(r["n"]); agg[kk][2]=agg[kk][2] or (k,r.get("rtype"))
        ranked=sorted(agg.items(),key=lambda kv:-kv[1][0]); top,rest=ranked[:14],ranked[14:]
        for kk,(v,n,(nm,rt)) in top:
            generic=nm in ("International NGO","Partner country based NGO","Governmental","Multilateral","IP not published","Oxfam Partner(s)")
            if kk in alias and alias[kk] in byname: nid=byname[alias[kk]]
            else:
                nid="iati-"+re.sub(r"[^a-z0-9]+","-",(short(pname)+" "+nm if generic else nm).lower())[:60]
                label=(nm.title() if nm.isupper() else nm); label={"Partner country based NGO":"National NGOs","International NGO":"International NGOs","Governmental":"Government bodies","IP not published":"Partners not published"}.get(label,label)
                if nid not in N: N[nid]={"id":nid,"name":label+(f" ({short(pname)} partners, by type)" if generic else ""),"label":label if len(label)<=26 else label[:24].rstrip()+"…","cat":RTYPE.get(str(rt),"private"),"iati":1,"self":0}
            iati_edges.append({"s":src,"t":nid,"a":round(v),"n":n})
        if rest:
            nid=f"iati-other-{src}"; N[nid]={"id":nid,"name":f"{len(rest)} other partners named by {short(pname)}","label":f"{len(rest)} other {short(pname)} partners","cat":"private","iati":1,"self":0}
            iati_edges.append({"s":src,"t":nid,"a":round(sum(v[0] for _,v in rest)),"n":sum(v[1] for _,v in rest)})
    for n in N.values():
        if n.get("_lvl","").startswith("Local and National") and n["cat"] in("nngo","hostgov"):
            review.setdefault(n["name"],{"cat":n["cat"],"fts_subtype":n["_sub"],"years":set(),"funders":set()})["years"].add(yr)
            review[n["name"]]["funders"]|={N[r["s"]]["label"] for r in flows if r["t"]==n["id"]}
        n.pop("_lvl",None); n.pop("_sub",None)
    OUT[str(yr)]={"nodes":list(N.values()),"flows":flows,"sectors":sectors,"projects":projects,"dash":dash,"iati":iati_edges,"meta":{k:(round(v) if isinstance(v,float) else v) for k,v in meta.items()}}
    print(yr,"nodes",len(N),"flows",len(flows),"sectors",len(sectors),"projects",len(projects),"iati edges",len(iati_edges),dict(OUT[str(yr)]["meta"]))
json.dump(PC,open("cache/projects.json","w"))
json.dump({"country":A.name,"iso3":ISO3,"years":OUT},open(f"data/{ISO3}.json","w",encoding="utf-8"),ensure_ascii=False,separators=(",",":"))
with open(f"review/{ISO3}.csv","w",newline="",encoding="utf-8") as fh:
    w=csv.writer(fh); w.writerow(["organisation","shown_as","fts_subtype","years","funded_by","confirm_national (y/n)"])
    for k,v in sorted(review.items()): w.writerow([k,v["cat"],v["fts_subtype"],";".join(map(str,sorted(v["years"]))),"; ".join(sorted(v["funders"]))[:200],""])
print("size",os.path.getsize(f"data/{ISO3}.json"),"review rows",len(review))
