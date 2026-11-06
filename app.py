# app.py - 1/3 - 4 صفحات فقط - PROMAX V2
from flask import Flask, request, jsonify, Response, redirect, make_response
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
import requests, random, string, json

app = Flask(__name__)

# ===== عدل هنا بس - يقرا من Render =====
import os
from supabase import create_client, Client

VPS_TOKEN = os.getenv("VPS_TOKEN", "vps_libya_2026_8rT9yU2iO5p")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
ADMIN_KEY = os.getenv("ADMIN_KEY", "123456")
ROOT_WALLET = os.getenv("ROOT_WALLET", "0x2d447f9d656594f6c65de039aebe7da32a968400")
VPS_HOST = os.getenv("VPS_HOST", "YOUR_VPS_IP")
DOMAIN = os.getenv("DOMAIN", "").strip() or VPS_HOST  # لو فاضي في Render، يستعمل IP
PORT = int(os.getenv("PORT", 5000))

ALLOWED_KEYS = [ADMIN_KEY, "123456", "admin123"]

# حماية - لو Supabase مش محطوط في Render، ما يطيحش السيرفر
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL.startswith("http") else None
except Exception as e:
    print("Supabase init failed:", e)
    supabase = None
# ======================

AGENT_URL = f"http://{VPS_HOST}:5001/api/agent"
ALLOWED_KEYS = [ADMIN_KEY, "123456", "admin123"]
USDT = "0x55d398326f99059fF775485246999027B3196775"
RPC = "https://bsc-dataseed.binance.org/"
TOPIC = "[STRIPPED 66 bytes]"
FILES = ["File.npvt", "File.ssc", "File.nm", "File.hc", "File.ehi", "File.npvs", "File.v2box"]
MADAR_PRICE = 10

try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL.startswith("http") else None
except Exception as e:
    print("Supabase init:", e)
    supabase = None

