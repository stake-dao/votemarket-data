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
    fetch("https://pancakeswap.finance/api/gauges/getAllGauges?inCap=true&testnet=", "cake.json")

def curve():
    fetch("https://api.curve.fi/api/getAllGauges", "curve.json")

def frax():
    fetch("https://api.frax.finance/v1/gauge/voter-info/0x0000000000000000000000000000000000000000", "frax.json")

def fxn():
    fetch("https://api.aladdin.club/api1/get_fx_gauge_list", "fxs.json")

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
                pools = [
                    {"name": pool["symbol"], "address": pool["gauge"]["address"], "chain": pool["chain"]}
                    for pool in data["data"]["veBalGetVotingList"]
                ]
                writeGauges(pools, "balancer.json")
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
            print(data)
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


__name__ == "__main__" and main()

#export PYTHONPATH=script/