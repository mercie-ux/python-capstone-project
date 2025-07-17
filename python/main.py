import os
import re
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException

# Node access params
rpcuser="alice"
rpcpassword="password"
rpcport = 18443
RPC_URL = "http://alice:password@127.0.0.1:18443"


def extract_address(script_pub_key):
    # try standard wallet
    addresses = script_pub_key.get('addresses')
    if addresses:
        return addresses[0]
    # with fallback to descriptor
    desc = script_pub_key.get('desc')
    if desc:
        match = re.search(r'addr\((.*?)\)', desc)
        if match:
            return match.group(1)
    return 'unknown'
def create_wallet_needed(client, wallet_name):
    try:
        client.createwallet(wallet_name)
        print(f"Wallet '{wallet_name}' created.")
    except JSONRPCException as e:
        if e.error['code'] == -4:
            print(f"Wallet '{wallet_name}' already exists")
        else:
            raise

def main():
    try:
        # General client for non-wallet-specific commands
        client = AuthServiceProxy(RPC_URL)

        # Get blockchain info
        blockchain_info = client.getblockchaininfo()
        print("Blockchain Info:", blockchain_info)

        # Create/Load the wallets, named 'Miner' and 'Trader'. Have logic to optionally create/load them if they do not exist or are not loaded already.
        #create/load wallets
        create_wallet_needed(client, "Miner")
        create_wallet_needed(client, "Trader")

        # wallet rpc interface
        miner = AuthServiceProxy(f"{RPC_URL}/wallet/Miner")
        trader = AuthServiceProxy(f"{RPC_URL}/wallet/Trader")

        # Generate spendable balances in the Miner wallet. Determine how many blocks need to be mined.
        # generate miner address
        miner_address = miner.getnewaddress("Mining Reward")
        #inital block count
        blocks_mined = 0
        while True:
            client.generatetoaddress(1, miner_address)
            balances = miner.getbalances()
            if balances['mine']['trusted'] > 0:
                break
            blocks_mined +=1 #Coinbase rewards take 100 blocks to mature, so up to 101 blocks might be needed
        
        #print Miner wallet balance
        print(f"Miner balance:", miner.getbalance())

        # Load the Trader wallet and generate a new address.
        trader_address = trader.getnewaddress("Received")

        # Send 20 BTC from Miner to Trader.
        txid = miner.sendtoaddress(trader_address, 20)

        # Check the transaction in the mempool.
        mempool_tx = client.getmempoolentry(txid)
        print("Mempool transaction:", mempool_tx)

        # Mine 1 block to confirm the transaction.
        client.generatetoaddress(1, miner_address)

        # Extract all required transaction details.
        raw_tx = client.getrawtransaction(txid, True)
        # Find inputs
        vin = raw_tx['vin'][0]
        input_txid =vin['txid']
        input_vout_index = vin ['vout']
        # Get input transaction to fetch input amount and address
        input_tx =client.getrawtransaction(input_txid, True)
        input_vout = input_tx['vout'][input_vout_index]

        input_value = input_vout['value']
        input_address = extract_address(input_vout['scriptPubKey'])
        
        #Find output
        vout = raw_tx['vout']
        trader_output = None
        change_output = None
        
        # Get Trader and change output
        for out in vout:
            out_address = extract_address(out['scriptPubKey'])
            if out_address == trader_address:
                trader_output = out
            else:
                change_output = out
        if not trader_output:
            trader_output =max(vout, key=lambda o: o['value'])
            trader_output_address = trader_output['scriptPubKey'].get('addresses', ['unknown'])[0]
            trader_output_amount = trader_output['value']
        else:
            trader_output_address = extract_address(trader_output['scriptPubKey'])
            trader_output_amount = trader_output['value']
        # assign change from outputs
        if not change_output:
            for out in vout:
                if out != trader_output:
                    change_output = out
                    break
        if not trader_output or not change_output:
            raise ValueError("Cannot find trader or change output.Check transaction details")
        change_output_address = extract_address(change_output['scriptPubKey'])
        change_amount = change_output['value']

        #Calculate fee 
        fee = input_value - (change_amount + trader_output_amount)

        # get blockchain information
        block_hash = raw_tx['blockhash']
        block = client.getblock(block_hash)
        block_height = block['height']
        # Write the data to ../out.txt in the specified format given in readme.md.
        out_path = os.path.join("..", "out.txt")
        with open(out_path, "w") as f:
            f.write(f"{txid}\n")
            f.write(f"{input_address}\n")
            f.write(f"{float(input_value):.8f}\n")
            f.write(f"{trader_output_address}\n")
            f.write(f"{float(trader_output_amount):.8f}\n")
            f.write(f"{change_output_address}\n")
            f.write(f"{float(change_amount):.8f}\n")
            f.write(f"{float(fee):.8f}\n")
            f.write(f"{block_height}\n")
            f.write(f"{block_hash}\n")
        
        print("Transaction details written to out.txt")
    except Exception as e:
        print("Error occurred: {}".format(e))

if __name__ == "__main__":
    main()