@app.errorhandler(Exception)
def _handle_all_errors(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        if request.path.startswith('/admin') or request.path.startswith('/api') or request.path.startswith('/check'):
            return jsonify({'error': str(e)}), e.code
        return e
    print('SERVER ERROR:', e)
    if request.path.startswith('/admin') or request.path.startswith('/api') or request.path.startswith('/check'):
        return jsonify({'error': str(e)}), 500
    raise e

# ===== VPS CONTROL =====
def agent_create_bundle(user_id, plan):
    try:
        r = requests.post(f"{AGENT_URL}/create_bundle", headers={"X-Agent-Token": VPS_TOKEN}, json={"user_id": user_id, "plan": plan}, timeout=20)
        if r.status_code == 200: return True, r.json()
        return False, r.text
    except Exception as e: return False, str(e)

def agent_delete_bundle(user_id):
    try:
        r = requests.post(f"{AGENT_URL}/delete_bundle", headers={"X-Agent-Token": VPS_TOKEN}, json={"user_id": user_id}, timeout=15)
        return r.status_code == 200
    except: return False

def agent_get_blob(user_id):
    try:
        r = requests.post(f"{AGENT_URL}/get_blob", headers={"X-Agent-Token": VPS_TOKEN}, json={"user_id": user_id}, timeout=15)
        if r.status_code == 200: return r.json().get('blob')
        return None
    except: return None

def agent_status(user_id):
    try:
        r = requests.post(f"{AGENT_URL}/status", headers={"X-Agent-Token": VPS_TOKEN}, json={"user_id": user_id}, timeout=10)
        if r.status_code == 200: return r.json()
        return None
    except: return None

def agent_health():
    try:
        r = requests.get(f"http://{VPS_HOST}:5001/health", timeout=8)
        if r.status_code == 200: return r.json()
        return None
    except: return None

def decode_blob(blob):
    try:
        raw = bytes.fromhex(blob).decode() if isinstance(blob, str) else blob
        return json.loads(raw)
    except: return None

def get_protocols(user_id):
    blob = agent_get_blob(user_id)
    if not blob:
        plan = "paid" if get_active_subscription(user_id) else "free"
        ok, _ = agent_create_bundle(user_id, plan)
        if ok: blob = agent_get_blob(user_id)
    if not blob: return None
    return decode_blob(blob)

# ===== Supabase + تصليح خطأ التاريخ =====
def parse_expire(s):
    if not s: return None
    try:
        # إصلاح خطأ offset-naive vs offset-aware - نحذف +00:00 و Z
        t = str(s).strip()
        if "+" in t: t = t.split("+")[0]
        if "Z" in t: t = t.replace("Z", "")
        t = t.replace("T", " ").split(".")[0][:19]
        return datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
    except: return None

def get_user(user_id):
    if not supabase: return None
    try:
        res = supabase.table("users").select("*").eq("user_id", user_id).execute()
        return res.data[0] if res.data else None
    except: return None

def save_user(user):
    if not supabase: return
    try: supabase.table("users").upsert(user).execute()
    except Exception as e: print("save error", e)

def get_remaining_hours(user):
    if not user or not user.get("expires_at"): return 0
    if user.get("status")=="inactive": return 0
    exp = parse_expire(user["expires_at"])
    if not exp: return 0
    return max(0, (exp - datetime.now()).total_seconds()/3600)

def format_hm(h):
    if h <=0: return "0:00:00"
    total=int(h*3600); hh=total//3600; m=(total%3600)//60; s=total%60
    if hh>=24: d=hh//24; rh=hh%24; return f"{d} يوم {rh}:{m:02d}:{s:02d}"
    return f"{hh}:{m:02d}:{s:02d}"

def get_active_subscription(user_id):
    if not supabase: return None
    try:
        res = supabase.table("subscriptions").select("*").eq("user_id", user_id).eq("is_paid", True).execute()
        if not res.data: return None
        best=None
        for s in res.data:
            exp=parse_expire(s.get("expire_at"))
            if exp and exp>datetime.now():
                if not best or exp>parse_expire(best.get("expire_at")): best=s
        return best
    except: return None

def is_paid_user(uid): return get_active_subscription(uid) is not None

def restore_paid_user(uid):
    sub=get_active_subscription(uid)
    if not sub: return None
    exp=parse_expire(sub.get("expire_at"))
    if not exp: return None
    u={"user_id":uid,"expires_at":exp.strftime("%Y-%m-%d %H:%M:%S"),"status":"active"}
    save_user(u); return u

def get_paid_users_list():
    if not supabase: return []
    try: subs=supabase.table("subscriptions").select("*").eq("is_paid",True).order("expire_at",desc=True).limit(200).execute().data or []
    except: return []
    out=[]; seen=set()
    for s in subs:
        uid=s.get("user_id")
        if not uid or uid in seen: continue
        exp=parse_expire(s.get("expire_at"))
        if not exp: continue
        seen.add(uid)
        tx=s.get("tx_hash") or ""
        is_madar=str(tx).startswith("madar_") or str(tx).startswith("manual_")
        method="مدار" if is_madar else "USDT"
        card_code=""
        if is_madar:
            try:
                used=supabase.table("madar_cards_used").select("*").eq("user_id",uid).execute().data
                if used: card_code=used[-1].get("card_code") or ""
            except: pass
        rem=max(0,(exp-datetime.now()).total_seconds()/3600)
        out.append({"user_id":uid,"method":method,"tx_hash":tx,"card_code":card_code,"amount_paid":s.get("amount_paid") or 0,"expire_at":s.get("expire_at") or "","remaining":rem,"remaining_formatted":format_hm(rem),"is_active":rem>0,"created_at":s.get("created_at") or ""})
    return out

def madar_activate(uid):
    exp=datetime.now()+timedelta(days=30)
    user=get_user(uid) or {"user_id":uid}
    user["expires_at"]=exp.strftime("%Y-%m-%d %H:%M:%S"); user["status"]="active"
    save_user(user)
    try: supabase.table("subscriptions").upsert({"user_id":uid,"expire_at":exp.isoformat(),"is_paid":True,"tx_hash":f"madar_{uid}_{int(datetime.now().timestamp())}","amount_paid":MADAR_PRICE}).execute()
    except: pass
    agent_create_bundle(uid, "paid")
    return True

def amount_for(uid):
    h=abs(hash(str(uid)))%900+100
    return round(1+h/10000,4)

def check_payment(uid):
    amt=amount_for(uid); target=int(amt*10**18)
    try:
        latest=int(requests.post(RPC,json={"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1},timeout=10).json()["result"],16)
        padded="0x000000000000000000000000"+ROOT_WALLET[2:].lower()
        logs=requests.post(RPC,json={"jsonrpc":"2.0","method":"eth_getLogs","params":[{"fromBlock":hex(latest-15000),"toBlock":"latest","address":USDT,"topics":[TOPIC,None,padded]}],"id":1},timeout=15).json().get("result",[])
        used=set()
        try: used={x["tx_hash"] for x in supabase.table("subscriptions").select("tx_hash").execute().data if x.get("tx_hash")}
        except: pass
        for log in logs:
            if int(log["data"],16)>=target and log["transactionHash"] not in used:
                return True, log["transactionHash"], amt
        return False,"no",amt
    except Exception as e: return False,str(e),amt
    # app.py - 2/3 - الصفحات الأربع
# ===== 1. الصفحة الرئيسية =====

# app.py - 3/3 - نهاية الملف
@app.route('/')
def home(): return Response(HOME_HTML, mimetype='text/html')

@app.route('/health')
def health():
    st = agent_status("test_health") if VPS_HOST != "YOUR_VPS_IP" else None
    return jsonify({"ok": True, "vps_host": VPS_HOST, "agent_reachable": st is not None or agent_health() is not None, "agent_health": agent_health(), "supabase": bool(supabase)})

@app.route('/go')
def go():
    ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()
    fp = request.args.get('fp','').strip() or request.cookies.get('device_fp','').strip()
    if fp and fp.startswith('fp_') and supabase:
        try:
            res = supabase.table("device_limits").select("*").eq("fingerprint", fp).execute()
            if res.data:
                row=res.data[0]
                created=parse_expire(row.get("created_at",""))
                if created and (datetime.now()-created).total_seconds()/3600 < 24:
                    return redirect(f"/view/{row['user_id']}")
        except: pass
    uid='user_'+''.join(random.choices(string.digits,k=6))
    exp=datetime.now()+timedelta(hours=2)
    user={"user_id":uid,"expires_at":exp.strftime("%Y-%m-%d %H:%M:%S"),"status":"active","ip_address":ip}
    save_user(user)
    if fp and fp.startswith('fp_') and supabase:
        try: supabase.table("device_limits").upsert({"fingerprint":fp,"user_id":uid,"ip_address":ip,"created_at":datetime.now().isoformat()},on_conflict="fingerprint").execute()
        except: pass
    ok,res=agent_create_bundle(uid,"free")
    if not ok: print(f"VPS FAIL free {uid}: {res}")
    resp=redirect(f"/view/{uid}")
    if fp: resp.set_cookie('device_fp',fp,max_age=86400*30,samesite='Lax')
    resp.set_cookie('last_user_id',uid,max_age=86400,samesite='Lax')
    return resp

@app.route('/clear')
def clear():
    resp=make_response("<script>localStorage.clear(); alert('تم المسح'); window.location='/';</script>")
    resp.set_cookie('device_fp','',expires=0); resp.set_cookie('last_user_id','',expires=0)
    return resp

@app.route('/view/<user_id>')
def view_user(user_id):
    u=get_user(user_id)
    if not u:
        restored=restore_paid_user(user_id)
        if restored: u=restored
        else:
            exp=datetime.now()+timedelta(hours=2)
            u={"user_id":user_id,"expires_at":exp.strftime("%Y-%m-%d %H:%M:%S"),"status":"active"}
            save_user(u)
    else:
        sub=get_active_subscription(user_id)
        if sub:
            exp=parse_expire(sub.get("expire_at"))
            if exp and exp>datetime.now() and parse_expire(u.get("expires_at"))!=exp:
                u["expires_at"]=exp.strftime("%Y-%m-%d %H:%M:%S"); u["status"]="active"; save_user(u)
    return Response(LIBRARY_HTML.replace("__UID__", user_id),mimetype='text/html')

@app.route('/pay/<user_id>')
def pay_page(user_id): return Response(PAY_HTML.replace("__WALLET__",ROOT_WALLET).replace("__UID__",user_id),mimetype='text/html')
@app.route('/content/<user_id>')
def content_page(user_id): return Response(LIBRARY_HTML.replace("__UID__",user_id),mimetype='text/html')
@app.route('/pay-madar/<user_id>')
def pay_madar_page(user_id): return Response(PAY_HTML.replace("__WALLET__",ROOT_WALLET).replace("__UID__",user_id),mimetype='text/html')
@app.route('/amount/<user_id>')
def amount_api(user_id): return jsonify({"amount":amount_for(user_id),"wallet":ROOT_WALLET})

@app.route('/api/support/send', methods=['POST'])
def support_send():
    data=request.get_json(silent=True) or {}
    try: supabase.table("support_messages").insert({"user_id":data.get("user_id","guest"),"message":data.get("message"),"sender":data.get("sender","user")}).execute()
    except Exception as e: return jsonify({"ok":False,"error":str(e)}),500
    return jsonify({"ok":True})

@app.route('/api/support/get')
def support_get():
    uid=request.args.get("user_id","guest")
    try:
        res=supabase.table("support_messages").select("*").eq("user_id",uid).order("created_at").limit(50).execute()
        return jsonify(res.data or [])
    except: return jsonify([])

@app.route('/verify/<user_id>')
def verify_api(user_id):
    ok,tx,amt=check_payment(user_id)
    if ok:
        exp=datetime.now()+timedelta(days=30)
        user=get_user(user_id) or {"user_id":user_id}
        user["expires_at"]=exp.strftime("%Y-%m-%d %H:%M:%S"); user["status"]="active"; save_user(user)
        try: supabase.table("subscriptions").upsert({"user_id":user_id,"expire_at":exp.isoformat(),"is_paid":True,"tx_hash":tx,"amount_paid":amt}).execute()
        except: pass
        agent_create_bundle(user_id,"paid")
        return jsonify({"paid":True})
    return jsonify({"paid":False,"amount":amt})

@app.route('/check', methods=['GET'])
def check():
    user_id=request.args.get('user_id')
    if not user_id: return jsonify({"error":"user_id missing"}),400
    now=datetime.now(); user=get_user(user_id)
    base_url=request.host_url
    links=[f"{base_url}download/{f}?user_id={user_id}" for f in FILES]
    vps = agent_status(user_id)
    vps_txt = "VPS ✅" if vps and vps.get("exists") else "VPS ❌"
    if not user:
        restored=restore_paid_user(user_id)
        if restored: return jsonify({"status":"active","links":links,"files":FILES,"hours":format_hm(get_remaining_hours(restored)),"vps_status":vps_txt})
        expires=now+timedelta(hours=2)
        user={"user_id":user_id,"expires_at":expires.strftime("%Y-%m-%d %H:%M:%S"),"status":"active"}
        save_user(user); agent_create_bundle(user_id,"free")
        return jsonify({"status":"active","links":links,"files":FILES,"hours":"2:00:00","vps_status":vps_txt})
    sub=get_active_subscription(user_id)
    if sub:
        exp=parse_expire(sub.get("expire_at"))
        if exp and exp>now:
            user["expires_at"]=exp.strftime("%Y-%m-%d %H:%M:%S"); user["status"]="active"; save_user(user)
            return jsonify({"status":"active","links":links,"files":FILES,"hours":format_hm(get_remaining_hours(user)),"vps_status":vps_txt})
    if user.get("status")=="inactive": return jsonify({"status":"disabled","message":"تم تعطيل حسابك","hours":"معطل","files":FILES,"vps_status":vps_txt})
    remaining=get_remaining_hours(user)
    if remaining<=0:
        last=parse_expire(user["expires_at"]) or now
        since=(now-last).total_seconds()/3600
        if since>=24:
            new=now+timedelta(hours=2)
            user["expires_at"]=new.strftime("%Y-%m-%d %H:%M:%S"); user["status"]="active"; save_user(user); agent_create_bundle(user_id,"free")
            return jsonify({"status":"active","links":links,"files":FILES,"hours":"2:00:00","vps_status":vps_txt})
        else: return jsonify({"status":"cooldown","message":f"انتهى - انتظر {format_hm(24-since)}","hours":format_hm(24-since),"files":FILES,"vps_status":vps_txt})
    return jsonify({"status":"active","links":links,"files":FILES,"hours":format_hm(remaining),"vps_status":vps_txt})

@app.route('/download/<filename>')
def download(filename):
    user_id=request.args.get('user_id')
    if not user_id: return "user_id missing",400
    user=get_user(user_id)
    if not user:
        restored=restore_paid_user(user_id)
        if restored: user=restored
        else: return redirect(f"/pay/{user_id}")
    if user.get("status")=="inactive": return Response("معطل",403)
    if get_remaining_hours(user)<=0: return redirect(f"/pay/{user_id}")
    if filename not in FILES: return "not allowed",403
    cfg = get_protocols(user_id)
    if not cfg: return "VPS لم يجهز الملف - تأكد أن agent.py يخدم على بورت 5001",500
    lines=[]
    lines.append(f"# PREMIUM GATE - {user_id} - {filename}")
    lines.append(f"# Expire: {cfg.get('expire_at','')}")
    lines.append(f"# Host: {cfg.get('host','')}")
    lines.append("")
    if cfg.get("ssh"):
        s=cfg["ssh"]; lines.append(f"[SSH]\n{s.get('username')}:{s.get('password')}@{s.get('host')}:{s.get('port')}\n")
    if cfg.get("tls"):
        t=cfg["tls"]; lines.append(f"[TLS]\n{t.get('host')}:{t.get('port')} SNI={t.get('sni')}\n")
    if cfg.get("vless"): lines.append(f"[VLESS]\n{cfg['vless'].get('link','')}\n")
    if cfg.get("trojan"): lines.append(f"[TROJAN]\n{cfg['trojan'].get('link','')}\n")
    if cfg.get("vmess"): lines.append(f"[VMESS]\n{cfg['vmess'].get('link','')}\n")
    lines.append("\n# Full JSON:\n" + json.dumps(cfg, ensure_ascii=False, indent=2))
    txt="\n".join(lines)
    base=filename.rsplit(".",1)[0]; ext=filename.rsplit(".",1)[1] if "." in filename else "txt"
    out=f"{base}.{user_id[:12]}.{ext}"
    return Response(txt, mimetype='text/plain', headers={"Content-Disposition": f"attachment;filename={out}"})

@app.route('/api/protocols/<user_id>')
def api_protocols(user_id):
    cfg = get_protocols(user_id)
    if not cfg: return jsonify({"ok": False, "error": "VPS no blob"}), 500
    return jsonify({"ok": True, "user_id": user_id, "config": cfg, "all_links": cfg.get("all_links", {})})

@app.route('/api/agent/connect', methods=['POST'])
def api_agent_connect():
    data=request.get_json(silent=True) or {}
    blob=data.get("blob")
    if not blob: return jsonify({"error":"blob required"}),400
    try:
        r=requests.post(f"{AGENT_URL}/connect", headers={"X-Agent-Token": VPS_TOKEN}, json={"blob": blob}, timeout=10)
        return jsonify(r.json()), r.status_code
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/create_free', methods=['POST'])
def api_create_free():
    uid=(request.get_json(silent=True) or {}).get("user_id")
    if not uid: return jsonify({"error":"user_id required"}),400
    ok,res=agent_create_bundle(uid,"free")
    return jsonify({"ok":ok,"data":res}),200 if ok else 500

@app.route('/api/create_paid', methods=['POST'])
def api_create_paid():
    uid=(request.get_json(silent=True) or {}).get("user_id")
    if not uid: return jsonify({"error":"user_id required"}),400
    ok,res=agent_create_bundle(uid,"paid")
    return jsonify({"ok":ok,"data":res}),200 if ok else 500

@app.route('/api/madar/charge-card', methods=['POST'])
def madar_charge_card():
    data=request.get_json(silent=True) or {}
    user_id=data.get("user_id")
    card_code=str(data.get("card_code","")).strip().replace(" ","").replace("-","")
    if not card_code or len(card_code)<10: return jsonify({"status":"fail"})
    try:
        used=supabase.table("madar_cards_used").select("*").eq("card_code",card_code).execute()
        if used.data: return jsonify({"status":"used"})
        pending=supabase.table("madar_pending").select("*").eq("card_code",card_code).eq("status","pending").execute()
        if pending.data: return jsonify({"status":"used"})
    except: pass
    try: supabase.table("madar_pending").insert({"user_id":user_id,"card_code":card_code,"status":"pending"}).execute()
    except Exception as e: return jsonify({"status":"fail","error":str(e)})
    return jsonify({"status":"pending"})

@app.route("/admin")
def admin():
    if request.args.get("key") not in ALLOWED_KEYS: return Response(f"<h1>401</h1><p>/admin?key={ADMIN_KEY}</p>",401)
    return Response(ADMIN_HTML, mimetype='text/html')

@app.route("/admin/users")
def a_users():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"key غلط"}),401
    if not supabase: return jsonify([])
    try: users=supabase.table("users").select("*").order("expires_at",desc=True).limit(200).execute().data or []
    except Exception as e: return jsonify({"error":str(e)}),500
    try: paid_ids={x["user_id"] for x in get_paid_users_list() if x.get("is_active")}
    except: paid_ids=set()
    out=[]
    for u in users:
        if u.get("user_id") in paid_ids: continue
        rs=u.get("status","active"); rem=get_remaining_hours(u)
        out.append({"user_id":u.get("user_id"),"expire_at":u.get("expires_at") or "","remaining":rem,"remaining_formatted":format_hm(rem) if rs!="inactive" else "معطل","raw_status":rs,"is_active":rs!="inactive" and rem>0,"is_paid":False,"ip_address":u.get("ip_address","")})
    return jsonify(out)

@app.route("/admin/paid")
def admin_paid():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"no"}),401
    return jsonify(get_paid_users_list())

