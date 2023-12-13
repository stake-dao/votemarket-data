import requests, json

def main():
    urlsResponse = requests.get("https://pancakeswap.finance/api/gauges/getAllGauges?inCap=true&testnet=")
    if urlsResponse.status_code != 200:
        return

    config = urlsResponse.json()
    json_object = json.dumps(config, indent=4)
    with open("./gauges/cake.json", "w") as outfile:
        outfile.write(json_object)

__name__ == "__main__" and main()

#export PYTHONPATH=script/