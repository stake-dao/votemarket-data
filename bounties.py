import requests, logging, os, time, json

def bounties(config): 
    now = int(time.time())

    urlsData = config["bribesUrls"]
    for urlData in urlsData:
        bountiesResponse = requests.get(url="https://votemarket.stakedao.org"+urlData["url"], timeout=60)
        if bountiesResponse.status_code != 200:
            return

        bounties = bountiesResponse.json()
        if urlData["url"] == 'stake-dao':
            if len(bounties) == 0:
                continue
        
        bountiesObj = {
            "lastUpdate": now,
            "bounties": bounties
        }

        json_object = json.dumps(bountiesObj, indent=4)
        with open("./bounties/"+urlData["name"]+".json", "w") as outfile:
            outfile.write(json_object)

def main():
    urlsResponse = requests.get("https://votemarket.stakedao.org/api/cache")
    if urlsResponse.status_code != 200:
        return

    config = urlsResponse.json()
    bounties(config)

__name__ == "__main__" and main()

#export PYTHONPATH=script/