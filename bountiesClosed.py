import requests, logging, json
from web3 import Web3

def load_json(name):
    with open("abi/" + name + ".json", "r") as f:
        return json.load(f)
    
def isNullAddress(addr):
    return addr == "0x0000000000000000000000000000000000000000"
    
def bounties(config): 
    w3 = Web3(Web3.HTTPProvider('https://eth.public-rpc.com'))
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
        bountiesClosable = []
        for i in range(nextID):

            # Fetch bounty
            bounty = platformContract.functions.getBounty(i).call()

            # If closed, we mark it as closed and we skip 
            if isNullAddress(bounty[1]):
                bountiesClosed.append(i)
                continue

            # We have to check if the bounty is closable
            # Check if we have an upgrade in queue
            upgrade = platformContract.functions.upgradeBountyQueue(i).call()
            currentPeriod = platformContract.functions.getCurrentPeriod().call()
            isClosable = False
            if upgrade[0] > 0:
                isClosable = upgrade[3] <= currentPeriod
            else:
                isClosable = bounty[4] <= currentPeriod

            if isClosable:
                bountyClosable = {}
                bountyClosable["id"] = i
                bountyClosable["manager"] = bounty[1]
                bountiesClosable.append(bountyClosable)

        bountiesClosedData[Web3.toChecksumAddress(platform["contract"])] = {}
        bountiesClosedData[Web3.toChecksumAddress(platform["contract"])]["bountiesClosed"] = bountiesClosed
        bountiesClosedData[Web3.toChecksumAddress(platform["contract"])]["bountiesClosable"] = bountiesClosable
    
    json_object = json.dumps(bountiesClosedData, indent=4)
    with open("./bounties/closed.json", "w") as outfile:
        outfile.write(json_object)

def main():
    urlsResponse = requests.get("https://votemarket.stakedao.org/platforms/index.json")
    if urlsResponse.status_code != 200:
        return

    config = urlsResponse.json()
    bounties(config)

__name__ == "__main__" and main()

#export PYTHONPATH=script/