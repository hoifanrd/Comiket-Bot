import os
import requests

API_URL = "https://api.twitterapi.io/twitter/tweets"
API_KEY = os.environ.get("TWITTER_API_KEY")

def get_twitter_details(url):
    
    tweet_id = url.split('/')[-1].split('?')[0]

    querystring = {"tweet_ids": tweet_id}
    headers = {"X-API-Key": API_KEY}
    response = requests.get(API_URL, headers=headers, params=querystring)

    if response.status_code != 200:
        raise Exception(f"Error fetching tweet details: {response.status_code} {url}")

    res_json = response.json()['tweets'][0]
    if res_json['type'] != 'tweet':
        raise Exception(f"Invalid tweet URL: {url}")

    author_name = res_json['author']['userName']
    author_title = res_json['author']['name']
    tweet_content = res_json['text']

    media_links = []

    extend = res_json['extendedEntities']
    media = extend.get('media', [])
    for m in media:
        if m['type'] == 'photo':
            media_links.append(m['media_url_https'])

    return author_name, author_title, tweet_content, media_links

