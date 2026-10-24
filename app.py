from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os, base64, requests, hmac, hashlib, base58
from datetime import datetime, timedelta
from Crypto.Hash import keccak
from ecdsa import SECP256k1
from ecdsa.ellipticcurve import Point
from supabase import create_client

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = os.getenv("API_URL", "https://kodular-api-1.onrender.com")
XPUB_BNB = os.getenv("XPUB_BNB")
ADMIN_KEY = os.getenv("ADMIN_KEY", "123456")

USDT_BEP20 = "0x55d398326f99059fF775485246999027B3196775"
PRICE_USDT = 15
ROOT_WALLET = "0x5430161DA6be4EF2B1Cfd2452F076eB67Db3BAc0"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def get_bnb_address(user_index):
    if not XPUB_BNB:
        return ROOT_WALLET
    try:
        xpub_clean = XPUB_BNB.strip()
        raw = base58.b58decode_check(xpub_clean)
        if len(raw) != 78:
            return ROOT_WALLET
        chain = raw[13:45]
        pub_compressed = raw[45:78]
        x = int.from_bytes(pub_compressed[1:], 'big')
        p = SECP256k1.curve.p()
        y_sq = (pow(x, 3, p) + 7) % p
        y = pow(y_sq, (p+1)//4, p)
        if (y % 2 == 0) != (pub_compressed[0] == 2):
            y = p - y
        def ckd(chain_code, px, py, idx):
            parity = b'\x02' if py % 2 == 0 else b'\x03'
            pub = parity + px.to_bytes(32, 'big')
            data = pub + idx.to_bytes(4, 'big')
            I = hmac.new(chain_code, data, hashlib.sha512).digest()
            il = int.from_bytes(I[:32], 'big')
            G = SECP256k1.generator
            curve = SECP256k1.curve
            parent_point = Point(curve, px, py)
            child_point = parent_point + il * G
            return I[32:], child_point.x(), child_point.y()
        c1, x1, y1 = ckd(chain, x, y, 0)
        _, x2, y2 = ckd(c1, x1, y1, user_index)
        k = keccak.new(digest_bits=256)
        k.update(b'\x04' + x2.to_bytes(32,'big') + y2.to_bytes(32,'big'))
        addr_hex = k.digest()[-20:].hex()
        k2 = keccak.new(digest_bits=256)
        k2.update(addr_hex.encode())
        hash_hex = k2.hexdigest()
        checksum = "".join(c.upper() if int(hash_hex[i],16) >= 8 else c for i,c in enumerate(addr_hex))
        return "0x" + checksum
    except:
        return ROOT_WALLET

def check_bnb_payment(bnb_address):
    try:
        rpc_url = "https://bsc-dataseed.binance.org/"
        addr_clean = bnb_address.lower().replace("0x","")
        data = "0x70a08231" + "0"*24 + addr_clean
        payload = {"jsonrpc":"2.0","method":"eth_call","params":[{"to":USDT_BEP20,"data":data},"latest"],"id":1}
        resp = requests.post(rpc_url, json=payload, timeout=15)
        r = resp.json()
        balance_hex = r.get("result","0x0")
        balance_int = 0 if not balance_hex or balance_hex == "0x" else int(balance_hex, 16)
        balance_usdt = balance_int / 10**18
        if balance_usdt >= 14.9:
            return True, f"balance_{balance_usdt}"
        return False, f"balance_{balance_usdt}"
    except Exception as e:
        return False, str(e)

@app.route("/")
def home():
    return f"OK - BNB System Working - ROOT {ROOT_WALLET}"

@app.route("/pay/<user_id>")
def pay_page(user_id):
    user_hash = abs(hash(user_id)) % 2147483647
    bnb_addr = get_bnb_address(user_hash)
    html = f"""<html><head><meta name="viewport" content="width=device-width"><meta charset="utf-8">
    <style>body{{background:#1a1a2e;color:#fff;font-family:Arial;text-align:center;padding:20px}}.box{{background:#16213e;padding:25px;border-radius:15px;max-width:450px;margin:auto;border:1px solid #0f3460}}.addr{{background:#000;padding:15px;word-break:break-all;border-radius:10px;font-size:14px;margin:15px 0;border:1px dashed #e94560}}button{{padding:15px 25px;border:none;border-radius:10px;font-weight:bold;cursor:pointer;margin:5px;width:100%}}.copy{{background:#e94560;color:#fff}}.check{{background:#0f3460;color:#fff}}</style></head><body>
    <div class="box"><h2>دفع 15 USDT (BEP20)</h2><p>يوزر: {user_id}</p><p>الشبكة: <b>BSC / BEP20</b></p><div class="addr" id="addr">{bnb_addr}</div>
    <button class="copy" onclick="navigator.clipboard.writeText('{bnb_addr}');this.innerText='تم النسخ'">نسخ العنوان</button>
    <button class="check" onclick="window.location.href='/verify/{user_id}'">تحقق من الدفع</button></div></body></html>"""
    return Response(html, mimetype='text/html')

@app.route("/verify/<user_id>")
def verify_payment(user_id):
    user_hash = abs(hash(user_id)) % 2147483647
    bnb_addr = get_bnb_address(user_hash)
    paid, info = check_bnb_payment(bnb_addr)
    if paid and supabase:
        try:
            existing = supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
            new_expire = datetime.utcnow() + timedelta(days=30)
            if existing.data:
                supabase.table("subscriptions").update({"expire_at": new_expire.isoformat(), "is_paid": True, "bnb_addr": bnb_addr}).eq("user_id", user_id).execute()
            else:
                supabase.table("subscriptions").insert({"user_id": user_id, "expire_at": new_expire.isoformat(), "is_paid": True, "bnb_addr": bnb_addr}).execute()
        except: pass
    return jsonify({"paid": paid, "tx": info, "bnb_addr": bnb_addr})

@app.route("/admin")
@app.route("/admin")
def admin_dashboard():
    key = request.args.get("key", "")
    if key != ADMIN_KEY:
        return "Unauthorized - add ?key=123456", 401
    try:
        if not supabase:
            return "No DB connected"
        all_subs = supabase.table("subscriptions").select("*").order("created_at", desc=True).limit(100).execute()
        data = all_subs.data or []
        rows = ""
        for sub in data:
            bnb_addr = sub.get("bnb_addr","")
            if not bnb_addr: 
                continue
            uid = sub.get("user_id","")
            # نوري الرابط فقط - بلا ما نكلم bsc
            rows += f"<tr><td>{uid}</td><td style='font-size:10px'><a href='https://bscscan.com/address/{bnb_addr}' target='_blank' style='color:#4db8ff'>{bnb_addr}</a></td><td><a href='https://bscscan.com/address/{bnb_addr}#tokentxns' target='_blank' style='background:#e94560;color:#fff;padding:5px 8px;border-radius:6px;text-decoration:none'>كشف BscScan</a></td></tr>"
        
        html = f"""
        <html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width'>
        <style>body{{background:#0a0a0f;color:#fff;font-family:Arial;padding:15px}}
        .box{{background:#16162a;padding:20px;border-radius:15px;max-width:1000px;margin:auto}}
        table{{width:100%;border-collapse:collapse}}th,td{{border:1px solid #333;padding:8px;font-size:12px}}th{{background:#1e1e3a}}</style>
        </head><body><div class='box'>
        <h2>لوحة تحكم - روابط الدفع</h2>
        <p>عدد العناوين: {len(data)} | ROOT: {ROOT_WALLET}</p>
        <table><tr><th>User</th><th>رابط الدفع (العنوان الفرعي)</th><th>الدليل</th></tr>{rows if rows else '<tr><td colspan=3>مافيش بيانات</td></tr>'}</table>
        <p style='font-size:11px;opacity:0.6;margin-top:15px'>اضغط على كشف BscScan باش تشوف هل دفع ولا لا - الميتاماسك ما يوريش</p>
        </div></body></html>
        """
        return Response(html, mimetype='text/html')
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Admin Error: {e}", 500

@app.route("/getfile/<file_id>")
def get_file(file_id):
    user_id = request.args.get("user_id", "unknown")
    sub = supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
    if not sub.data:
        return jsonify({"error": "not_subscribed", "pay_url": f"{API_URL}/pay/{user_id}"}), 403
    expire_str = sub.data[0].get("expire_at")
    try:
        exp = datetime.fromisoformat(expire_str.replace("Z","+00:00").replace("+00:00",""))
        if exp.tzinfo: exp = exp.replace(tzinfo=None)
        if exp < datetime.utcnow():
            return jsonify({"error": "expired", "pay_url": f"{API_URL}/pay/{user_id}"}), 403
    except:
        return jsonify({"error": "expired"}), 403
    try:
        file_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        r = requests.get(file_url, timeout=30)
        b64 = base64.b64encode(r.content).decode()
        return jsonify({"file": b64})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
