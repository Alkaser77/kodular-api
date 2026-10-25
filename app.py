import os
import base64
import hashlib
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS
from supabase import create_client, Client
from datetime import datetime

app = Flask(__name__)
CORS(app)

# --- ENV ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MNEMONIC = os.getenv("MNEMONIC")
ROOT_WALLET = os.getenv("ROOT_WALLET", "0x54302d5D0A43d9284C41F1C84a8B7c2c6aAcBAc0")
AIA_EXT_ID = os.getenv("AIA_EXT_ID")
AIA_URL = "https://kodular-api-1.onrender.com"

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- HELPERS ---
def stable_hash(user_id):
    return int(hashlib.sha256(str(user_id).encode()).hexdigest(), 16) % 2147483647

def get_bnb_address(user_id):
    try:
        from eth_account import Account
        Account.enable_unaudited_hdwallet_features()
        idx = stable_hash(user_id)
        acct = Account.from_mnemonic(MNEMONIC, account_path=f"m/44'/60'/0'/0/0/{idx}")
        return acct.address, idx, acct
    except Exception as e:
        return None, None, str(e)

def check_bnb_payment(address):
    try:
        rpc = "https://bsc-dataseed.binance.org/"
        payload = {"jsonrpc":"2.0","method":"eth_getBalance","params":[address,"latest"],"id":1}
        r = requests.post(rpc, json=payload, timeout=10).json()
        bal_wei = int(r.get("result","0x0"), 16)
        bal_bnb = bal_wei / 10**18
        return bal_bnb, bal_wei
    except Exception as e:
        return 0, 0

# --- ROUTES ---
@app.route("/")
def home():
    return jsonify({"status":"ok", "root": ROOT_WALLET})

@app.route("/getkey/<user_id>")
def getkey(user_id):
    addr, idx, acct_or_err = get_bnb_address(user_id)
    if not addr:
        return jsonify({"error": str(acct_or_err)})
    return jsonify({"user_id": user_id, "idx": idx, "bnb_address": addr, "root": ROOT_WALLET})

@app.route("/pay", methods=["POST"])
def pay():
    data = request.json or {}
    user_id = data.get("user_id")
    if not user_id:
        return jsonify({"error":"user_id ناقص"})
    addr, idx, _ = get_bnb_address(user_id)
    return jsonify({
        "user_id": user_id,
        "pay_to": addr,
        "amount_bnb": "0.001",
        "network": "BSC",
        "verify_url": f"{AIA_URL}/verify/{user_id}"
    })

@app.route("/verify/<user_id>")
def verify(user_id):
    addr, idx, _ = get_bnb_address(user_id)
    if not addr:
        return jsonify({"paid": False, "error": "no addr"})
    bnb, wei = check_bnb_payment(addr)
    is_test = "test" in user_id.lower()
    required = 0.0001 if is_test else 0.001
    paid = bnb >= required
    
    if paid and supabase:
        try:
            supabase.table("subscriptions").upsert({
                "user_id": user_id,
                "bnb_address": addr,
                "paid": True,
                "bnb_amount": bnb,
                "updated_at": datetime.utcnow().isoformat()
            }, on_conflict="user_id").execute()
        except Exception as e:
            print("supabase error", e)

    return jsonify({
        "paid": paid,
        "user_id": user_id,
        "bnb_address": addr,
        "idx": idx,
        "bnb_balance": bnb,
        "required": required,
        "root": ROOT_WALLET
    })

@app.route("/sweep_one/<user_id>")
def sweep_one(user_id):
    try:
        from eth_account import Account
        Account.enable_unaudited_hdwallet_features()
        idx = int(hashlib.sha256(str(user_id).encode()).hexdigest(), 16) % 2147483647
        acct = Account.from_mnemonic(MNEMONIC, account_path=f"m/44'/60'/0'/0/0/{idx}")
        addr = acct.address
        rpc = "https://bsc-dataseed.binance.org/"
        bal_resp = requests.post(rpc, json={"jsonrpc":"2.0","method":"eth_getBalance","params":[addr,"latest"],"id":1}, timeout=10).json()
        bal_wei = int(bal_resp.get("result","0x0"), 16)
        if bal_wei == 0:
            return jsonify({"addr": addr, "bnb": 0, "msg": "فاضي ما فيش BNB"})

        gas_price = 5_000_000_000
        gas_limit = 21000
        fee = gas_price * gas_limit
        if bal_wei <= fee:
            return jsonify({"addr": addr, "bnb": bal_wei/10**18, "msg": "رصيد قليل ما يكفيش للغاز"})

        nonce_resp = requests.post(rpc, json={"jsonrpc":"2.0","method":"eth_getTransactionCount","params":[addr,"latest"],"id":1}, timeout=10).json()
        nonce = int(nonce_resp.get("result","0x0"), 16)
        tx = {
            "to": ROOT_WALLET,
            "value": bal_wei - fee,
            "gas": gas_limit,
            "gasPrice": gas_price,
            "nonce": nonce,
            "chainId": 56
        }
        signed = acct.sign_transaction(tx)
        send_resp = requests.post(rpc, json={"jsonrpc":"2.0","method":"eth_sendRawTransaction","params":[signed.raw_transaction.hex()],"id":1}, timeout=10).json()
        return jsonify({"from": addr, "to": ROOT_WALLET, "bnb_sent": (bal_wei-fee)/10**18, "result": send_resp, "idx": idx})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
