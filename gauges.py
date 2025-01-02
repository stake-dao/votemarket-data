import requests, json

def writeGauges(gauges, file):
    json_object = json.dumps(gauges, indent=4)
    with open("./gauges/"+file, "w") as outfile:
        outfile.write(json_object)

def fetch(url, file):
    urlsResponse = requests.get(url)
    if urlsResponse.status_code != 200:
        return

    config = urlsResponse.json()
    writeGauges(config, file)

def cake():
    urlsResponse = requests.get("https://pancakeswap.finance/api/gauges/getAllGauges?inCap=true&testnet=")
    if urlsResponse.status_code != 200:
        return
    urlsResponse = urlsResponse.json()
    
    if "data" not in urlsResponse:
        return
    
    data = urlsResponse["data"]

    # Fetch all chain id for position manager
    chain_ids = {}
    for gaugeData in data:
        if "chainId" in gaugeData:
            chain_ids[gaugeData["chainId"]] = True

    for chain_id in chain_ids:
        response = requests.get(f"https://configs.pancakeswap.com/api/data/cached/positionManagers?chainId={chain_id}")
        if response.status_code != 200:
            continue
        response = response.json()
        
        for positionManager in response:
            if "idByManager" not in positionManager or "name" not in positionManager or "vaultAddress" not in positionManager:
                continue
            vault_address = positionManager["vaultAddress"]
            id_by_manager = positionManager["idByManager"]
            name = positionManager["name"]

            for gaugeData in data:
                if "address" not in gaugeData:
                    continue

                if gaugeData["address"].lower() == vault_address.lower():
                    gaugeData["pairName"] += f" {name}#{id_by_manager}"
                    break

    writeGauges(urlsResponse, "cake.json")

def curve():
    fetch("https://api.curve.fi/api/getAllGauges", "curve.json")

def frax():
    fetch("https://api.frax.finance/v1/gauge/voter-info/0x0000000000000000000000000000000000000000", "frax.json")

def fxn():
    fetch("https://api.aladdin.club/api1/get_fx_gauge_list", "fxn.json")

def balancer():
    try:
        response = requests.post(
            "https://api-v3.balancer.fi/",
            json={
                "query": """
            query {
              veBalGetVotingList {
                gauge {
                    address
                    isKilled
                }
                symbol
                chain
              }
            }
            """
            },
        )

        if response.status_code == 200:
            data = response.json()
            if data and "data" in data and "veBalGetVotingList" in data["data"]:
                writeGauges(data["data"]["veBalGetVotingList"], "balancer.json")
            else:
                print(
                    "Failed to fetch Balancer pools: API responded with success: false"
                )
        else:
            print(
                f"Failed to fetch Balancer pools: HTTP status code {response.status_code}"
            )
    except Exception as e:
        print(f"Error fetching Balancer pools: {e}")

def lit():
    try:
        response = requests.post(
            "https://api.thegraph.com/subgraphs/name/bunniapp/bunni-mainnet",
            json={
                "query": """
                query  {
                    pools(first: 1000) {
                        bunniTokens{
                            name
                            gauge {
                                address
                            }
                        }
                    }
                }
            """
            },
        )

        if response.status_code == 200:
            data = response.json()
            if data and "data" in data and "pools" in data["data"] :
                writeGauges(data["data"]["pools"], "lit.json")
            else:
                print(
                    "Failed to fetch Lit pools: API responded with success: false"
                )
        else:
            print(
                f"Failed to fetch Lit pools: HTTP status code {response.status_code}"
            )
    except Exception as e:
        print(f"Error fetching Balancer pools: {e}")

def main():
    cake()
    balancer()
    curve()
    frax()
    fxn()
    lit()
    fxn()


__name__ == "__main__" and main()

#export PYTHONPATH=script/