@app.route("/admin/usdt")
def admin_usdt():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"no"}),401
    return jsonify([x for x in get_paid_users_list() if x.get("method")=="USDT"])

@app.route("/admin/vps/users")
def admin_vps_users():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"no"}),401
    users=[]
    if supabase:
        try: users=supabase.table("users").select("*").order("expires_at",desc=True).limit(200).execute().data or []
        except: users=[]
    out=[]
    for u in users:
        uid=u.get("user_id")
        out.append({"user_id":uid,"expire_at":u.get("expires_at") or "","remaining":get_remaining_hours(u),"remaining_formatted":format_hm(get_remaining_hours(u)),"vps":agent_status(uid) or {"exists": False},"is_paid":is_paid_user(uid)})
    return jsonify(out)

@app.route("/admin/vps/create", methods=['POST'])
def admin_vps_create():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"message":"key غلط"}),401
    data=request.get_json(silent=True) or {}; uid=data.get("user_id"); plan=data.get("plan","free")
    if not uid: return jsonify({"message":"user_id ناقص"}),400
    ok,res=agent_create_bundle(uid, plan)
    if ok:
        hours = 2 if plan=="free" else 720
        exp=datetime.now()+timedelta(hours=hours)
        user=get_user(uid) or {"user_id":uid}
        user["expires_at"]=exp.strftime("%Y-%m-%d %H:%M:%S"); user["status"]="active"; save_user(user)
        return jsonify({"message":f"تم خلق {uid} في VPS - {plan}"})
    return jsonify({"message":f"فشل VPS: {res}"}),500

