from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os, base64, requests, hmac, hashlib, base58
from datetime import datetime, timedelta
from Crypto.Hash import keccak
from ecdsa import SECP256k1
from ecdsa.ellipticcurve import Point
from supabase import create_client 
from bip32utils import BIP32Key
from eth_account import Account
import traceback

app = Flask(__name__)
CORS(app) 

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
API_URL = os.getenv("API_URL", "https://kodular-api-1.onrender.com")
XPUB_BNB = os.getenv("XPUB_BNB") 
XPRV_OLD = os.getenv("XPRV_OLD", "").strip()

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
    except Exception as e:
        traceback.print_exc()
        return ROOT_WALLET 

def check_bnb_payment(bnb_address):
    if not bnb_address or bnb_address.startswith("0xERROR") or bnb_address.startswith("0xSET"):
        return False, "bad_address"
    try:
        rpc_url = "https://bsc-dataseed.binance.org/"
        addr_clean = bnb_address.lower().replace("0x","")
        data = "0x70a08231" + "0"*24 + addr_clean
        payload = {"jsonrpc":"2.0","method":"eth_call","params":[{"to":USDT_BEP20,"data":data},"latest"],"id":1}
        resp = requests.post(rpc_url, json=payload, timeout=15)
        r = resp.json()
        balance_hex = r.get("result","0x0")
        balance_int = 0 if not balance_hex or balance_hex in ["0x","0x0"] else int(balance_hex, 16)
        balance_usdt = balance_int / 10**18
        if balance_usdt >= 14.9:
            return True, f"balance_{balance_usdt}"
        return False, f"balance_{balance_usdt}"
    except Exception as e:
        traceback.print_exc()
        return False, str(e) 

@app.route("/")
def home():
    return f"OK - BNB System Working - ROOT {ROOT_WALLET} - XPUB {'OK' if XPUB_BNB else 'MISSING'} - XPRV_OLD {'OK' if XPRV_OLD else 'MISSING'}" 

@app.route("/pay/<user_id>")
def pay_page(user_id):
    try:
        user_hash = abs(hash(user_id)) % 2147483647
        bnb_addr = get_bnb_address(user_hash)
        html = f"""<html><head><meta name="viewport" content="width=device-width"><meta charset="utf-8"><style>body{{background:#1a1a2e;color:#fff;font-family:Arial;text-align:center;padding:20px}}.box{{background:#16213e;padding:25px;border-radius:15px;max-width:450px;margin:auto;border:1px solid #0f3460}}.addr{{background:#000;padding:15px;word-break:break-all;border-radius:10px;font-size:14px;margin:15px 0;border:1px dashed #e94560}}button{{padding:15px 25px;border:none;border-radius:10px;font-weight:bold;cursor:pointer;margin:5px;width:100%}}.copy{{background:#e94560;color:#fff}}.check{{background:#0f3460;color:#fff}}</style></head><body><div class="box"><h2>💰 دفع 15 USDT (BEP20)</h2><p>يوزر: {user_id}</p><p>الشبكة: <b>BSC / BEP20</b></p><div class="addr" id="addr">{bnb_addr}</div><button class="copy" onclick="navigator.clipboard.writeText('{bnb_addr}');this.innerText='✅ تم النسخ'">📋 نسخ العنوان</button><button class="check" onclick="window.location.href='/verify/{user_id}'">🔍 تحقق من الدفع</button></div></body></html>"""
        return Response(html, mimetype='text/html')
    except Exception as e:
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
                            if old_date.replace(tzinfo=None) > datetime.utcnow():
                                new_expire = old_date.replace(tzinfo=None) + timedelta(days=30)
                        except: pass
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
            if exp.tzinfo: exp = exp.replace(tzinfo=None)
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
            except: pass
        status = "✅ فعال" if is_paid else "❌ منتهي"
        html = f"""<html><head><meta name="viewport" content="width=device-width"><meta charset="utf-8"><style>body{{background:#1a1a2e;color:#fff;font-family:Arial;padding:20px;text-align:center}}.box{{background:#16213e;padding:20px;border-radius:15px;max-width:400px;margin:auto}}</style></head><body><div class="box"><h3>حالة الاشتراك</h3><p>يوزر: {user_id}</p><p>{status}</p><p>ينتهي: {expire}</p><a href="/pay/{user_id}" style="display:block;background:#e94560;color:#fff;padding:15px;border-radius:10px;text-decoration:none;margin-top:15px">💰 ترقية 30 يوم - 15 USDT</a></div></body></html>"""
        return Response(html, mimetype='text/html')
    except Exception as e:
        return str(e), 500 

