from flask import Flask, request, jsonify, Response
from flask_cors import CORS
import os, base64, requests, hashlib
from datetime import datetime, timedelta
from supabase import create_client
from eth_account import Account
Account.enable_unaudited_hdwallet_features()

app = Flask(__name__)
CORS(app)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MNEMONIC = os.getenv("MNEMONIC")
API_URL = os.getenv("API_URL", "https://kodular-api-1.onrender.com")
ADMIN_KEY = os.getenv("ADMIN_KEY", "123456")
USDT_BEP20 = "0x55d398326f99059fF775485246999027B3196775"
ROOT_WALLET = "0x5430161DA6be4EF2B1Cfd2452F076eB67Db3BAc0"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def stable_hash(user_id):
    return int(hashlib.sha256(str(user_id).encode()).hexdigest(), 16) % 2147483647

def get_bnb_address(user_index):
    if not MNEMONIC:
        return ROOT_WALLET
    acct = Account.from_mnemonic(MNEMONIC, account_path=f"m/44'/60'/0'/0/0/{user_index}")
    return acct.address

@app.route("/sweep_all_old")
def sweep_all_old():
    try:
        import base58, hmac, hashlib
        xpub = os.getenv("XPUB_BNB","").strip()
        if not xpub or not supabase:
            return jsonify({"error":"XPUB او SUPABASE ناقص"})

        P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEFFFFFC2F
        def decompress_pub(compressed):
            prefix = compressed[0]
            x = int.from_bytes(compressed[1:], 'big')
            y_sq = (pow(x,3,P) + 7) % P
            y = pow(y_sq, (P+1)//4, P)
            if (y % 2 == 0 and prefix == 3) or (y % 2 == 1 and prefix == 2):
                y = P - y
            return x, y

        def compress_pub(x,y):
            prefix = b'\x02' if y % 2 == 0 else b'\x03'
            return prefix + x.to_bytes(32,'big')

        def decode_xpub(xpub_str):
            dec = base58.b58decode_check(xpub_str)
            return dec[45:78], dec[13:45]
        
        def ckd(pub_compressed, chain, index):
            from ecdsa import SECP256k1
            from ecdsa.ellipticcurve import Point
            data = pub_compressed + index.to_bytes(4,'big')
            I = hmac.new(chain, data, hashlib.sha512).digest()
            il_int = int.from_bytes(I[:32],'big')
            x1, y1 = decompress_pub(pub_compressed)
            parent_point = Point(SECP256k1.curve, x1, y1, SECP256k1.order)
            child_point = il_int * SECP256k1.generator + parent_point
            child_pub = compress_pub(child_point.x(), child_point.y())
            return child_pub, I[32:]
        
        def pub_to_addr(pub_compressed):
            from eth_hash.auto import keccak
            x, y = decompress_pub(pub_compressed)
            uncompressed = x.to_bytes(32,'big') + y.to_bytes(32,'big')
            keccak_hash = keccak(uncompressed)
            return "0x" + keccak_hash[-20:].hex()

        def stable_hash_old(user_id):
            return int(hashlib.sha256(str(user_id).encode()).hexdigest(), 16) % 2147483647

        subs = supabase.table("subscriptions").select("user_id").limit(500).execute()
        users = subs.data if subs.data else []

        pub0, chain0 = decode_xpub(xpub)
        pub1, chain1 = ckd(pub0, chain0, 0)
        
        rpc = "https://bsc-dataseed.binance.org/"
        found = []
        for row in users:
            uid = row.get("user_id")
            idx = stable_hash_old(uid)
            p, c = ckd(pub1, chain1, idx)
            addr = pub_to_addr(p)
            try:
                bal_resp = requests.post(rpc, json={"jsonrpc":"2.0","method":"eth_getBalance","params":[addr,"latest"],"id":1}, timeout=5).json()
                bal = int(bal_resp.get("result","0x0"), 16)
                if bal > 0:
                    found.append({"user_id": uid, "index": idx, "addr": addr, "bnb": bal/10**18})
            except:
                continue
        
        return jsonify({"found": found, "checked": len(users)})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()})
            except:
                continue
        
        return jsonify({"found": found, "checked": len(users)})
    except Exception as e:
        return jsonify({"error": str(e), "line": str(e.__traceback__)})

