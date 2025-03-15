import requests, json
from urllib.parse import urlencode

# fmt: off
QUERY_PARAMS = {
    "protocols": "v3",
    "chains": [
        "bsc", "ethereum", "base", "arbitrum",
        "zksync", "polygon-zkevm", "linea", "opbnb",
    ],
}
# fmt: on


def main():
    url = f"https://explorer.pancakeswap.com/api/cached/pools/farming?{urlencode(QUERY_PARAMS, doseq=True)}"
    response = requests.get(url)
    pools = response.json()

    res = {}

    for pool in pools:
        res[pool["id"].lower()] = {
            "token0": pool["tvlToken0"],
            "token1": pool["tvlToken1"],
        }

    json_object = json.dumps(res)
    with open("./tvls/cake.json", "w") as outfile:
        outfile.write(json_object)


__name__ == "__main__" and main()

# export PYTHONPATH=script/