@app.route("/admin/vps/delete", methods=['POST'])
def admin_vps_delete():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"message":"key غلط"}),401
    uid=(request.get_json(silent=True) or {}).get("user_id")
    ok=agent_delete_bundle(uid)
    return jsonify({"message":f"تم حذف {uid} من VPS" if ok else "VPS ما لقاش اليوزر"})

@app.route("/admin/paid-extend", methods=['POST'])
def admin_paid_extend():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"message":"key غلط"}),401
    data=request.get_json(silent=True) or {}; uid=data.get("user_id")
    if not uid: return jsonify({"message":"user_id ناقص"}),400
    try:
        subs=supabase.table("subscriptions").select("*").eq("user_id",uid).eq("is_paid",True).execute().data or []
        if not subs: return jsonify({"message":"ماعنداش اشتراك"}),404
        best=max(subs,key=lambda s: parse_expire(s.get("expire_at") or "2000-01-01") or datetime(2000,1,1))
        old=parse_expire(best.get("expire_at")) or datetime.now()
        new=max(old,datetime.now())+timedelta(days=30)
        if best.get("id"): supabase.table("subscriptions").update({"expire_at":new.isoformat()}).eq("id",best.get("id")).execute()
        else: supabase.table("subscriptions").update({"expire_at":new.isoformat()}).eq("user_id",uid).eq("tx_hash",best.get("tx_hash")).execute()
        user=get_user(uid)
        if user: user["expires_at"]=new.strftime("%Y-%m-%d %H:%M:%S"); user["status"]="active"; save_user(user)
        agent_create_bundle(uid,"paid")
        return jsonify({"message":f"تم تمديد {uid} 30 يوم + تجديد VPS"})
    except Exception as e: return jsonify({"message":f"خطأ: {e}"}),500