def check_bnb_payment(bnb_address, test_mode=False):
    try:
        rpc_url = "https://bsc-dataseed.binance.org/"
        if test_mode:
            payload = {"jsonrpc":"2.0","method":"eth_getBalance","params":[bnb_address,"latest"],"id":1}
            resp = requests.post(rpc_url, json=payload, timeout=15).json()
            bal_wei = int(resp.get("result","0x0"), 16)
            return (bal_wei / 10**18 >= 0.0001, f"balance_{bal_wei/10**18}")
        else:
            addr_clean = bnb_address.lower().replace("0x","")
            data = "0x70a08231" + "0"*24 + addr_clean
            payload = {"jsonrpc":"2.0","method":"eth_call","params":[{"to":USDT_BEP20,"data":data},"latest"],"id":1}
            resp = requests.post(rpc_url, json=payload, timeout=15).json()
            balance_hex = resp.get("result","0x0")
            balance_int = 0 if not balance_hex or balance_hex == "0x" else int(balance_hex, 16)
            return (balance_int / 10**18 >= 14.9, f"usdt_{balance_int/10**18}")
    except Exception as e:
        return False, str(e)

@app.route("/")
def home():
    return f"OK - MNEMONIC SYSTEM - {ROOT_WALLET}"

@app.route("/getkey/<user_id>")
def getkey(user_id):
    idx = stable_hash(user_id)
    addr = get_bnb_address(idx)
    return f"User {user_id}<br>idx {idx}<br>Addr {addr}<br>هذا العنوان الصح"

@app.route("/pay/<user_id>")
def pay_page(user_id):
    bnb_addr = get_bnb_address(stable_hash(user_id))
    html = f"""<html><head><meta name="viewport" content="width=device-width"><meta charset="utf-8">
    <style>body{{background:#1a1a2e;color:#fff;font-family:Arial;text-align:center;padding:20px}}.box{{background:#16213e;padding:25px;border-radius:15px;max-width:450px;margin:auto}}.addr{{background:#000;padding:15px;word-break:break-all;border-radius:10px}}</style></head><body>
    <div class="box"><h2>دفع 15 USDT (BEP20)</h2><p>{user_id}</p><div class="addr">{bnb_addr}</div>
    <button onclick="navigator.clipboard.writeText('{bnb_addr}')">نسخ العنوان</button><br><br>
    <button onclick="window.location.href='/verify/{user_id}'">تحقق من الدفع</button></div></body></html>"""
    return Response(html, mimetype='text/html')

@app.route("/verify/<user_id>")
def verify_payment(user_id):
    bnb_addr = get_bnb_address(stable_hash(user_id))
    is_test = "test" in user_id.lower()
    paid, info = check_bnb_payment(bnb_addr, test_mode=is_test)
    if paid and supabase:
        try:
            existing = supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
            new_expire = datetime.utcnow() + timedelta(days=30)
            if existing.data:
                supabase.table("subscriptions").update({"expire_at": new_expire.isoformat(), "is_paid": True, "bnb_addr": bnb_addr}).eq("user_id", user_id).execute()
            else:
                supabase.table("subscriptions").insert({"user_id": user_id, "expire_at": new_expire.isoformat(), "is_paid": True, "bnb_addr": bnb_addr}).execute()
        except:
            pass
    return jsonify({"paid": paid, "tx": info, "bnb_addr": bnb_addr})

@app.route("/getfile/<file_id>")
def get_file(file_id):
    user_id = request.args.get("user_id", "unknown")
    if supabase:
        sub = supabase.table("subscriptions").select("*").eq("user_id", user_id).execute()
        if not sub.data:
            return jsonify({"error": "not_subscribed", "pay_url": f"{API_URL}/pay/{user_id}"}), 403
    try:
        file_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        r = requests.get(file_url, timeout=30)
        b64 = base64.b64encode(r.content).decode()
        return jsonify({"file": b64})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
