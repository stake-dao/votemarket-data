import requests, logging, os, time, json
from web3 import Web3

def load_json(name):
    with open("abi/" + name + ".json", "r") as f:
        return json.load(f)
    
def isNullAddress(addr):
    return addr == "0x0000000000000000000000000000000000000000"
    
def bounties(config): 
    w3 = Web3(Web3.HTTPProvider('https://mainnet.infura.io/v3/4c7ecc406ff04ac68659d8309fd7db47'))
    if w3.isConnected() == False:
        logging.error("RPC down")
        return

    platforms = config["platforms"]
    platformAbi = load_json("Platform")

    bountiesClosedData = {}

    for platform in platforms:
        platformContract = w3.eth.contract(address=Web3.toChecksumAddress(platform["contract"]), abi=platformAbi)
        nextID = platformContract.functions.nextID().call()
        
        bountiesClosed = []
        for i in range(nextID):
            bounty = platformContract.functions.getBounty(i).call()
            if isNullAddress(bounty[1]):
                bountiesClosed.append(i)

        bountiesClosedData[Web3.toChecksumAddress(platform["contract"])] = bountiesClosed
    
    json_object = json.dumps(bountiesClosedData, indent=4)
    with open("./bounties/closed.json", "w") as outfile:
        outfile.write(json_object)

def main():
    urlsResponse = requests.get("https://bribe-platform-git-feature-eng-339-vm-add-bsc-stake-capital.vercel.app/platforms/index.json")
    if urlsResponse.status_code != 200:
        return

    config = urlsResponse.json()
    bounties(config)

__name__ == "__main__" and main()

#export PYTHONPATH=script/