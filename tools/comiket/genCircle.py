import requests
import os
import json
import time
from tqdm import tqdm

from cookie import COOKIE

reqsession = requests.Session()

XY_GROUPS = {
    "e456": {
        "e4": [0, 370],
        "e5": [390, 760],
        "e6": [780, 2000],
    },
    "e7": {
        "e7": [0, 2000],
    },
    "w12": {
        "w1": [0, 490],
        "w2": [500, 2000],
    },
    "s12": {
        "s1": [0, 310],
        "s2": [320, 1000],
    },
}


def getData(url, filepath, post=False):
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as file:
            return json.load(file)

    print(f"Fetching data from {url} and saving to {filepath}")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
        "Cookie": COOKIE,
        "sec-ch-ua": '"Not;A=Brand";v="99", "Google Chrome";v="139", "Chromium";v="139"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Accept": "application/json, text/javascript, */*; q=0.01",
        "Accept-Encoding": "gzip, deflate, br",
        "Accept-Language": "zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "https://webcatalog.circle.ms/",
        "Origin": "https://webcatalog.circle.ms",
        "upgrade-insecure-requests": "1",
    }
    response = reqsession.get(url, headers=headers) if not post else reqsession.post(url, headers=headers)
    res = response.json()

    time.sleep(0.1)
    with open(filepath, 'w', encoding='utf-8') as file:
        json.dump(res, file, ensure_ascii=False, indent=4)
    
    return res


def main():

    genre_data = getData('https://webcatalog.circle.ms/Map/GetGenrePosition2', 'data/genre_data.json')
    
    halls = set(elem['hall'] for elem in genre_data)
    hall_datas = dict()
    for hall in halls:
        hall_data = getData(f'https://webcatalog.circle.ms/Map/GetMapDataFromExcel?hall={hall}', f'data/hall_{hall}_data.json')
        hall_data = hall_data['mapcsv']
        
        # Parse hall data to a more structured format
        spaced_hall_data = dict()
        for elem in hall_data:
            space = elem['space']

            for spec_hall, (start, end) in XY_GROUPS[hall].items():
                if start <= elem['locate'][0] * 10 <= end:
                    elem['hall'] = spec_hall
                    break

            del elem['space']
            spaced_hall_data[space] = elem
            
        hall_datas[hall] = spaced_hall_data
    


    day_halls = set((int(elem['day'][-1]), elem['hall']) for elem in genre_data)
    day_hall_booth_datas = dict()
    for day_hall in day_halls:
        day, hall = day_hall
        day_hall_booth_data = getData(f'https://webcatalog.circle.ms/Map/GetMapping2?day=Day{day}&hall={hall}', f'data/booth_{day}_{hall}_data.json')

        if day not in day_hall_booth_datas:
            day_hall_booth_datas[day] = dict()
        
        if hall not in day_hall_booth_datas[day]:
            day_hall_booth_datas[day][hall] = dict()

        day_hall_booth_datas[day][hall] = day_hall_booth_data


    # Merge booth data for booths that share the same circle
    for _, hall_booth_datas in day_hall_booth_datas.items():
        for _, booth_datas in hall_booth_datas.items():
            booths_a = [booth for booth in booth_datas.keys() if booth.endswith('a')]
            for booth_a in booths_a:
                booth_b = booth_a[:-1] + 'b'
                if booth_datas[booth_a]['id'] == booth_datas[booth_b]['id']:
                    booth_ab = booth_a[:-1] + 'ab'
                    booth_datas[booth_ab] = booth_datas[booth_a]
                    del booth_datas[booth_a]
                    del booth_datas[booth_b]
    

    booth_json_datas = dict()
    for day, hall_booth_datas in day_hall_booth_datas.items():
        for hall, booth_datas in hall_booth_datas.items():
            print(f"Working on Day {day}, Hall {hall}:")
            if not os.path.exists(f'data/circles/{day}/{hall}'):
                os.makedirs(f'data/circles/{day}/{hall}', exist_ok=True)
            
            for booth, booth_data in tqdm(booth_datas.items()):
                wid = booth_data['wid']
                booth_json = getData(f'https://webcatalog.circle.ms/Circle/{wid}/DetailJson', f'data/circles/{day}/{hall}/{wid}.json', post=True)
                booth_json['Space'] = booth
                booth_json_datas[wid] = booth_json


    # Put all booth data into a single file
    for day, hall_booth_datas in day_hall_booth_datas.items():
        for hall, booth_datas in hall_booth_datas.items():
            for booth, booth_data in booth_datas.items():
                wid = booth_data['wid']
                booth_json = booth_json_datas[wid]
                booth_datas[booth] = booth_json

    json.dump(
        day_hall_booth_datas,
        open('output/circle_data.json', 'w', encoding='utf-8'),
        ensure_ascii=False,
        indent=4,
        sort_keys=True
    )

    json.dump(
        hall_datas,
        open('output/hall_data.json', 'w', encoding='utf-8'),
        ensure_ascii=False,
        indent=4,
        sort_keys=True
    )


if __name__ == "__main__":
    main()