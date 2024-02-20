import requests, logging, os, time, json
from web3 import Web3

MAINNET_URL = 'https://eth.public-rpc.com'
BSC_URL = 'https://rpc.ankr.com/bsc'
FXS_GAUGE_CONTROLLER = "0x3669C421b77340B2979d1A00a792CC2ee0FcE737"
WEEK = 604800

def getRpcUrl(chainId):
    if chainId == 1:
        return MAINNET_URL
    if chainId == 56:
        return BSC_URL
    return MAINNET_URL

def load_json(name):
    with open(name + ".json", "r") as f:
        return json.load(f)
    
def isNullAddress(addr):
    return addr == "0x0000000000000000000000000000000000000000"

def isBountyClosed(bounties, bountyContractAddress, i):
    for contractAddress in bounties:
        if contractAddress.lower() != bountyContractAddress.lower():
            continue

        bountiesClosed = bounties[contractAddress]["bountiesClosed"]
        for bountiesClosedIndex in bountiesClosed:
            if bountiesClosedIndex == i:
                return True
            
        bountiesClosed = bounties[contractAddress]["bountiesClosable"]
        for bountiesClosedObj in bountiesClosed:
            if bountiesClosedObj["id"] == i:
                return True
            
        return False
    return False

def getTokenPrice(tokenAddress, chainId):
    try:
        prefix = ""
        if chainId == 1:
            prefix = "ethereum:"
        elif chainId == 56:
            prefix = "bsc:"
        prefix += tokenAddress
    
        response = requests.get("https://coins.llama.fi/prices/current/" + prefix)
        if response.status_code != 200:
            return 0

        coins = response.json()
        return coins["coins"][prefix]["price"]
    except:
        return 0


