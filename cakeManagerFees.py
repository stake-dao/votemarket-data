import requests, json

def main():
    urlsResponse = requests.get("https://vault.pancakeswap.com/api/statistics?chainId=56&item=feeAvg")
    if urlsResponse.status_code == 200:
        response = urlsResponse.json()
        json_object = json.dumps(response, indent=4)
        with open("./tvls/pancakeManagersFees.json", "w") as outfile:
            outfile.write(json_object)

__name__ == "__main__" and main()