@app.route("/admin/paid-delete", methods=['POST'])
def admin_paid_delete():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"no"}),401
    uid=(request.get_json(silent=True) or {}).get("user_id")
    try:
        supabase.table("subscriptions").delete().eq("user_id",uid).execute()
        supabase.table("users").delete().eq("user_id",uid).execute()
        try: supabase.table("madar_cards_used").delete().eq("user_id",uid).execute()
        except: pass
        try: supabase.table("madar_pending").delete().eq("user_id",uid).execute()
        except: pass
        agent_delete_bundle(uid)
        return jsonify({"message":f"تم حذف {uid}"})
    except Exception as e: return jsonify({"message":str(e)}),500

@app.route("/admin/action", methods=['POST'])
def admin_action():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"message":"key غلط"}),401
    data=request.get_json(silent=True) or {}; uid=data.get("user_id"); act=data.get("action"); days=data.get("days",0); hours=data.get("hours",0)
    try:
        if is_paid_user(uid) and act in ["delete","disable","enable","add_days"]:
            return jsonify({"message":"هذا مدفوع - عدله من تب المدفوعين"}),400
        user=get_user(uid)
        if not user and act!="delete": return jsonify({"message":"اليوزر غير موجود"}),404
        if act=="delete":
            supabase.table("users").delete().eq("user_id",uid).execute(); agent_delete_bundle(uid)
            return jsonify({"message":f"تم حذف {uid}"})
        elif act=="disable":
            supabase.table("users").update({"status":"inactive"}).eq("user_id",uid).execute(); agent_delete_bundle(uid)
            return jsonify({"message":f"تم تعطيل {uid} + حذف من VPS"})
        elif act=="enable":
            supabase.table("users").update({"status":"active"}).eq("user_id",uid).execute(); agent_create_bundle(uid,"free")
            return jsonify({"message":f"تم تفعيل {uid} + خلق في VPS"})
        elif act=="extend_custom" or act=="add_days":
            cur=parse_expire(user.get("expires_at")) if user else datetime.now()
            if not cur or cur<datetime.now(): cur=datetime.now()
            new=cur+timedelta(days=int(days),hours=int(hours))
            supabase.table("users").update({"expires_at":new.strftime("%Y-%m-%d %H:%M:%S"),"status":"active"}).eq("user_id",uid).execute()
            return jsonify({"message":"تم التحديث"})
    except Exception as e: return jsonify({"message":f"خطأ: {e}"}),500
    return jsonify({"message":"unknown"})

