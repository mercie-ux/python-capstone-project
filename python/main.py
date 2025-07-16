from decimal import Decimal
from bitcoinrpc.authproxy import AuthServiceProxy, JSONRPCException

# Node access params
rpcuser="alice"
rpcpassword="password"
rpcport = 18443
RPC_URL = "http://alice:password@127.0.0.1:18443"

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
            info = miner.getwalletinfo()
            if info['balance'] > 0:
                break
            blocks_mined +=1
            # blocks have not yet mature a coinbase transaction which is  100 blocks have been recorded, this is why it may take up to 101 block to access the balance
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
        input_address = input_vout['scriptPubKey'].get('addresses', ['unknown'])[0]
        
        #Find output
        vout = raw_tx['vout']
        trader_output = None
        change_output = None
        
        # Get Trader and change output
        for out in vout:
            addresses = out['scriptPubKey'].get('addresses', [])
            if trader_address in addresses:
                trader_output = out
            else:
                change_output = out
        if not trader_output:
            trader_output =max(vout, key=lambda o: o['value'])
            trader_output_address = trader_output['scriptPubKey'].get('addresses', ['unknown'])[0]
            trader_output_amount = trader_output['value']
        else:
            trader_output_address = trader_output['scriptPubKey']['addresses'][0]
            trader_output_amount = trader_output['value']
        # assign change from outputs
        if not change_output:
            for out in vout:
                if out != trader_output:
                    change_output = out
                    break
        if not trader_output or not change_output:
            raise ValueError("Cannot find trader or change output.Check transaction details")
        change_output_address = change_output['scriptPubKey'].get('addresses',['unknown'])[0]
        change_amount = change_output['value']

        #Calculate fee 
        fee = input_value - (change_amount + trader_output_amount)

        # get blockchain information
        block_hash = raw_tx['blockhash']
        block = client.getblock(block_hash)
        block_height = block['height']
        # Write the data to ../out.txt in the specified format given in readme.md.
        with open("out.txt", "w") as f:
            f.write(f"{txid}\n")
            f.write(f"{input_address}\n")
            f.write(f"{input_value:.8f}\n")
            f.write(f"{trader_output_address}\n")
            f.write(f"{trader_output_amount:.8f}\n")
            f.write(f"{change_output_address}\n")
            f.write(f"{change_amount:.8f}\n")
            f.write(f"{fee:.8f}\n")
            f.write(f"{block_height}\n")
            f.write(f"{block_hash}\n")
        
        print("Transaction details written to out.txt")
    except Exception as e:
        print("Error occurred: {}".format(e))

if __name__ == "__main__":
    main()
