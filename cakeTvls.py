import requests, json

def main():
    res = {}
    f = open("./gauges/cake.json")
    gauges = json.load(f)
    for gauge in gauges["data"] :
        urlsResponse = requests.get("https://farms-api.pancakeswap.com/v3/"+ str(gauge["chainId"]) + "/liquidity/" + gauge["address"])
        if urlsResponse.status_code == 200:
            response = urlsResponse.json()
            res[gauge["address"]] = response["formatted"]


    json_object = json.dumps(res, indent=4)
    with open("./tvls/cake.json", "w") as outfile:
        outfile.write(json_object)

__name__ == "__main__" and main()

#export PYTHONPATH=script/