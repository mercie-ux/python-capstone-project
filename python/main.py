import os
import re
import time
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException

RPC_URL = "http://alice:password@127.0.0.1:18443"


def extract_address(script_pub_key):
    # Newer Bitcoin Core versions
    if "address" in script_pub_key:
        return script_pub_key["address"]

    # Older versions
    addresses = script_pub_key.get("addresses")
    if addresses:
        return addresses[0]

    # Descriptor fallback
    desc = script_pub_key.get("desc")
    if desc:
        match = re.search(r'addr\((.*?)\)', desc)
        if match:
            return match.group(1)

    return "unknown"


def ensure_wallet_loaded(client, wallet_name):
    loaded_wallets = client.listwallets()

    if wallet_name in loaded_wallets:
        print(f"{wallet_name} already loaded")
        return

    try:
        client.loadwallet(wallet_name)
        print(f"{wallet_name} loaded")
    except JSONRPCException:
        client.createwallet(wallet_name)
        print(f"{wallet_name} created")


def main():
    try:
        # General RPC client
        client = AuthServiceProxy(RPC_URL)

        # Ensure wallets exist and are loaded
        ensure_wallet_loaded(client, "Miner")
        ensure_wallet_loaded(client, "Trader")

        # Wallet RPC interfaces
        miner = AuthServiceProxy(f"{RPC_URL}/wallet/Miner")
        trader = AuthServiceProxy(f"{RPC_URL}/wallet/Trader")

        # Generate mining address
        miner_address = miner.getnewaddress("Mining Reward")

        # Mine enough blocks for mature coinbase rewards
        while miner.getbalance() < 150:
            client.generatetoaddress(1, miner_address)

        print("Miner balance:", miner.getbalance())

        # Trader receive address
        trader_address = trader.getnewaddress("Trader Receive")

        # Send BTC
        txid = miner.sendtoaddress(trader_address, 20)

        print("Transaction sent:", txid)

        # Confirm transaction
        client.generatetoaddress(1, miner_address)

        # Retry until transaction is indexed and confirmed
        MAX_RETRIES = 10
        WAIT_INTERVAL = 0.5

        wallet_tx = None

        for _ in range(MAX_RETRIES):
            try:
                wallet_tx = miner.gettransaction(txid, True)

                if wallet_tx.get("confirmations", 0) > 0:
                    break

            except JSONRPCException:
                pass

            time.sleep(WAIT_INTERVAL)

        if wallet_tx is None:
            raise Exception("Transaction not found")

        decoded_tx = wallet_tx["decoded"]

        # Transaction metadata
        block_hash = wallet_tx["blockhash"]
        block_height = wallet_tx["blockheight"]
        fee = abs(wallet_tx["fee"])

        # Inputs
        vin = decoded_tx["vin"]

        total_input_value = 0
        input_addresses = []

        for tx_input in vin:
            input_txid = tx_input["txid"]
            input_vout_index = tx_input["vout"]

            prev_tx = client.getrawtransaction(input_txid, True)
            prev_vout = prev_tx["vout"][input_vout_index]

            total_input_value += prev_vout["value"]

            input_address = extract_address(prev_vout["scriptPubKey"])
            input_addresses.append(input_address)

        primary_input_address = input_addresses[0]

        # Outputs
        trader_output = None
        change_output = None

        for out in decoded_tx["vout"]:
            out_address = extract_address(out["scriptPubKey"])

            if out_address == trader_address:
                trader_output = out
            else:
                change_output = out

        if trader_output is None or change_output is None:
            raise Exception("Could not determine outputs")

        trader_output_address = extract_address(
            trader_output["scriptPubKey"]
        )
        trader_output_amount = trader_output["value"]

        change_output_address = extract_address(
            change_output["scriptPubKey"]
        )
        change_amount = change_output["value"]

        # Write results
        out_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "out.txt"
        )

        with open(out_path, "w") as f:
            f.write(f"{txid}\n")
            f.write(f"{primary_input_address}\n")
            f.write(f"{float(total_input_value):.8f}\n")
            f.write(f"{trader_output_address}\n")
            f.write(f"{float(trader_output_amount):.8f}\n")
            f.write(f"{change_output_address}\n")
            f.write(f"{float(change_amount):.8f}\n")
            f.write(f"{float(fee):.8f}\n")
            f.write(f"{block_height}\n")
            f.write(f"{block_hash}\n")

        print("Transaction details written to out.txt")

    except Exception as e:
        print(f"Error occurred: {e}")


if __name__ == "__main__":
    main()