@app.route("/find_old")
def find_old():
    target = request.args.get("addr", "0x7D6a002E87c6F36873cdBfc01D759Fe020E22549").lower()
    start = int(request.args.get("start", "0"))
    count = int(request.args.get("count", "10000"))
    if not XPRV_OLD:
        return jsonify({"error": "XPRV_OLD ناقص"})
    try:
        master = BIP32Key.fromExtendedKey(XPRV_OLD)
        for i in range(start, start+count):
            try:
                c = master.ChildKey(0).ChildKey(i)
                addr = Account.from_key(c.PrivateKey()).address.lower()
                if addr == target.lower():
                    return jsonify({"found": True, "index": i, "path": f"0/{i}", "address": addr})
            except: pass
            try:
                c = master.ChildKey(0).ChildKey(0).ChildKey(i)
                addr = Account.from_key(c.PrivateKey()).address.lower()
                if addr == target.lower():
                    return jsonify({"found": True, "index": i, "path": f"0/0/{i}", "address": addr})
            except: pass
        return jsonify({"found": False, "checked": f"{start} to {start+count}", "next_url": f"/find_old?addr={target}&start={start+count}&count={count}"})
    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()})

@app.route("/sweep_old_final")
def sweep_old_final():
    if not XPRV_OLD:
        return jsonify({"error": "XPRV_OLD مش موجود في Environment"})
    try:
        target = request.args.get("addr", "0x7D6a002E87c6F36873cdBfc01D759Fe020E22549")
        rpc = "https://bsc-dataseed.binance.org/"
        master = BIP32Key.fromExtendedKey(XPRV_OLD)
        found = None
        fpath = ""
        # يدور 5000 الاولى بسرعة
        for i in range(5000):
            try:
                c = master.ChildKey(0).ChildKey(i)
                if Account.from_key(c.PrivateKey()).address.lower() == target.lower():
                    found = c; fpath = f"0/{i}"; break
            except: pass
            try:
                c = master.ChildKey(0).ChildKey(0).ChildKey(i)
                if Account.from_key(c.PrivateKey()).address.lower() == target.lower():
                    found = c; fpath = f"0/0/{i}"; break
            except: pass
        if not found:
            return jsonify({"error": f"ما لقيتش {target} في 5000، استعمل /find_old باش تدور في الالاف", "hint": f"/find_old?addr={target}&start=0&count=10000"})
        acct = Account.from_key(found.PrivateKey())
        bal_r = requests.post(rpc, json={"jsonrpc":"2.0","method":"eth_getBalance","params":[acct.address,"latest"],"id":1}, timeout=15).json()
        bal_wei = int(bal_r.get("result","0x0"), 16)
        if bal_wei == 0:
            return jsonify({"addr": acct.address, "path": fpath, "balance": 0})
        gas_price = 5_000_000_000
        gas_limit = 21000
        fee = gas_price * gas_limit
        nonce_r = requests.post(rpc, json={"jsonrpc":"2.0","method":"eth_getTransactionCount","params":[acct.address,"latest"],"id":1}, timeout=15).json()
        nonce = int(nonce_r.get("result","0x0"), 16)
        tx = {"to": ROOT_WALLET, "value": bal_wei - fee, "gas": gas_limit, "gasPrice": gas_price, "nonce": nonce, "chainId": 56}
        signed = acct.sign_transaction(tx)
        raw = signed.raw_transaction if hasattr(signed,'raw_transaction') else signed.rawTransaction
        send_r = requests.post(rpc, json={"jsonrpc":"2.0","method":"eth_sendRawTransaction","params":[raw.hex()],"id":1}, timeout=15).json()
        return jsonify({"from": acct.address, "path": fpath, "sent": (bal_wei-fee)/1e18, "result": send_r})
    except Exception as e:
        return jsonify({"error": str(e), "trace": traceback.format_exc()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
