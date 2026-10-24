from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os, json, base64, requests, hmac, hashlib, base58
from datetime import datetime, timedelta
from Crypto.Hash import keccak
from ecdsa import SECP256k1, VerifyingKey
from ecdsa.ellipticcurve import Point
from supabase import create_client
import telebot

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DRIVE_NPVT_ID = os.getenv("DRIVE_NPVT_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = os.getenv("API_URL", "https://kodular-api-1.onrender.com")
XPUB_BNB = os.getenv("XPUB_BNB")
BSC_API_KEY = os.getenv("BSC_API_KEY")
USDT_BEP20 = "0x55d398326f99059fF775485246999027B319F875"
PRICE_USDT = 15

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None
bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

def get_bnb_address(user_index):
    if not XPUB_BNB:
        return "0xSET_XPUB_IN_ENV"
    try:
        xpub_clean = XPUB_BNB.strip()
        raw = base58.b58decode_check(xpub_clean)
        if len(raw) != 78:
            return f"0xINVALID_XPUB_LEN_{len(raw)}"
        chain = raw[13:45]
        pub_compressed = raw[45:78]
        x = int.from_bytes(pub_compressed[1:], 'big')
        p = SECP256k1.curve.p()
        y_sq = (pow(x, 3, p) + 7) % p
        y = pow(y_sq, (p+1)//4, p)
        is_even = (y % 2 == 0)
        should_be_even = (pub_compressed[0] == 2)
        if is_even != should_be_even:
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
        addr_bytes = k.digest()[-20:]
        addr_hex = addr_bytes.hex()
        k2 = keccak.new(digest_bits=256)
        k2.update(addr_hex.encode())
        hash_hex = k2.hexdigest()
        checksum = "".join(c.upper() if int(hash_hex[i],16) >= 8 else c for i,c in enumerate(addr_hex))
        return "0x" + checksum
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"0xERROR_{str(e)[:40]}"

def check_bnb_payment(bnb_address):
    if not bnb_address or bnb_address.startswith("0xERROR") or bnb_address.startswith("0xSET"):
        return False, "bad_address"
    try:
        # نستخدم BSC Public RPC - مجاني
        rpc_url = "https://bsc-dataseed.binance.org/"
        
        # 1. نحول العنوان لـ balanceOf call
        # balanceOf(address) = 0x70a08231 + 32 bytes address
        addr_clean = bnb_address.lower().replace("0x","")
        data = "0x70a08231" + "0"*24 + addr_clean
        
        payload = {
            "jsonrpc": "2.0",
            "method": "eth_call",
            "params": [{"to": USDT_BEP20, "data": data}, "latest"],
            "id": 1
        }
        
        resp = requests.post(rpc_url, json=payload, timeout=15)
        r = resp.json()
        
        if "result" in r:
            balance_hex = r["result"]
            balance_int = int(balance_hex, 16)
            # USDT BEP20 has 18 decimals
            balance_usdt = balance_int / (10**18)
            print(f"Balance for {bnb_address}: {balance_usdt} USDT")
            
            if balance_usdt >= 14.9:  # 15 - fee
                return True, f"balance_{balance_usdt}"
        
        return False, f"no_tx_yet_balance_0"
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return False, str(e)

def download_from_drive(file_id):
    try:
        url = f"https://www.googleapis.com/drive/v3/files/{file_id}?alt=media&key=AIzaSyDUMMY"
        # نستخدم رابط مباشر gdrive
        url2 = f"https://drive.google.com/uc?export=download&id={file_id}"
        r = requests.get(url2, timeout=30)
        if r.status_code == 200 and len(r.content) > 100:
            return base64.b64encode(r.content).decode()
        return None
    except:
        return None

@app.route("/")
def home():
    return "OK - NO ADS - BNB System Working V4 - FIXED"

@app.route("/pay/<user_id>")
def pay_page(user_id):
    try:
        user_hash = abs(hash(user_id)) % 2147483647
        bnb_addr = get_bnb_address(user_hash)
        html = f"""
        <html><head><meta name="viewport" content="width=device-width"><meta charset="utf-8">
        <style>
        body{{background:#1a1a2e;color:#fff;font-family:Arial;text-align:center;padding:20px}}
        .box{{background:#16213e;padding:25px;border-radius:15px;max-width:450px;margin:auto;border:1px solid #0f3460}}
        .addr{{background:#000;padding:15px;word-break:break-all;border-radius:10px;font-size:14px;margin:15px 0;border:1px dashed #e94560}}
        button{{padding:15px 25px;border:none;border-radius:10px;font-weight:bold;cursor:pointer;margin:5px;width:100%}}
        .copy{{background:#e94560;color:#fff}}
        .check{{background:#0f3460;color:#fff}}
        </style></head><body>
        <div class="box">
        <h2>💰 دفع 15 USDT (BEP20)</h2>
        <p>يوزر: {user_id}</p>
        <p>الشبكة: <b>BSC / BEP20</b></p>
        <div class="addr" id="addr">{bnb_addr}</div>
        <button class="copy" onclick="navigator.clipboard.writeText('{bnb_addr}');this.innerText='✅ تم النسخ'">📋 نسخ العنوان</button>
        <button class="check" onclick="window.location.href='/verify/{user_id}'">🔍 تحقق من الدفع</button>
        <p style="font-size:12px;margin-top:20px">بعد الدفع اضغط تحقق، سيتم تفعيل 30 يوم تلقائيا</p>
        <p style="font-size:10px;opacity:0.5">{bnb_addr}</p>
        </div></body></html>
        """
        return Response(html, mimetype='text/html')
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"Pay Error: {e}", 500

@app.route("/verify/<user_id>")
def verify_payment(user_id):
    try:
        user_hash = abs(hash(user_id)) % 2147483647
        bnb_addr = get_bnb_address(user_hash)
        paid, info = check_bnb_payment(bnb_addr)
        if paid:
            if supabase:
                try:
                    existing = supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
                    new_expire = datetime.utcnow() + timedelta(days=30)
                    if existing.data:
                        old_exp = existing.data[0].get("expire_at")
                        try:
                            old_date = datetime.fromisoformat(old_exp.replace("Z","+00:00")) if old_exp else datetime.utcnow()
                            if old_date > datetime.utcnow():
                                new_expire = old_date + timedelta(days=30)
                        except:
                            pass
                        supabase.table("subscriptions").update({"expire_at": new_expire.isoformat(), "is_paid": True, "bnb_addr": bnb_addr}).eq("user_id", user_id).execute()
                    else:
                        supabase.table("subscriptions").insert({"user_id": user_id, "expire_at": new_expire.isoformat(), "is_paid": True, "bnb_addr": bnb_addr}).execute()
                    return jsonify({"paid": True, "tx": info, "expire_at": new_expire.isoformat(), "bnb_addr": bnb_addr})
                except Exception as e:
                    return jsonify({"paid": True, "tx": info, "db_error": str(e), "bnb_addr": bnb_addr})
            return jsonify({"paid": True, "tx": info, "bnb_addr": bnb_addr})
        else:
            return jsonify({"paid": False, "reason": info, "bnb_addr": bnb_addr})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"paid": False, "error": str(e)}), 500

