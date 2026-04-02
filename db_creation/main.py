import requests

APP_ID = "1687950"
url = f"https://store.steampowered.com/appreviews/{APP_ID}"

params = {
    "json": 1,
    "num_per_page": 100,   # max per request
    "language": "english",
    "filter": "recent",    # or "all"
}

all_reviews = []
cursor = "*"

while len(all_reviews) < 500:
    params["cursor"] = cursor
    res = requests.get(url, params=params).json()
    
    reviews = res.get("reviews", [])

    if not reviews:
        break

    all_reviews.extend(reviews)
    cursor = res.get("cursor")
    

# trim to exactly 200
all_reviews = [r for r in all_reviews if not r['refunded']]
all_reviews = [r for r in all_reviews if len(r['review'].split())>= 50]
all_reviews.sort(key = lambda r:float(r['weighted_vote_score']), reverse =  True)    

for count, review in enumerate(all_reviews): 
    print(review['review'])
    if count == 4 :
        break