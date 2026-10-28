from flask import Flask, request, jsonify, Response, redirect
from datetime import datetime, timedelta
from supabase import create_client, Client
import os, requests

app = Flask(__name__)
SUPABASE_URL = os.environ.get('SUPABASE_URL')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
ADMIN_KEY = os.environ.get('ADMIN_KEY', "admin123")
ROOT_WALLET = os.getenv("ROOT_WALLET", "0x5430161DA6be4EF2B1Cfd2452F076eB67Db3BAc0")
USDT = "0x55d398326f99059fF775485246999027B3196775"
RPC = "https://bsc-dataseed.binance.org/"
TOPIC = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
DRIVE_NPVT_ID = os.environ.get('DRIVE_NPVT_ID', '1T8zHaaiCEf-Zkgxpz-ig5Q8_5hScsq1I')
FOLDER = 'files'
FILES = ["File.npvt", "File.ssc", "File.nm", "File.hc", "File.ehi", "File.npvs", "File.v2box"]

def amount_for(uid):
    h = abs(hash(str(uid))) % 900 + 100
    return round(1 + h/10000, 4)

def check_payment(uid):
    amt = amount_for(uid)
    target = int(amt * 10**18)
    try:
        latest = int(requests.post(RPC, json={"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}, timeout=10).json()["result"],16)
        padded = "0x000000000000000000000000" + ROOT_WALLET[2:].lower()
        logs = requests.post(RPC, json={"jsonrpc":"2.0","method":"eth_getLogs","params":[{"fromBlock":hex(latest-15000),"toBlock":"latest","address":USDT,"topics":[TOPIC,None,padded]}],"id":1}, timeout=15).json().get("result",[])
        used = set()
        try: used = {x["tx_hash"] for x in supabase.table("subscriptions").select("tx_hash").execute().data if x.get("tx_hash")}
        except: pass
        for log in logs:
            paid = int(log["data"],16)
            if paid >= target and log["transactionHash"] not in used:
                return True, log["transactionHash"], amt
        return False, "no", amt
    except Exception as e: return False, str(e), amt

def get_user(user_id):
    res = supabase.table("users").select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None
def save_user(user): supabase.table("users").upsert(user).execute()
def get_remaining_hours(user):
    if not user or not user.get("expires_at"): return 0
    if user.get("status")=="inactive": return 0
    try:
        expires = datetime.strptime(user["expires_at"], "%Y-%m-%d %H:%M:%S")
        return max(0, (expires - datetime.now()).total_seconds()/3600)
    except: return 0
def format_hm(hours_float):
    total_minutes=int(round(hours_float*60)); h=total_minutes//60; m=total_minutes%60
    if h>=24: d=h//24; rh=h%24; return f"{d} day {rh}:{m:02d}" if d==1 else f"{d} days {rh}:{m:02d}"
    return f"{h}:{m:02d}"

PAY_HTML = """<!DOCTYPE html><html dir="rtl" lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>الدفع الآمن</title><script src="https://cdn.tailwindcss.com"></script><link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet"><style>@import url('https://fonts.googleapis.com/css2?family=Tajawal:wght@400;700&display=swap');*{font-family:'Tajawal',sans-serif}#toast-copy{position:fixed;top:20px;left:50%;transform:translateX(-50%);z-index:9999;transition:all 0.3s}</style></head><body class="bg-[#0a0a12] min-h-screen flex items-center justify-center p-4">
<div id="toast-copy" class="hidden"><div id="toastCopyBox" class="bg-white text-black px-6 py-3 rounded-full font-bold shadow-2xl text-sm">✅ تم النسخ</div></div>
<div class="w-full max-w-md"><div class="bg-gradient-to-b from-[#1e1e35] to-[#151528] rounded-[24px] p-6 border border-white/10 shadow-2xl"><div class="text-center mb-6"><div class="w-16 h-16 bg-gradient-to-br from-green-400 to-emerald-600 rounded-2xl flex items-center justify-center mx-auto mb-3"><i class="fa-solid fa-shield-halved text-2xl text-white"></i></div><h1 class="text-xl font-bold text-white">الدفع الآمن</h1><p class="text-gray-400 text-sm mt-1">BSC BEP20 • تأكيد تلقائي</p></div><div class="bg-black/40 rounded-2xl p-4 border border-white/5 mb-4"><div class="flex justify-between text-sm text-gray-400 mb-2"><span>المبلغ المطلوب</span><span class="text-yellow-400">الحد الأدنى</span></div><div id="amt" class="text-3xl font-bold text-emerald-400 text-center">-- USDT</div><p class="text-[11px] text-gray-500 text-center mt-1">تقدر تدفع أكثر براحتك</p></div><div class="bg-black/40 rounded-2xl p-4 border border-white/5 mb-4"><p class="text-xs text-gray-400 mb-2">عنوان المحفظة</p><div class="bg-[#0a0a12] p-3 rounded-xl font-mono text-[11px] break-all border border-white/10 text-left text-white">__WALLET__</div><div class="grid grid-cols-2 gap-2 mt-3"><button onclick="copyText('__WALLET__','العنوان')" class="bg-white text-black py-3 rounded-xl font-bold text-sm">نسخ العنوان</button><button onclick="copyText(AMT+'','المبلغ')" class="bg-white/10 text-white border border-white/10 py-3 rounded-xl font-bold text-sm">نسخ المبلغ</button></div></div><button onclick="verify()" id="btn" class="w-full bg-gradient-to-r from-emerald-500 to-green-500 text-black py-4 rounded-xl font-bold">لقد دفعت، فعل حسابي</button><div id="status" class="mt-4 text-center text-sm min-h-[24px] text-white"></div><div class="text-center mt-3"><a id="toContent" class="text-xs text-gray-400 underline">عرض المحتوى</a></div></div></div>
<script>
let AMT=0,UID="__UID__";
function showCopyToast(msg){let t=document.getElementById('toast-copy'),b=document.getElementById('toastCopyBox');b.innerText=msg;t.classList.remove('hidden');setTimeout(()=>t.classList.add('hidden'),2000);}
function copyText(text,label){if(navigator.clipboard && window.isSecureContext){navigator.clipboard.writeText(text).then(()=>{showCopyToast('✅ تم نسخ '+label+' للحافظة');}).catch(()=>{fallbackCopy(text,label);});}else{fallbackCopy(text,label);}}
function fallbackCopy(text,label){let ta=document.createElement('textarea');ta.value=text;ta.style.position='fixed';ta.style.top='-1000px';document.body.appendChild(ta);ta.focus();ta.select();try{document.execCommand('copy');showCopyToast('✅ تم نسخ '+label+' للحافظة');}catch(e){showCopyToast('❌ فشل النسخ');}document.body.removeChild(ta);}
async function init(){let r=await fetch(`/amount/${UID}`).then(x=>x.json());AMT=r.amount;document.getElementById('amt').innerText=AMT+' USDT';document.getElementById('toContent').href=`/content/${UID}`;}
async function verify(){let b=document.getElementById('btn'),s=document.getElementById('status');b.innerHTML="⏳ جاري التحقق...";b.disabled=true;try{let r=await fetch(`/verify/${UID}`).then(x=>x.json());if(r.paid){s.innerHTML="<span class='text-emerald-400 font-bold'>✅ تم التفعيل - 30 يوم</span>";setTimeout(()=>location.href=`/content/${UID}`,1500);}else{s.innerHTML=`<span class='text-red-400'>❌ لم نجد ${r.amount} أو أكثر</span>`;b.disabled=false;b.innerHTML="لقد دفعت، فعل حسابي";}}catch(e){s.innerText="خطأ";b.disabled=false;}}
init();
</script></body></html>"""

CONTENT_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مكتبتي</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#080810] min-h-screen p-4"><div class="max-w-3xl mx-auto"><div class="flex justify-between items-center mb-6"><h1 class="text-xl font-bold text-white">📁 مكتبتك - __UID__</h1><span id="time" class="bg-[#1e1e35] px-3 py-1 rounded-full text-xs text-white"></span></div><div id="list" class="space-y-3"></div></div>
<script>
const UID="__UID__";
async function load(){
  let c=await fetch(`/check?user_id=${UID}`).then(r=>r.json());
  document.getElementById('time').innerText=c.hours||'';
  if(c.status==='disabled'){
    document.getElementById('list').innerHTML=`<div class='bg-gradient-to-b from-[#1e1e35] to-[#151528] p-6 rounded-[24px] text-center border border-red-500/20'><p class='text-red-400 font-bold text-lg'>🚫 ${c.message||'تم تعطيل حسابك'}</p></div>`;
    return;
  }
  if(c.status!=='active'){
    let filesHtml="";(c.files||[]).forEach(f=>{filesHtml+=`<div class='bg-[#12121f] border border-white/5 rounded-2xl p-4 flex justify-between items-center opacity-30'><div><p class='font-bold text-white'>${f}</p></div><button disabled class='bg-gray-700 text-gray-400 px-4 py-2 rounded-xl text-sm'>مقفل 🔒</button></div>`;});
    document.getElementById('list').innerHTML=`<div class='bg-gradient-to-b from-[#1e1e35] to-[#151528] p-6 rounded-[24px] text-center border border-white/10 mb-4'><p class='text-white'>${c.message||'انتهى وقتك'}</p><a href='/pay/${UID}' class='mt-6 inline-block w-full bg-emerald-500 text-black py-3 rounded-xl font-bold'>💳 ادفع للتجديد 30 يوم</a></div>`+filesHtml;
    return;
  }
  let h="";c.files.forEach(f=>{h+=`<div class='bg-[#12121f] border border-white/5 rounded-2xl p-4 flex justify-between items-center'><div><p class='font-bold text-white'>${f}</p></div><button onclick="location.href='/download/${f}?user_id=${UID}'" class='bg-white text-black px-4 py-2 rounded-xl text-sm font-bold'>تحميل</button></div>`;});
  document.getElementById('list').innerHTML=h;
}
load();
</script></body></html>"""

ADMIN_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin Pro MAX</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#080810] text-white min-h-screen p-4">
<div id="toast" class="fixed top-4 right-4 z-50 hidden"><div id="toastBox" class="bg-emerald-500 text-black px-6 py-3 rounded-xl font-bold shadow-2xl text-sm"><span id="toastText"></span></div></div>
<div class="max-w-7xl mx-auto"><div class="flex justify-between items-center mb-6"><h1 class="text-2xl font-bold">لوحة التحكم <span class="text-emerald-400">Pro MAX</span></h1><button onclick="load()" class="bg-emerald-500 text-black px-4 py-2 rounded-xl text-sm font-bold">تحديث</button></div>
<div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6"><div class="bg-emerald-900/40 p-5 rounded-2xl"><p class="text-gray-400 text-xs">النشطين</p><p id="active" class="text-3xl font-bold">--</p></div><div class="bg-[#1a1a2e] p-5 rounded-2xl"><p class="text-gray-400 text-xs">الكل</p><p id="total" class="text-3xl font-bold">--</p></div><div class="bg-[#1a1a2e] p-5 rounded-2xl"><p class="text-gray-400 text-xs">منتهي</p><p id="exp" class="text-3xl font-bold text-red-400">--</p></div><div class="bg-yellow-900/30 p-5 rounded-2xl"><p class="text-gray-400 text-xs">الارباح</p><p id="rev" class="text-xl font-bold text-yellow-400">--</p></div></div>
<div class="bg-[#12121f] rounded-2xl border border-white/5 overflow-hidden">
<div class="p-4 bg-black/30 border-b border-white/5 flex flex-wrap gap-3 items-end">
<div><label class="text-[11px] text-gray-400">اضافة يوزر</label><div class="flex gap-2 mt-1"><input id="newUid" placeholder="USER_ID" class="bg-black border border-white/20 rounded-lg px-3 py-2 text-xs w-36 text-white"><input id="newDays" type="number" value="30" class="bg-black border border-white/20 rounded-lg px-2 py-2 text-xs w-20 text-center text-white"><button onclick="addUser()" class="bg-emerald-500 text-black px-4 py-2 rounded-lg text-xs font-bold">+ اضافة</button></div></div>
<div class="mr-auto"><input id="search" oninput="filter()" placeholder="بحث..." class="bg-black/50 border border-white/10 rounded-lg px-3 py-2 text-xs w-48"></div>
</div>
<div class="overflow-x-auto"><table class="w-full text-sm"><thead class="text-gray-500 bg-black/30"><tr><th class="p-3 text-right">User</th><th class="p-3">متبقي</th><th class="p-3">المبلغ</th><th class="p-3">الحالة</th><th class="p-3 min-w-[650px]">تحكم</th></tr></thead><tbody id="tb"></tbody></table></div></div></div>
<script>
const KEY=new URLSearchParams(location.search).get("key");let ALL=[];
function showToast(msg,color="emerald"){let t=document.getElementById('toast'),box=document.getElementById('toastBox'),txt=document.getElementById('toastText');txt.innerText=msg;box.className=`px-6 py-3 rounded-xl font-bold shadow-2xl text-sm ${color==='red'?'bg-red-500 text-white':color==='blue'?'bg-blue-500 text-white':'bg-emerald-500 text-black'}`;t.classList.remove('hidden');setTimeout(()=>{t.classList.add('hidden')},3000);}
async function load(){let s=await fetch(`/admin/stats?key=${KEY}`).then(r=>r.json());document.getElementById('active').innerText=s.active_users;document.getElementById('total').innerText=s.total_users;document.getElementById('exp').innerText=s.expired;document.getElementById('rev').innerText=s.total_revenue+" USDT";let u=await fetch(`/admin/users?key=${KEY}`).then(r=>r.json());ALL=u;render(u);}
function render(list){let h="";list.forEach(x=>{
  let status=x.raw_status==='inactive' ? '<span class="bg-orange-900/50 text-orange-300 px-2 py-1 rounded-full text-xs">⏸️ معطل</span>' : x.is_paid ? '<span class="bg-emerald-900/50 text-emerald-300 px-2 py-1 rounded-full text-xs">✅ نشط</span>' : '<span class="bg-red-900/50 text-red-300 px-2 py-1 rounded-full text-xs">❌ منتهي</span>';
  let toggle=x.raw_status==='inactive' ? `<button onclick="toggleUser('${x.user_id}')" class='bg-emerald-900/50 text-emerald-300 px-2 py-1.5 rounded-lg text-xs'>🟢 تنشيط</button>` : `<button onclick="toggleUser('${x.user_id}')" class='bg-orange-900/50 text-orange-300 px-2 py-1.5 rounded-lg text-xs'>🔴 تعطيل</button>`;
  h+=`<tr class='border-b border-white/5'><td class='p-3 font-mono text-xs'><a href='/admin/view/${x.user_id}?key=${KEY}' target='_blank' class='text-cyan-400 underline'>${x.user_id}</a></td><td class='p-3 text-xs'>${x.remaining||''}</td><td class='p-3 text-emerald-400'>${x.amount_paid||0}</td><td class='p-3'>${status}</td><td class='p-2 flex gap-1 flex-wrap'>${toggle}<input id='d_${x.user_id}' type='number' value='30' class='bg-black border border-white/20 rounded-lg w-14 px-2 py-1.5 text-xs text-center text-white'><button onclick="extCustom('${x.user_id}')" class='bg-white text-black px-2 py-1.5 rounded-lg text-xs font-bold'>+ اضافة</button><a href='/content/${x.user_id}' target='_blank' class='bg-purple-900/40 text-purple-300 px-2 py-1.5 rounded-lg text-xs'>📁 محتوى</a><button onclick="resetU('${x.user_id}')" class='bg-gray-700 px-2 py-1.5 rounded-lg text-xs'>تصفير</button><button onclick="del('${x.user_id}')" class='bg-red-900/50 text-red-300 px-2 py-1.5 rounded-lg text-xs'>حذف</button></td></tr>`});document.getElementById('tb').innerHTML=h}
function filter(){let q=document.getElementById('search').value;render(ALL.filter(x=>x.user_id.toLowerCase().includes(q.toLowerCase())))}
async function addUser(){let uid=document.getElementById('newUid').value.trim();let days=parseInt(document.getElementById('newDays').value)||0;if(!uid){showToast('اكتب ID','red');return;}let r=await fetch(`/admin/add_user?key=${KEY}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:uid,days:days})});let j=await r.json();if(j.ok){showToast('✅ '+uid,'emerald');document.getElementById('newUid').value='';load();}else{showToast(j.error||'موجود','red');}}
async function del(uid){if(!confirm('حذف '+uid+' ?'))return;await fetch(`/admin/delete?key=${KEY}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:uid})});showToast('🗑️ '+uid,'red');load();}
async function resetU(uid){await fetch(`/admin/reset?key=${KEY}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:uid})});showToast('🔄 تصفير '+uid,'blue');load();}
async function extCustom(uid){let days=parseInt(document.getElementById('d_'+uid).value)||0;await fetch(`/admin/extend?key=${KEY}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:uid,days:days})});showToast('✅ +'+days+' يوم','emerald');load();}
async function toggleUser(uid){let r=await fetch(`/admin/toggle?key=${KEY}`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({user_id:uid})});let j=await r.json();showToast(j.action==='enabled'?'✅ تنشيط':'⏸️ تعطيل',j.action==='enabled'?'emerald':'red');load();}
load();
</script></body></html>"""

@app.route('/')
def home(): return "OK - 1$ Min Any Amount", 200
@app.route('/pay/<user_id>')
def pay_page(user_id): return Response(PAY_HTML.replace("__WALLET__", ROOT_WALLET).replace("__UID__", user_id), mimetype='text/html')
@app.route('/content/<user_id>')
def content_page(user_id): return Response(CONTENT_HTML.replace("__UID__", user_id), mimetype='text/html')
@app.route('/amount/<user_id>')
def amount_api(user_id): return jsonify({"amount": amount_for(user_id), "wallet": ROOT_WALLET})
@app.route('/api/files')
def api_files(): return jsonify([{"id":f,"name":f} for f in FILES])

@app.route('/verify/<user_id>')
def verify_api(user_id):
    ok, tx, amt = check_payment(user_id)
    if ok:
        exp = datetime.now() + timedelta(days=30)
        user=get_user(user_id)
        if not user: user={"user_id":user_id}
        user["expires_at"]=exp.strftime("%Y-%m-%d %H:%M:%S"); user["status"]="active"; save_user(user)
        try: supabase.table("subscriptions").upsert({"user_id":user_id,"expire_at":exp.isoformat(),"is_paid":True,"tx_hash":tx,"amount_paid":amt}).execute()
        except: pass
        return jsonify({"paid":True})
    return jsonify({"paid":False,"amount":amt})

@app.route('/check', methods=['GET'])
def check():
    user_id = request.args.get('user_id')
    if not user_id: return jsonify({"error": "user_id missing"}), 400
    now = datetime.now(); user = get_user(user_id)
    base_url = request.host_url
    links = [f"{base_url}download/{f}?user_id={user_id}" for f in FILES]
    if not user:
        expires = now + timedelta(hours=2)
        user = {"user_id": user_id, "expires_at": expires.strftime("%Y-%m-%d %H:%M:%S"), "status": "active"}
        save_user(user)
        return jsonify({"status": "active", "links": links, "files": FILES, "hours": "2:00", "content_url": f"/content/{user_id}", "pay_url": f"/pay/{user_id}"})
    if user.get("status")=="inactive":
        return jsonify({"status": "disabled", "message": "تم تعطيل حسابك من الادارة", "hours": "معطل", "files": FILES, "pay_url": f"/pay/{user_id}", "content_url": f"/content/{user_id}"})
    remaining = get_remaining_hours(user)
    if remaining <= 0:
        last_expire = datetime.strptime(user["expires_at"], "%Y-%m-%d %H:%M:%S")
        hours_since_expire = (now - last_expire).total_seconds() / 3600
        if hours_since_expire >= 24:
            new_expire = now + timedelta(hours=2)
            user["expires_at"] = new_expire.strftime("%Y-%m-%d %H:%M:%S"); user["status"]="active"; save_user(user)
            return jsonify({"status": "active", "links": links, "files": FILES, "hours": "2:00", "content_url": f"/content/{user_id}"})
        else:
            remaining_cooldown = 24 - hours_since_expire
            save_user(user)
            return jsonify({"status": "cooldown", "message": f"انتهى - انتظر {format_hm(remaining_cooldown)} او ادفع", "hours": format_hm(remaining_cooldown), "files": FILES, "pay_url": f"/pay/{user_id}", "content_url": f"/content/{user_id}"})
    return jsonify({"status": "active", "links": links, "files": FILES, "hours": format_hm(remaining), "content_url": f"/content/{user_id}", "pay_url": f"/pay/{user_id}"})

@app.route('/download/<filename>')
def download(filename):
    user_id = request.args.get('user_id')
    if not user_id: return "user_id missing", 400
    user = get_user(user_id)
    if not user: return redirect(f"/pay/{user_id}")
    if user.get("status")=="inactive": return Response("🚫 تم تعطيل حسابك", 403)
    if get_remaining_hours(user) <= 0: return redirect(f"/pay/{user_id}")
    if filename not in FILES: return f"File {filename} not allowed", 403
    if filename == "File.npvt":
        gdrive_url = f"https://drive.google.com/uc?export=download&id={DRIVE_NPVT_ID}"
        r = requests.get(gdrive_url, stream=True, timeout=30)
        return Response(r.iter_content(chunk_size=8192), mimetype='application/octet-stream', headers={"Content-Disposition": f"attachment;filename={filename}"})
    file_path = os.path.join(FOLDER, filename)
    if not os.path.exists(file_path): return f"File {filename} not found", 404
    with open(file_path, 'rb') as f: data = f.read()
    return Response(data, mimetype='application/octet-stream', headers={"Content-Disposition": f"attachment;filename={filename}"})

@app.route("/admin")
def admin():
    if request.args.get("key")!=ADMIN_KEY: return Response("401 ?key=",401)
    return Response(ADMIN_HTML, mimetype='text/html')

@app.route("/admin/stats")
def a_stats():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    users = supabase.table("users").select("*").execute().data
    active = sum(1 for u in users if u.get("status")!="inactive" and get_remaining_hours(u)>0)
    try: subs = supabase.table("subscriptions").select("*").execute().data; rev = sum(float(s.get("amount_paid",0) or 0) for s in subs)
    except: rev=0
    return jsonify({"total_users":len(users),"active_users":active,"expired":len(users)-active,"total_revenue":round(rev,4)})

@app.route("/admin/users")
def a_users():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    users = supabase.table("users").select("*").order("expires_at",desc=True).limit(200).execute().data
    out=[]
    for u in users:
        raw_status=u.get("status","active")
        is_paid = raw_status!="inactive" and get_remaining_hours(u)>0
        rem = format_hm(get_remaining_hours(u)) if raw_status!="inactive" else "معطل"
        amt=0
        try:
            r=supabase.table("subscriptions").select("*").eq("user_id",u["user_id"]).execute()
            if r.data: amt=r.data[0].get("amount_paid",0)
        except: pass
        out.append({"user_id":u["user_id"],"expire_at":u["expires_at"],"remaining":rem,"amount_paid":amt,"is_paid":is_paid,"raw_status":raw_status})
    return jsonify(out)

@app.route("/admin/add_user", methods=["POST"])
def a_add_user():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    uid=request.json.get("user_id","").strip(); days=int(request.json.get("days",0))
    if not uid: return jsonify({"error":"اكتب ID"}),400
    if get_user(uid): return jsonify({"error":"موجود مسبقا"}),400
    if days>0: exp=datetime.now()+timedelta(days=days)
    else: exp=datetime.now()
    save_user({"user_id":uid,"expires_at":exp.strftime("%Y-%m-%d %H:%M:%S"),"status":"active"})
    return jsonify({"ok":True})

@app.route("/admin/delete", methods=["POST"])
def a_del():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    uid=request.json.get("user_id"); supabase.table("users").delete().eq("user_id", uid).execute()
    try: supabase.table("subscriptions").delete().eq("user_id", uid).execute()
    except: pass
    return jsonify({"ok":True})

@app.route("/admin/reset", methods=["POST"])
def a_reset():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    uid=request.json.get("user_id"); user=get_user(uid)
    if user: user["expires_at"]=datetime.now().strftime("%Y-%m-%d %H:%M:%S"); user["status"]="active"; save_user(user)
    return jsonify({"ok":True})

@app.route("/admin/extend", methods=["POST"])
def a_ext():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    uid=request.json.get("user_id"); days=int(request.json.get("days",30)); user=get_user(uid)
    if not user: return jsonify({"error":"not found"}),404
    try: old=datetime.strptime(user["expires_at"], "%Y-%m-%d %H:%M:%S")
    except: old=datetime.now()
    if old<datetime.now(): old=datetime.now()
    user["expires_at"]=(old+timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S"); user["status"]="active"; save_user(user)
    return jsonify({"ok":True})

@app.route("/admin/toggle", methods=["POST"])
def a_toggle():
    if request.args.get("key")!=ADMIN_KEY: return jsonify({"error":"no"}),401
    uid=request.json.get("user_id"); user=get_user(uid)
    if not user: return jsonify({"error":"not found"}),404
    if user.get("status")=="inactive":
        user["expires_at"]=(datetime.now()+timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
        user["status"]="active"; save_user(user); return jsonify({"ok":True,"action":"enabled"})
    else: user["status"]="inactive"; save_user(user); return jsonify({"ok":True,"action":"disabled"})

@app.route("/admin/view/<user_id>")
def a_view(user_id):
    if request.args.get("key")!=ADMIN_KEY: return Response("401",401)
    u=get_user(user_id)
    if not u: return Response(f"<body style='background:#080810;color:white;padding:20px'><h1>{user_id} مش موجود</h1></body>",404)
    rem="معطل" if u.get("status")=="inactive" else format_hm(get_remaining_hours(u))
    html=f"<html dir='rtl'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><script src='https://cdn.tailwindcss.com'></script></head><body class='bg-[#080810] text-white p-6'><div class='max-w-lg mx-auto bg-[#12121f] rounded-2xl p-6 border border-white/10'><h1 class='text-xl font-bold mb-4'>👤 {user_id}</h1><p>متبقي: {rem}</p><p>حالة: {u.get('status')}</p><div class='mt-6 grid grid-cols-2 gap-2'><a href='/pay/{user_id}' target='_blank' class='bg-emerald-500 text-black py-3 rounded-xl text-center font-bold'>💳 دفع</a><a href='/content/{user_id}' target='_blank' class='bg-purple-600 text-white py-3 rounded-xl text-center font-bold'>📁 محتوى</a></div></div></body></html>"
    return Response(html,mimetype='text/html')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
