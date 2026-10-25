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

@app.route("/sweep_old/<user_id>")
def sweep_old(user_id):
    try:
        from eth_account import Account
        import hmac, hashlib
        from ecdsa import SigningKey, SECP256k1
        CURVE_N = SECP256k1.order

        def seed_from_mnemonic(m):
            return hashlib.pbkdf2_hmac('sha512', m.encode(), b'mnemonic', 2048)
        
        def priv_to_pub_compressed(p):
            sk = SigningKey.from_string(p, curve=SECP256k1)
            x = sk.verifying_key.pubkey.point.x()
            y = sk.verifying_key.pubkey.point.y()
            return (b'\x02' if y%2==0 else b'\x03') + x.to_bytes(32,'big')

        def derive(p, c, idx):
            pub = priv_to_pub_compressed(p)
            data = pub + idx.to_bytes(4,'big')
            I = hmac.new(c, data, hashlib.sha512).digest()
            child = (int.from_bytes(I[:32],'big') + int.from_bytes(p,'big')) % CURVE_N
            return child.to_bytes(32,'big'), I[32:]

        def master(s):
            I = hmac.new(b"Bitcoin seed", s, hashlib.sha512).digest()
            return I[:32], I[32:]

        seed = seed_from_mnemonic(MNEMONIC)
        priv, chain = master(seed)
        for i in [44+0x80000000, 60+0x80000000, 0+0x80000000, 0]:
            real = i-0x80000000 if i>=0x80000000 else i
            # hardened derivation simplified
            if i>=0x80000000:
                data = b'\x00' + priv + i.to_bytes(4,'big')
                I = hmac.new(chain, data, hashlib.sha512).digest()
                priv = ((int.from_bytes(I[:32],'big') + int.from_bytes(priv,'big')) % CURVE_N).to_bytes(32,'big')
                chain = I[32:]
            else:
                priv, chain = derive(priv, chain, real)

        old_idx = abs(int(hashlib.sha256(str(user_id).encode()).hexdigest(), 16)) % 2147483647
        priv, chain = derive(priv, chain, 0)
        priv, chain = derive(priv, chain, old_idx)
        
        acct = Account.from_key(priv)
        old_addr = acct.address

        rpc = "https://bsc-dataseed.binance.org/"
        bal = requests.post(rpc, json={"jsonrpc":"2.0","method":"eth_getBalance","params":[old_addr,"latest"],"id":1}, timeout=10).json()
        bal_wei = int(bal.get("result","0x0"), 16)
        
        if bal_wei == 0:
            return jsonify({"old_addr": old_addr, "balance": 0, "msg": "العنوان فاضي او الرصيد تحول خلاص"})

        gas_price = 3*10**9
        gas = 21000
        nonce = int(requests.post(rpc, json={"jsonrpc":"2.0","method":"eth_getTransactionCount","params":[old_addr,"latest"],"id":1}, timeout=10).json().get("result","0x0"),16)
        tx = {'to': ROOT_WALLET, 'value': bal_wei - gas*gas_price, 'gas': gas, 'gasPrice': gas_price, 'nonce': nonce, 'chainId': 56}
        signed = Account.sign_transaction(tx, priv)
        sent = requests.post(rpc, json={"jsonrpc":"2.0","method":"eth_sendRawTransaction","params":[signed.rawTransaction.hex()],"id":1}, timeout=10).json()
        return jsonify({"old_addr": old_addr, "root": ROOT_WALLET, "result": sent})
    except Exception as e:
        return jsonify({"error": str(e)})

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
