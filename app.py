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
FILES = ["File.npvt", "File.ssc", "File.nm"]  # نفس اللي في مجلد files عندك

def amount_for(uid):
    h = abs(hash(str(uid))) % 900 + 100
    return round(15 + h/10000, 4)

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

def get_user(user_id):
    res = supabase.table("users").select("*").eq("user_id", user_id).execute()
    return res.data[0] if res.data else None
def save_user(user): supabase.table("users").upsert(user).execute()
def get_remaining_hours(user):
    if not user or not user.get("expires_at"): return 0
    expires = datetime.strptime(user["expires_at"], "%Y-%m-%d %H:%M:%S")
    return max(0, (expires - datetime.now()).total_seconds()/3600)
def format_hm(hours_float):
    total_minutes=int(round(hours_float*60)); h=total_minutes//60; m=total_minutes%60
    if h>=24: d=h//24; rh=h%24; return f"{d} days {rh}:{m:02d}"
    return f"{h}:{m:02d}"

PAY_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>الدفع</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#0a0a12] min-h-screen flex items-center justify-center p-4"><div class="w-full max-w-md bg-[#1e1e35] rounded-[24px] p-6 border border-white/10 text-center"><h1 class="text-xl font-bold text-white">انتهى وقتك المجاني</h1><p id="amt" class="text-3xl font-bold text-emerald-400 mt-4">-- USDT</p><div class="bg-black/40 p-3 rounded-xl font-mono text-[11px] break-all mt-3 text-white text-left">__WALLET__</div><button onclick="verify()" id="btn" class="w-full bg-emerald-500 text-black py-4 rounded-xl font-bold mt-4">لقد دفعت</button><div id="status" class="mt-3 text-white"></div></div><script>let AMT=0,UID="__UID__";async function init(){let r=await fetch(`/amount/${UID}`).then(x=>x.json());AMT=r.amount;document.getElementById('amt').innerText=AMT+' USDT';}async function verify(){let b=document.getElementById('btn');b.innerHTML="⏳...";let r=await fetch(`/verify/${UID}`).then(x=>x.json());if(r.paid){document.getElementById('status').innerText="✅ تم";setTimeout(()=>location.href=`/content/${UID}`,1000);}else{document.getElementById('status').innerText="❌ لم نجد "+r.amount;b.innerHTML="لقد دفعت";}}init();</script></body></html>"""
CONTENT_HTML = """<!DOCTYPE html><html dir="rtl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>مكتبتي</title><script src="https://cdn.tailwindcss.com"></script></head><body class="bg-[#080810] min-h-screen p-4"><div class="max-w-3xl mx-auto"><h1 class="text-xl font-bold text-white mb-6">📁 مكتبتك __UID__ - <span id="time"></span></h1><div id="list"></div></div><script>const UID="__UID__";async function load(){let c=await fetch(`/check?user_id=${UID}`).then(r=>r.json());document.getElementById('time').innerText=c.hours||'';if(c.status!=='active'){document.getElementById('list').innerHTML=`<div class='bg-[#1e1e35] p-6 rounded-2xl text-center'><p class='text-white'>${c.message||'انتهى'}</p><a href='/pay/${UID}' class='mt-4 inline-block bg-emerald-500 text-black px-6 py-3 rounded-xl font-bold'>ادفع</a></div>`;return;}let h="";c.files.forEach(f=>{let src=f==='File.npvt'?'Drive':'من مجلد files';h+=`<div class='bg-[#12121f] border border-white/5 rounded-2xl p-4 flex justify-between items-center mb-3'><div><p class='text-white font-bold'>${f}</p><p class='text-xs text-gray-400'>${src}</p></div><button onclick="location.href='/download/${f}?user_id=${UID}'" class='bg-white text-black px-4 py-2 rounded-xl font-bold'>تحميل</button></div>`});document.getElementById('list').innerHTML=h;}load();</script></body></html>"""

