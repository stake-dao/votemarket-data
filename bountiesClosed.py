import logging, json
from web3 import Web3
from web3.middleware import geth_poa_middleware

def load_json(name):
    with open("abi/" + name + ".json", "r") as f:
        return json.load(f)
    
def isNullAddress(addr):
    return addr == "0x0000000000000000000000000000000000000000"

def getRpcUrl(chainId):
    if chainId == 1:
        return 'https://eth.drpc.org'
    if chainId == 56:
        return "https://bsc-rpc.publicnode.com"
    
    return 'https://eth.drpc.org'

def bounties(config): 

    platforms = config["platforms"]

    bountiesClosedData = {}

    for platform in platforms:
        platformAbi = load_json("Platform")
        if platform["chainId"] == 56:
            platformAbi = load_json("PlatformBSC")

        w3 = Web3(Web3.HTTPProvider(getRpcUrl(platform["chainId"])))
        if platform["chainId"] != 1:
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)

        if w3.isConnected() == False:
            logging.error("RPC down")
            continue
        platformContract = w3.eth.contract(address=Web3.toChecksumAddress(platform["contract"]), abi=platformAbi)
        nextID = platformContract.functions.nextID().call()

        currentPeriod = 0
        if platform["chainId"] == 56:
            currentPeriod = platformContract.functions.getCurrentEpoch().call()
        else:
            currentPeriod = platformContract.functions.getCurrentPeriod().call()

        bountiesClosed = []
        bountiesClosable = []
        for i in range(nextID):
            print(f"{platform} - {i}")
            # Fetch bounty
            bounty = platformContract.functions.getBounty(i).call()

            # If closed, we mark it as closed and we skip
            manager = bounty[1]
            if platform["chainId"] == 56:
                manager = bounty[2]
                
            if isNullAddress(manager):
                bountiesClosed.append(i)
                continue

            # We have to check if the bounty is closable
            # Check if we have an upgrade in queue
            upgrade = platformContract.functions.upgradeBountyQueue(i).call()
            
            isClosable = False
            if upgrade[0] > 0:
                isClosable = upgrade[3] <= currentPeriod
            else:
                if platform["chainId"] == 56:
                    isClosable = bounty[5] <= currentPeriod
                else:
                    isClosable = bounty[4] <= currentPeriod

            if isClosable:
                bountyClosable = {}
                bountyClosable["id"] = i
                bountyClosable["manager"] = manager
                bountiesClosable.append(bountyClosable)

        bountiesClosedData[Web3.toChecksumAddress(platform["contract"])] = {}
        bountiesClosedData[Web3.toChecksumAddress(platform["contract"])]["bountiesClosed"] = bountiesClosed
        bountiesClosedData[Web3.toChecksumAddress(platform["contract"])]["bountiesClosable"] = bountiesClosable
    
    json_object = json.dumps(bountiesClosedData, indent=4)
    with open("./bounties/closed.json", "w") as outfile:
        outfile.write(json_object)

def main():

    config = {
        "platforms": [
            {
                "contract": "0x000000073D065Fc33a3050C2d0E19C393a5699ba",
                "chainId": 1,
            },
            {
                "contract": "0x0000000895cB182E6f983eb4D8b4E0Aa0B31Ae4c",
                "chainId": 1,
            },
            {
                "contract": "0x00000004E4FB0C3017b543EF66cC8A89F5dE74Ff",
                "chainId": 1,
            },
            {
                "contract": "0x0000000446b28e4c90dbf08ead10f3904eb27606",
                "chainId": 1,
            },
            {
                "contract": "0x000000060e56DEfD94110C1a9497579AD7F5b254",
                "chainId": 1,
            },
            {
                "contract": "0x000000071a273073c824E2a8B0192963e0eEA68b",
                "chainId": 1,
            },
            {
                "contract": "0x000000069feD904D94e72202BDC417b19993e18D",
                "chainId": 1,
            },
            {
                "contract": "0x00000000d0FFb95412346C83F12D0697E4dD2255",
                "chainId": 1,
            },
            {
                "contract": "0x00000007D987c2Ea2e02B48be44EC8F92B8B06e8",
                "chainId": 1,
            },
            {
                "contract": "0x0fD2d686C02D686c65804ff45E4e570386E3595f",
                "chainId": 56,
            },
            {
                "contract": "0x62c5D779f5e56F6BC7578066546527fEE590032c",
                "chainId": 56,
            },
            {
                "contract": "0xa77889DA8fEDC7FD65D37Af60d0744B954E3bAf0",
                "chainId": 56,
            }
        ]
    }
    bounties(config)

__name__ == "__main__" and main()

#export PYTHONPATH=script/