@app.route("/admin/support")
def admin_support():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"no"}),401
    try:
        res=supabase.table("support_messages").select("*").order("created_at",desc=True).limit(200).execute()
        return jsonify(res.data or [])
    except: return jsonify([])

@app.route("/admin/devices")
def admin_devices():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"no"}),401
    try:
        res=supabase.table("device_limits").select("*").execute()
        return jsonify(res.data or [])
    except: return jsonify([])

@app.route("/admin/devices/delete", methods=['POST'])
def admin_devices_delete():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"no"}),401
    data=request.get_json(silent=True) or {}
    try: supabase.table("device_limits").delete().eq("fingerprint",data.get("fingerprint")).execute()
    except: pass
    return jsonify({"message":"تم"})

@app.route("/admin/devices/clear", methods=['POST'])
def admin_devices_clear():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"no"}),401
    try: supabase.table("device_limits").delete().neq("fingerprint","___none___").execute()
    except: pass
    return jsonify({"message":"تم المسح"})

@app.route("/admin/madar-pending")
def admin_madar_pending():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"no"}),401
    try:
        res=supabase.table("madar_pending").select("*").order("created_at",desc=True).limit(200).execute()
        return jsonify(res.data or [])
    except: return jsonify([])

@app.route("/admin/madar-approve", methods=['POST'])
def admin_madar_approve():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"no"}),401
    data=request.get_json(silent=True) or {}; pid=data.get("id"); uid=data.get("user_id"); card=data.get("card_code","")
    try:
        supabase.table("madar_pending").update({"status":"approved"}).eq("id",pid).execute()
        try: supabase.table("madar_cards_used").insert({"user_id":uid,"card_code":card}).execute()
        except: pass
        madar_activate(uid)
        return jsonify({"message":f"تم تفعيل {uid} - 30 يوم + VPS paid"})
    except Exception as e: return jsonify({"message":f"خطأ: {e}"}),500

@app.route("/admin/madar-reject", methods=['POST'])
def admin_madar_reject():
    if request.args.get("key") not in ALLOWED_KEYS: return jsonify({"error":"no"}),401
    pid=(request.get_json(silent=True) or {}).get("id")
    try:
        supabase.table("madar_pending").update({"status":"rejected"}).eq("id",pid).execute()
        return jsonify({"ok":True})
    except Exception as e: return jsonify({"error":str(e)}),500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=PORT)