def bounties(config): 

    platforms = config["platforms"]

    platformAbi = load_json("abi/Platform")
    platformBSCAbi = load_json("abi/PlatformBSC")
    erc20Abi = load_json("abi/ERC20")
    bountiesData = load_json("bounties/closed")
    gaugeControllerAbi = load_json("abi/GaugeController")
    gaugeControllerPancakeAbi = load_json("abi/CakeGaugeController")
    
    tokensData = {}
    tokenPricesData = {}
    now = int(time.time())
    bounties = {}

    for platform in platforms:

        bountyContractAddress = platform["contract"]
        bounties[bountyContractAddress] = []

        chainId = platform["chainId"]
        correspondingVeToken = platform["correspondingVeToken"]

        w3 = Web3(Web3.HTTPProvider(getRpcUrl(chainId)))
        if w3.isConnected() == False:
            logging.error("RPC down")
            return
        
        abi = None
        gcAbi = None

        if chainId == 1:
            abi = platformAbi
            gcAbi = gaugeControllerAbi
        elif chainId == 56:
            abi = platformBSCAbi
            gcAbi = gaugeControllerPancakeAbi

        # Fetch platform configs
        platformContract = w3.eth.contract(address=Web3.toChecksumAddress(bountyContractAddress), abi=abi)
        
        nextID = platformContract.functions.nextID().call()
        currentPeriod = platformContract.functions.getCurrentPeriod().call()
        fee = platformContract.functions.fee().call()
        fee = fee / 10**18

        # Fetch bounties
        for i in range(nextID):
            if isBountyClosed(bountiesData, bountyContractAddress, i):
                continue

            bounty = platformContract.functions.bounties(i).call()
            upgradableBounty = platformContract.functions.getUpgradedBountyQueued(i).call()
            amountClaimed = platformContract.functions.amountClaimed(i).call()
            activePeriod = platformContract.functions.activePeriod(i).call()
            blacklistedAddresses = platformContract.functions.getBlacklistedAddressesPerBounty(i).call()

            gauge = bounty.pop(0)

            bountyChainId = chainId
            if chainId == 56:
                bountyChainId = bounty.pop(0)

            manager = bounty.pop(0)
            rewardToken = bounty.pop(0)
            numberOfPeriods = bounty.pop(0)
            endTimestamp = bounty.pop(0)
            maxRewardPerVote = bounty.pop(0)
            totalRewardAmount = bounty.pop(0)

            if upgradableBounty[0] > 0:
                numberOfPeriods = upgradableBounty[0]
                totalRewardAmount = upgradableBounty[1]
                maxRewardPerVote = upgradableBounty[2]
                endTimestamp = upgradableBounty[3]

            # Token reward data
            rewardTokenSymbol = ""
            rewardTokenDecimals = -1

            if (rewardToken in tokensData) == False:
                rewardTokenContract = w3.eth.contract(address=Web3.toChecksumAddress(rewardToken), abi=erc20Abi)
                rewardTokenSymbol = rewardTokenContract.functions.symbol().call()
                rewardTokenDecimals = rewardTokenContract.functions.decimals().call()
                tokensData[rewardToken] = [rewardTokenSymbol, rewardTokenDecimals]
            else:
                rewardTokenSymbol = tokensData[rewardToken][0]
                rewardTokenDecimals = tokensData[rewardToken][1]

            maxRewardPerVote /= 10**rewardTokenDecimals

            bribePeriodLeft = 0
            if endTimestamp > currentPeriod:
                bribePeriodLeft = (endTimestamp - currentPeriod) / WEEK

            activePeriodRewardPerPeriod = activePeriod[2]

            gaugeController = platformContract.functions.gaugeController().call()
            gaugeControllerContract = w3.eth.contract(address=Web3.toChecksumAddress(gaugeController), abi=gcAbi)
            
            gaugeWeight = None
            if chainId == 1:
                gaugeWeight = gaugeControllerContract.functions.get_gauge_weight(gauge).call()
            elif chainId == 56:
                gaugeWeight = 0#gaugeControllerContract.functions.getGaugeWeight(gauge).call()

            for blacklistedAddress in blacklistedAddresses:
                if chainId == 1:
                    w = gaugeControllerContract.functions.vote_user_slopes(blacklistedAddress, gauge).call()
                    veVoted = w[0] * (w[2] - (currentPeriod + WEEK))
                    gaugeWeight -= veVoted
                elif chainId == 56:
                    # gaugeWeight = gaugeControllerContract.functions.voteUserSlopes(blacklistedAddress).call()
                    # TODO
                    gaugeWeight -= 0

            gaugeWeight = gaugeWeight / 10**18
            
            # Round duration in week
            roundDuration = 1
            if chainId == 56:
                roundDuration = 2

            remainingWeeks = 0
            totalRewardPerPeriod = 0

            if upgradableBounty[0] > 0:
                timeLeft = endTimestamp - currentPeriod
                if timeLeft < 0:
                    timeLeft = 0

                remainingWeeks = timeLeft / WEEK
                remainingWeeksForTotalReward = timeLeft / (WEEK * roundDuration)
                if remainingWeeksForTotalReward - 1 > 0:
                    totalRewardPerPeriod = (totalRewardAmount - amountClaimed) / (remainingWeeksForTotalReward - 1)
                else:
                    totalRewardPerPeriod = (totalRewardAmount - amountClaimed)
            else:
                totalRewardPerPeriod = activePeriodRewardPerPeriod
                remainingWeeks = bribePeriodLeft

            # Token prices
            tokenRewardPrice = 0
            if (rewardToken in tokenPricesData) == False:
                tokenRewardPrice = getTokenPrice(rewardToken, chainId)
                tokenPricesData[rewardToken] = tokenRewardPrice
            else:
                tokenRewardPrice = tokenPricesData[rewardToken]

            veTokenPrice = 0
            if (correspondingVeToken in tokenPricesData) == False:
                veTokenPrice = getTokenPrice(correspondingVeToken, chainId)
                tokenPricesData[correspondingVeToken] = veTokenPrice
            else:
                veTokenPrice = tokenPricesData[correspondingVeToken]

            realRemainingWeeks = remainingWeeks - 1
            if chainId == 56 and now > (endTimestamp - roundDuration * WEEK):
                realRemainingWeeks = 0

            isEnded = realRemainingWeeks <= 0

            # Bounty data
            rewardsAvailable = totalRewardPerPeriod / 10**rewardTokenDecimals
            rewardsAvailableUSD = rewardsAvailable * tokenRewardPrice
            maxRewardPerVoteUSD = maxRewardPerVote * tokenRewardPrice

            if isEnded:
                rewardsAvailable = 0
                rewardsAvailableUSD = 0

            tokenPerVoteValue = rewardsAvailable
            if gaugeWeight > 0:
                tokenPerVoteValue /= gaugeWeight

            # Minus fees
            tokenPerVoteValue *= 1-fee
            maxRewardPerVoteUSD *= 1-fee

            # Calculate agin with correct value
            rewardPerVoteValue = min(tokenRewardPrice * tokenPerVoteValue, maxRewardPerVoteUSD)
            tokenPerVoteValue = 0
            if tokenRewardPrice > 0:
                tokenPerVoteValue = rewardPerVoteValue / tokenRewardPrice
            
            apr = 0
            if isEnded == False:
                veMultiplier = 1
                if gaugeController.lower() == FXS_GAUGE_CONTROLLER.lower():
                    veMultiplier = 4
                ratio = 0
                if veTokenPrice > 0:
                    ratio = min(rewardPerVoteValue * 100 / veTokenPrice, maxRewardPerVoteUSD * 100 / veTokenPrice)
                apr = (ratio * (52 / roundDuration) / 100) * veMultiplier

            closableAt = endTimestamp
            endClaimDate = endTimestamp - (roundDuration * WEEK)
            startClaimDate = endTimestamp - (roundDuration * numberOfPeriods * WEEK)
            start = endTimestamp - (roundDuration * numberOfPeriods * WEEK) - (roundDuration * WEEK)
            end = endTimestamp - (roundDuration * 2 * WEEK)
            
            bounty = {
                "id": i,
                "manager": manager,
                "bountyChainId": bountyChainId,
                "isEnded": isEnded,
                "start": start,
                "end": end,
                "startClaimDate": startClaimDate,
                "endClaimDate": endClaimDate,
                "closableAt": closableAt,
                "apr": apr,
                "tokenPerVoteValue": tokenPerVoteValue,
                "tokenPerVoteValueUSD": rewardPerVoteValue,
                "rewardsAvailable": rewardsAvailable,
                "rewardsAvailableUSD": rewardsAvailableUSD,
                "maxRewardPerVote": maxRewardPerVote,
                "maxRewardPerVoteUSD": maxRewardPerVoteUSD,
                "totalVotes": gaugeWeight
            }
            bounties[bountyContractAddress].append(bounty)
    
    json_object = json.dumps(bounties, indent=4)
    with open("./bounties/votemarket.json", "w") as outfile:
        outfile.write(json_object)
            
def main():
    urlsResponse = requests.get("https://votemarket-git-feature-eng-421-vesdt-votemarket-stake-dao.vercel.app/platforms/index.json")
    if urlsResponse.status_code != 200:
        return

    config = urlsResponse.json()
    bounties(config)

__name__ == "__main__" and main()

#export PYTHONPATH=script/