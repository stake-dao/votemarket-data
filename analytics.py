import requests, logging, os, time, json

def analytics(config): 
    now = int(time.time())

    protocols = config["protocols"]
    for protocol in protocols:
        print("https://votemarket.stakedao.org/api/analytics/global?protocolKey="+protocol["key"])
        analyticsResponse = requests.get(url="https://votemarket.stakedao.org/api/analytics/global?protocolKey="+protocol["key"], timeout=30*60)
        if analyticsResponse.status_code != 200:
            continue

        analytics = analyticsResponse.json()
        if len(analytics) == 0:
            continue
        
        analyticsObj = {
            "lastUpdate": now,
            "analytics": analytics
        }
        
        json_object = json.dumps(analyticsObj, indent=4)
        with open("./analytics/"+protocol["key"]+".json", "w") as outfile:
            outfile.write(json_object)

def main():
    # only once per day
    f = open('./analytics/config.json')
 
    config = json.load(f)
    now = int(time.time())

    if config["latestRun"] + (60 * 60 * 24) - 1 > now:
        return
    
    config["latestRun"] = now
    json_object = json.dumps(config, indent=4)
    with open("./analytics/config.json", "w") as outfile:
        outfile.write(json_object)

    urlsResponse = requests.get("https://votemarket.stakedao.org/api/cache")
    if urlsResponse.status_code != 200:
        return

    config = urlsResponse.json()
    analytics(config)

__name__ == "__main__" and main()

#export PYTHONPATH=script/