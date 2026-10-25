from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os, requests
from datetime import datetime, timedelta
from supabase import create_client

app = Flask(__name__)
CORS(app)

# --- الاعدادات ---
ROOT_WALLET = os.getenv("ROOT_WALLET", "0x5430161DA6be4EF2B1Cfd2452F076eB67Db3BAc0")
USDT = "0x55d398326f99059fF775485246999027B3196775"
RPC = "https://bsc-dataseed.binance.org/"
TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
ADMIN_KEY = os.getenv("ADMIN_KEY", "admin123")
supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def amount_for(uid):
    h = abs(hash(str(uid))) % 900 + 100
    return round(15 + h/10000, 4)

def is_sub(uid):
    try:
        r = supabase.table("subscriptions").select("*").eq("user_id", uid).execute()
        if not r.data: return False, None
        d = r.data[0]
        exp = datetime.fromisoformat(d["expire_at"].replace("Z",""))
        if exp.tzinfo: exp = exp.replace(tzinfo=None)
        if not d.get("is_paid", True): return False, d
        return exp > datetime.utcnow(), d
    except: return False, None

def check_payment(uid):
    amt = amount_for(uid)
    target = int(amt * 10**18)
    try:
        latest = int(requests.post(RPC, json={"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}, timeout=10).json()["result"],16)
        padded = "0x000000000000000000000000" + ROOT_WALLET[2:].lower()
        logs = requests.post(RPC, json={"jsonrpc":"2.0","method":"eth_getLogs","params":[{"fromBlock":hex(latest-15000),"toBlock":"latest","address":USDT,"topics":[TOPIC,None,padded]}],"id":1}, timeout=15).json().get("result",[])
        used = {x["tx_hash"] for x in supabase.table("subscriptions").select("tx_hash").execute().data if x.get("tx_hash")}
        for log in logs:
            if int(log["data"],16)==target and log["transactionHash"] not in used:
                return True, log["transactionHash"], amt
        return False, "no", amt
    except Exception as e: return False, str(e), amt

PAY_HTML = """<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>الدفع الآمن</title><script src="https://cdn.tailwindcss.com"></script><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet"><style>@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');*{font-family:'Tajawal',sans-serif}</style></head><body class="bg-[#0a0a12] min-h-screen flex items-center justify-center p-4"><div class="w-full max-w-md"><div class="bg-gradient-to-b from-[#1e1e35] to-[#151528] rounded-[24px] p-6 border border-white/10 shadow-2xl"><div class="text-center mb-6"><div class="w-16 h-16 bg-gradient-to-br from-green-400 to-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-3"><i class="fa-solid fa-shield-halved text-2xl text-white"></i></div><h1 class="text-xl font-bold text-white">الدفع الآمن</h1><p class="text-gray-400 text-sm mt-1">BSC BEP20 • تأكيد تلقائي</p></div><div class="bg-black/40 rounded-2xl p-4 border border-white/5 mb-4"><div class="flex justify-between text-sm text-gray-400 mb-2"><span>المبلغ المطلوب</span><span class="text-yellow-400">مميز لك</span></div><div id="amt" class="text-3xl font-bold text-emerald-400 text-center">-- USDT</div></div><div class="bg-black/40 rounded-2xl p-4 border border-white/5 mb-4"><p class="text-xs text-gray-400 mb-2">عنوان المحفظة</p><div class="bg-[#0a0a12] p-3 rounded-xl font-mono text-[11px] break-all border border-white/10 text-left text-white">__WALLET__</div><div class="grid grid-cols-2 gap-2 mt-3"><button onclick="copyW()" class="bg-white text-black py-3 rounded-xl font-bold text-sm">نسخ العنوان</button><button onclick="copyA()" class="bg-white/10 text-white border border-white/10 py-3 rounded-xl font-bold text-sm">نسخ المبلغ</button></div></div><button onclick="verify()" id="btn" class="w-full bg-gradient-to-r from-emerald-500 to-green-500 text-black py-4 rounded-xl font-bold">لقد دفعت، فعل حسابي</button><div id="status" class="mt-4 text-center text-sm min-h-[24px] text-white"></div></div></div><script>let AMT=0,UID="__UID__";async function init(){let r=await fetch(`/amount/${UID}`).then(x=>x.json());AMT=r.amount;document.getElementById('amt').innerText=AMT+' USDT';}function copyW(){navigator.clipboard.writeText("__WALLET__");toast("تم نسخ العنوان");}function copyA(){navigator.clipboard.writeText(AMT+"");toast("تم نسخ المبلغ "+AMT);}function toast(t){let s=document.getElementById('status');s.innerHTML=`<span class='text-emerald-400'>${t}</span>`;setTimeout(()=>s.innerHTML="",2000)}async function verify(){let b=document.getElementById('btn'),s=document.getElementById('status');b.innerHTML="⏳ جاري التحقق...";b.disabled=true;try{let r=await fetch(`/verify/${UID}`).then(x=>x.json());if(r.paid){s.innerHTML="<span class='text-emerald-400 text-base font-bold'>✅ تم التفعيل - 30 يوم</span>";b.innerHTML="✅ تم بنجاح";}else{s.innerHTML=`<span class='text-red-400'>❌ لم نجد ${r.amount} - انتظر دقيقة</span>`;b.innerHTML="لقد دفعت، فعل حسابي";b.disabled=false;}}catch(e){s.innerText="خطأ اتصال";b.disabled=false;}}init();</script></body></html>"""

ADMIN_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin Pro</title><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-[#080810] text-white min-h-screen p-4 md:p-6"><div class="max-w-7xl mx-auto">
<div class="flex flex-wrap justify-between items-center gap-4 mb-6"><h1 class="text-2xl font-bold">لوحة التحكم <span class="text-emerald-400">Pro MAX</span></h1><button onclick="load()" class="bg-emerald-500 text-black px-4 py-2 rounded-xl text-sm font-bold">تحديث</button></div>
<div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
<div class="bg-gradient-to-br from-emerald-900/40 to-[#1a1a2e] p-5 rounded-2xl border border-emerald-800/30"><p class="text-gray-400 text-xs">النشطين</p><p id="active" class="text-3xl font-bold mt-1">--</p></div>
<div class="bg-[#1a1a2e] p-5 rounded-2xl border border-white/5"><p class="text-gray-400 text-xs">الكل</p><p id="total" class="text-3xl font-bold mt-1">--</p></div>
<div class="bg-[#1a1a2e] p-5 rounded-2xl border border-white/5"><p class="text-gray-400 text-xs">منتهي</p><p id="exp" class="text-3xl font-bold mt-1 text-red-400">--</p></div>
<div class="bg-gradient-to-br from-yellow-900/30 to-[#1a1a2e] p-5 rounded-2xl border border-yellow-800/30"><p class="text-gray-400 text-xs">الارباح</p><p id="rev" class="text-xl font-bold mt-1 text-yellow-400">--</p></div>
</div>
<div class="bg-[#12121f] rounded-2xl border border-white/5 p-4 mb-6 flex flex-wrap gap-3 items-end">
<div><label class="text-xs text-gray-400 block mb-1">User ID</label><input id="newUid" placeholder="مثلا user123" class="bg-black/50 border border-white/10 rounded-xl px-3 py-2 text-sm w-40"></div>
<div><label class="text-xs text-gray-400 block mb-1">المدة (يوم)</label><input id="newDays" type="number" value="30" class="bg-black/50 border border-white/10 rounded-xl px-3 py-2 text-sm w-20"></div>
<button onclick="addUser()" class="bg-emerald-500 text-black px-5 py-2.5 rounded-xl text-sm font-bold h-fit">+ اضافة اشتراك</button>
<span id="msg" class="text-sm font-bold h-fit pb-2"></span>
</div>
<div class="bg-[#12121f] rounded-2xl border border-white/5 overflow-hidden"><div class="p-4 border-b border-white/5 flex justify-between"><h3 class="font-bold">الاشتراكات</h3><input id="search" oninput="filter()" placeholder="بحث بـ user_id..." class="bg-black/50 border border-white/10 rounded-lg px-3 py-1 text-xs w-48"></div><div class="overflow-x-auto"><table class="w-full text-sm"><thead class="text-gray-500 bg-black/30"><tr><th class="p-3 text-right">User</th><th class="p-3">المبلغ</th><th class="p-3">الانتهاء</th><th class="p-3">الحالة</th><th class="p-3">تحكم كامل</th></tr></thead><tbody id="tb"></tbody></table></div></div>
</div>
<script>
const KEY=new URLSearchParams(location.search).get("key");let ALL=[];
async function load(){let s=await fetch(`/admin/stats?key=${KEY}`).then(r=>r.json());document.getElementById('active').innerText=s.active_users;document.getElementById('total').innerText=s.total_users;document.getElementById('exp').innerText=s.expired;document.getElementById('rev').innerText=s.total_revenue+" USDT";let u=await fetch(`/admin/users?key=${KEY}`).then(r=>r.json());ALL=u;render(u);}
function render(list){let h="";list.forEach(x=>{let d=new Date(x.expire_at),isTime=d>new Date(),isActive=isTime && x.is_paid!==false;let status = !x.is_paid ? '<span class="bg-orange-900/50 text-orange-300 px-2 py-1 rounded-full text-xs">⏸️ معطل</span>' : isTime ? '<span class="bg-emerald-900/50 text-emerald-300 px-2 py-1 rounded-full text-xs">✅ نشط</span>' : '<span class="bg-red-900/50 text-red-300 px-2 py-1 rounded-full text-xs">❌ منتهي</span>';h+=`<tr class='border-b border-white/5 hover:bg-white/5'><td class='p-3 font-mono text-xs'>${x.user_id}</td><td class='p-3 text-emerald-400'>${x.amount_paid||0}</td><td class='p-3 text-xs'>${d.toLocaleDateString('ar-LY')} ${d.toLocaleTimeString('ar-LY')}</td><td class='p-3'>${status}</td><td class='p-2 flex gap-1 flex-wrap'><button onclick="toggle('${x.user_id}', ${x.is_paid})" class="${x.is_paid ? 'bg-orange-500/20 text-orange-300 border border-orange-500/30' : 'bg-emerald-500 text-black'} px-3 py-1.5 rounded-lg text-xs font-bold">${x.is_paid ? '⏸️ تعطيل' : '✅ تفعيل'}</button><button onclick="ext('${x.user_id}')" class="bg-white/10 px-3 py-1.5 rounded-lg text-xs">+30 يوم</button><button onclick="del('${x.user_id}')" class="bg-red-900/50 text-red-300 px-3 py-1.5 rounded-lg text-xs">حذف</button></td></tr>`});document.getElementById('tb').innerHTML=h||'<tr><td colspan=5 class="p-6 text-center text-gray-500">لا يوجد بيانات</td></tr>'}
function filter(){let q=document.getElementById('search').value;render(ALL.filter(x=>x.user_id.toLowerCase().includes(q.toLowerCase())))}
async function del(uid){if(!confirm("هل تريد حذف "+uid+" نهائيا؟"))return;await fetch(`/admin/delete?key=${KEY}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:uid})});load();}
async function ext(uid){let m=document.getElementById('msg');m.innerText="⏳ جاري تمديد...";await fetch(`/admin/extend?key=${KEY}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:uid,days:30})});m.innerText="✅ تم تمديد 30 يوم";setTimeout(()=>m.innerText="",3000);load();}
async function toggle(uid,current){let m=document.getElementById('msg');m.innerText="⏳ جاري...";await fetch(`/admin/toggle?key=${KEY}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:uid,is_paid:current})});m.innerText=current ? "⏸️ تم تعطيل الحساب بنجاح" : "✅ تم تفعيل الحساب بنجاح";setTimeout(()=>m.innerText="",3000);load();}
async function addUser(){let u=document.getElementById('newUid').value.trim(),days=document.getElementById('newDays').value,m=document.getElementById('msg');if(!u){m.innerText="❌ اكتب User ID";return;}m.innerText="⏳ جاري الإضافة...";let r=await fetch(`/admin/add?key=${KEY}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:u,days:parseInt(days)||30})}).then(x=>x.json());if(r.ok){m.innerHTML="<span class='text-emerald-400'>✅ تمت الإضافة بنجاح - الحساب نشط الآن</span>";document.getElementById('newUid').value="";}else{m.innerText="❌ فشل الإضافة";}setTimeout(()=>m.innerText="",4000);load();}
load();
</script></body></html>"""

@app.route("/pay/<user_id>")
def pay_page(user_id):
    html = PAY_HTML.replace("__WALLET__", ROOT_WALLET).replace("__UID__", user_id)
    return Response(html, mimetype='text/html')

@app.route("/amount/<user_id>")
def amount_api(user_id): return jsonify({"amount": amount_for(user_id), "wallet": ROOT_WALLET})

@app.route("/verify/<user_id>")
def verify_api(user_id):
    ok, tx, amt = check_payment(user_id)
    if ok:
        exp = datetime.utcnow() + timedelta(days=30)
        ok2, data = is_sub(user_id)
        if ok2:
            old = datetime.fromisoformat(data["expire_at"].replace("Z",""))
            if old.tzinfo: old = old.replace(tzinfo=None)
            if old > datetime.utcnow(): exp = old + timedelta(days=30)
        supabase.table("subscriptions").upsert({"user_id": user_id, "expire_at": exp.isoformat(), "is_paid": True, "tx_hash": tx, "amount_paid": amt}).execute()
        return jsonify({"paid": True, "amount": amt, "expire_at": exp.isoformat()})
    return jsonify({"paid": False, "amount": amt})

@app.route("/getfile/<file_id>")
def getfile(file_id):
    uid = request.args.get("user_id")
    if not uid: return jsonify({"error":"need user_id"}),400
    ok,_ = is_sub(uid)
    if not ok: return jsonify({"error":"not_subscribed","pay_url":f"/pay/{uid}","amount":amount_for(uid)}),403
    try:
        import base64, requests as rq
        r = rq.get(f"https://drive.google.com/uc?export=download&id={file_id}", timeout=30)
        return jsonify({"file": base64.b64encode(r.content).decode()})
    except Exception as e: return jsonify({"error":str(e)}),500

@app.route("/admin/stats")
def a_stats():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    subs = supabase.table("subscriptions").select("*").execute().data
    active = sum(1 for s in subs if datetime.fromisoformat(s["expire_at"].replace("Z","")).replace(tzinfo=None) > datetime.utcnow() and s.get("is_paid",True))
    rev = sum(float(s.get("amount_paid",0) or 0) for s in subs if s.get("amount_paid"))
    return jsonify({"total_users":len(subs),"active_users":active,"expired":len(subs)-active,"total_revenue":round(rev,4)})

@app.route("/admin/users")
def a_users():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    return jsonify(supabase.table("subscriptions").select("*").order("expire_at",desc=True).limit(200).execute().data)

@app.route("/admin/delete", methods=["POST"])
def a_del():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    uid = request.json.get("user_id")
    supabase.table("subscriptions").delete().eq("user_id", uid).execute()
    return jsonify({"ok":True})

@app.route("/admin/extend", methods=["POST"])
def a_ext():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    uid = request.json.get("user_id")
    days = int(request.json.get("days",30))
    r = supabase.table("subscriptions").select("*").eq("user_id", uid).execute()
    if not r.data: return jsonify({"error":"not found"}),404
    old = datetime.fromisoformat(r.data[0]["expire_at"].replace("Z",""))
    if old.tzinfo: old = old.replace(tzinfo=None)
    if old < datetime.utcnow(): old = datetime.utcnow()
    new_exp = old + timedelta(days=days)
    supabase.table("subscriptions").update({"expire_at": new_exp.isoformat(), "is_paid": True}).eq("user_id", uid).execute()
    return jsonify({"ok":True})

@app.route("/admin/add", methods=["POST"])
def a_add():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    uid = request.json.get("user_id")
    days = int(request.json.get("days",30))
    exp = datetime.utcnow() + timedelta(days=days)
    supabase.table("subscriptions").upsert({"user_id":uid,"expire_at":exp.isoformat(),"is_paid":True,"tx_hash":"MANUAL","amount_paid":0}).execute()
    return jsonify({"ok":True})

@app.route("/admin/toggle", methods=["POST"])
def a_toggle():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    uid = request.json.get("user_id")
    current = request.json.get("is_paid")
    new_status = not bool(current)
    supabase.table("subscriptions").update({"is_paid": new_status}).eq("user_id", uid).execute()
    return jsonify({"ok":True, "new_status": new_status})

@app.route("/admin")
def admin():
    if request.args.get("key")!=ADMIN_KEY: return Response("401 ?key=",401)
    return Response(ADMIN_HTML, mimetype='text/html')

@app.route("/")
def home(): return "API ONLINE - Pro MAX Control"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT",10000)))