@app.route("/getfile/<file_id>")
def get_file(file_id):
    user_id = request.args.get("user_id", "unknown")
    if not supabase:
        return jsonify({"error": "no supabase"}), 500
    try:
        sub = supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
        if not sub.data:
            return jsonify({"error": "not_subscribed", "pay_url": f"{API_URL}/pay/{user_id}"}), 403
        expire_str = sub.data[0].get("expire_at")
        try:
            exp = datetime.fromisoformat(expire_str.replace("Z","+00:00").replace("+00:00","")) if expire_str else datetime.utcnow() - timedelta(days=1)
            if exp.tzinfo:
                exp = exp.replace(tzinfo=None)
            if exp < datetime.utcnow():
                return jsonify({"error": "expired", "pay_url": f"{API_URL}/pay/{user_id}"}), 403
        except:
            return jsonify({"error": "expired", "pay_url": f"{API_URL}/pay/{user_id}"}), 403
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    try:
        file_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        r = requests.get(file_url, timeout=30)
        if r.status_code != 200:
            return jsonify({"error": "drive_error"}), 500
        b64 = base64.b64encode(r.content).decode()
        return jsonify({"file": b64})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/user/<user_id>")
def user_page(user_id):
    try:
        if not supabase:
            return "No DB"
        sub = supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
        is_paid = False
        expire = "غير مشترك"
        if sub.data:
            exp_str = sub.data[0].get("expire_at")
            try:
                exp = datetime.fromisoformat(exp_str.replace("Z","+00:00").replace("+00:00",""))
                if exp.tzinfo: exp = exp.replace(tzinfo=None)
                is_paid = exp > datetime.utcnow()
                expire = exp.strftime("%Y-%m-%d %H:%M")
            except:
                pass
        status = "✅ فعال" if is_paid else "❌ منتهي"
        html = f"""
        <html><head><meta name="viewport" content="width=device-width"><meta charset="utf-8">
        <style>body{{background:#1a1a2e;color:#fff;font-family:Arial;padding:20px;text-align:center}}.box{{background:#16213e;padding:20px;border-radius:15px;max-width:400px;margin:auto}}</style>
        </head><body><div class="box"><h3>حالة الاشتراك</h3><p>يوزر: {user_id}</p><p>{status}</p><p>ينتهي: {expire}</p>
        <a href="/pay/{user_id}" style="display:block;background:#e94560;color:#fff;padding:15px;border-radius:10px;text-decoration:none;margin-top:15px">💰 ترقية 30 يوم - 15 USDT</a>
        </div></body></html>
        """
        return Response(html, mimetype='text/html')
    except Exception as e:
        return str(e), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
