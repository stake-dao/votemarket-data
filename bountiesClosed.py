import requests, logging, json
from web3 import Web3

def load_json(name):
    with open("abi/" + name + ".json", "r") as f:
        return json.load(f)
    
def isNullAddress(addr):
    return addr == "0x0000000000000000000000000000000000000000"
    
def bounties(config): 
    w3 = Web3(Web3.HTTPProvider('https://rpc.ankr.com/eth'))
    if w3.isConnected() == False:
        logging.error("RPC down")
        return

    platforms = config["platforms"]
    platformAbi = load_json("Platform")

    bountiesClosedData = {}

    for platform in platforms:
        platformContract = w3.eth.contract(address=Web3.toChecksumAddress(platform["contract"]), abi=platformAbi)
        nextID = platformContract.functions.nextID().call()
        currentPeriod = platformContract.functions.getCurrentPeriod().call()

        bountiesClosed = []
        bountiesClosable = []
        for i in range(nextID):
            print(f"{platform} - {i}")
            # Fetch bounty
            bounty = platformContract.functions.getBounty(i).call()

            # If closed, we mark it as closed and we skip 
            if isNullAddress(bounty[1]):
                bountiesClosed.append(i)
                continue

            # We have to check if the bounty is closable
            # Check if we have an upgrade in queue
            upgrade = platformContract.functions.upgradeBountyQueue(i).call()
            
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

    config = {
        "platforms": [
            {
                "contract": "0x000000073D065Fc33a3050C2d0E19C393a5699ba",
                "chainId": 1,
                "correspondingVeToken": "0xD533a949740bb3306d119CC777fa900bA034cd52"
            },
            {
                "contract": "0x0000000895cB182E6f983eb4D8b4E0Aa0B31Ae4c",
                "chainId": 1,
                "correspondingVeToken": "0xD533a949740bb3306d119CC777fa900bA034cd52"
            },
            {
                "contract": "0x00000004E4FB0C3017b543EF66cC8A89F5dE74Ff",
                "chainId": 1,
                "correspondingVeToken": "0x31429d1856ad1377a8a0079410b297e1a9e214c2"
            },
            {
                "contract": "0x0000000446b28e4c90dbf08ead10f3904eb27606",
                "chainId": 1,
                "correspondingVeToken": "0x5c6ee304399dbdb9c8ef030ab642b10820db8f56"
            },
            {
                "contract": "0x000000060e56DEfD94110C1a9497579AD7F5b254",
                "chainId": 1,
                "correspondingVeToken": "0x3432B6A60D23Ca0dFCa7761B7ab56459D9C964D0"
            },
            {
                "contract": "0x000000071a273073c824E2a8B0192963e0eEA68b",
                "chainId": 1,
                "correspondingVeToken": "0x9232a548dd9e81bac65500b5e0d918f8ba93675c"
            },
            {
                "contract": "0x000000069feD904D94e72202BDC417b19993e18D",
                "chainId": 1,
                "correspondingVeToken": "0x73968b9a57c6E53d41345FD57a6E6ae27d6CDB2F"
            },
            {
                "contract": "0x00000000d0FFb95412346C83F12D0697E4dD2255",
                "chainId": 1,
                "correspondingVeToken": "0x97effb790f2fbb701d88f89db4521348a2b77be8"
            },
            {
                "contract": "0x00000007D987c2Ea2e02B48be44EC8F92B8B06e8",
                "chainId": 1,
                "correspondingVeToken": "0x365AccFCa291e7D3914637ABf1F7635dB165Bb09"
            }
        ]
    }
    bounties(config)

__name__ == "__main__" and main()

#export PYTHONPATH=script/