@app.route('/')
def home(): return "OK", 200
@app.route('/pay/<user_id>')
def pay_page(user_id): return Response(PAY_HTML.replace("__WALLET__", ROOT_WALLET).replace("__UID__", user_id), mimetype='text/html')
@app.route('/content/<user_id>')
def content_page(user_id): return Response(CONTENT_HTML.replace("__UID__", user_id), mimetype='text/html')
@app.route('/amount/<user_id>')
def amount_api(user_id): return jsonify({"amount": amount_for(user_id), "wallet": ROOT_WALLET})
@app.route('/api/files')
def api_files(): return jsonify([{"id":f,"name":f,"source_type":"drive" if f=="File.npvt" else "repo"} for f in FILES])

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
        return jsonify({"status": "active", "links": links, "files": FILES, "hours": "2:00"})
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
            return jsonify({"status": "cooldown", "message": f"انتظر {format_hm(remaining_cooldown)} او ادفع", "hours": format_hm(remaining_cooldown), "files": FILES, "pay_url": f"/pay/{user_id}", "content_url": f"/content/{user_id}"})
    return jsonify({"status": "active", "links": links, "files": FILES, "hours": format_hm(remaining), "content_url": f"/content/{user_id}", "pay_url": f"/pay/{user_id}"})

@app.route('/download/<filename>')
def download(filename):
    user_id = request.args.get('user_id')
    if not user_id: return "user_id missing", 400
    user = get_user(user_id)
    if get_remaining_hours(user) <= 0: return redirect(f"/pay/{user_id}")
    if filename not in FILES: return f"File {filename} not allowed", 403

    # 1- الوحيد من Drive
    if filename == "File.npvt":
        gdrive_url = f"https://drive.google.com/uc?export=download&id={DRIVE_NPVT_ID}"
        r = requests.get(gdrive_url, stream=True, timeout=30)
        return Response(r.iter_content(chunk_size=8192), mimetype='application/octet-stream', headers={"Content-Disposition": f"attachment;filename={filename}"})

    # 2- الباقي من مجلد files اللي في GitHub (اللي في الصورة عندك)
    file_path = os.path.join(FOLDER, filename)
    if not os.path.exists(file_path): return f"File {filename} not found in repo/files - تأكد رافعه في GitHub", 404
    with open(file_path, 'rb') as f: data = f.read()
    return Response(data, mimetype='application/octet-stream', headers={"Content-Disposition": f"attachment;filename={filename}"})

@app.route('/admin', methods=['GET'])
def admin_panel():
    key = request.args.get('key')
    if key!= ADMIN_KEY: return "<h3 style='color:red'>كلمة سر غلط</h3>", 401
    now=datetime.now()
    if request.args.get('action')=='ban':
        supabase.table("users").delete().eq("user_id", request.args.get('user_id')).execute()
        return redirect(f"/admin?key={ADMIN_KEY}")
    if request.args.get('action')=='reset':
        user=get_user(request.args.get('user_id'))
        if user: user["expires_at"]=(now+timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S"); user["status"]="active"; save_user(user)
        return redirect(f"/admin?key={ADMIN_KEY}")
    all_users=supabase.table("users").select("*").order("expires_at",desc=True).execute().data
    html=f"<html dir='rtl'><head><meta charset='utf-8'><script src='https://cdn.tailwindcss.com'></script></head><body class='bg-[#080810] text-white p-6'><div class='max-w-5xl mx-auto bg-[#12121f] rounded-2xl p-6'><h2 class='text-center font-bold text-xl'>لوحة التحكم - القديم + دفع</h2><p class='text-center text-sm text-gray-400 mt-2'>File.npvt من Drive - الباقي من files/ في GitHub</p><table class='w-full mt-6 text-sm'><tr class='bg-[#1e1e35]'><th class='p-2'>ID</th><th>متبقي</th><th>تحكم</th></tr>"
    for u in all_users:
        html+=f"<tr class='border-b border-white/5'><td class='p-2 font-mono'><a href='/content/{u['user_id']}' target='_blank' class='text-cyan-300'>{u['user_id']}</a></td><td class='p-2'>{format_hm(get_remaining_hours(u))}</td><td class='p-2'><a href='/admin?key={ADMIN_KEY}&action=reset&user_id={u['user_id']}' class='bg-gray-600 px-2 py-1 rounded'>تصفير</a> <a href='/pay/{u['user_id']}' target='_blank' class='bg-emerald-500 text-black px-2 py-1 rounded'>دفع</a> <a href='/admin?key={ADMIN_KEY}&action=ban&user_id={u['user_id']}' class='bg-red-600 px-2 py-1 rounded'>حذف</a></td></tr>"
    html+="</table></div></body></html>"
    return html

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
