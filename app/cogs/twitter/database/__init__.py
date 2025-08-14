import requests
import os
import json

db_folder = os.environ.get("DB_FOLDER") 
# 檢查環境變數 DB_FOLDER 是否設置
if os.environ.get("DB_FOLDER") is None:
    raise ValueError("DB_FOLDER environment variable is not set.")

JSON_PATHS = [
    os.path.join(db_folder, 'circle_day1.json'),
    os.path.join(db_folder, 'circle_day2.json')
]


def find_circle_by_row_booth(row: str, booth: str, day):
    if not row or not booth:
        return None
    
    # Remove any trailing 'ab' from booth and only search for 'a'
    removedTrail = False
    if booth[-2:] == "ab":
        booth = booth[:-1]
        removedTrail = True

    day_idx = day - 1
    filename = JSON_PATHS[day_idx]

    with open(filename, 'r', encoding='utf-8') as file:
        data = json.load(file)
    
    for item in data:
        loc = item.get('loc', '')
        if not loc: continue

        cur_row, cur_booth = loc[2], loc[3:]
        if cur_row == row and cur_booth == booth:
            form_data = {
                'circle_name': item['kan'],
                'author_name': item.get('url', [''])[0],
                'row': item['loc'][2],
                'booth': (item['loc'][3:] + "b") if removedTrail else item['loc'][3:],
                'x': item.get('x', '')
            }
            return form_data
    
    return None



def find_circle_by_tweeter_name(username: str, day):
    day_idx = day - 1
    filename = JSON_PATHS[day_idx]

    with open(filename, 'r', encoding='utf-8') as file:
        data = json.load(file)
    
    res = None
    for idx, item in enumerate(data):
        if ('url' in item) and ('https://twitter.com/' + username in item['url'] or \
            'https://x.com/' + username in item['url']):
            
            res = item

            # 如果是ab，則檢查下一個項目是否為b
            if idx < len(data) - 1:
                next_item = data[idx + 1]
                if ('url' in next_item) and ('https://twitter.com/' + username in next_item['url'] or \
                'https://x.com/' + username in next_item['url']) and res.get('loc', '')[-1] == "a":
                    res['loc'] += "b"
            
            break
    
    
    # 如果當天找到，則檢查下一天都有沒有
    filename = JSON_PATHS[(day_idx + 1) % 2]
    with open(filename, 'r', encoding='utf-8') as file:
        data = json.load(file)
    
    for idx, item in enumerate(data):
        if ('url' in item) and ('https://twitter.com/' + username in item['url'] or \
            'https://x.com/' + username in item['url']) and res is not None:
            res['has_two_days'] = True
            break
    else:
        if res is not None:
            res['has_two_days'] = False
        
    form_data = {
        'circle_name': res['kan'],
        'author_name': res.get('url', [''])[0],
        'row': res['loc'][2],
        'booth': res['loc'][3:],
        'has_two_days': res['has_two_days']
    }

    return form_data

        

def init_circle_data():

    day1_filename = JSON_PATHS[0]
    if not os.path.exists(day1_filename):
        with open(day1_filename, 'w', encoding='utf-8') as file:
            r = requests.get('https://ocv.me/bp/106/lkrxy1.json')
            res = r.json()
            json.dump(res, file, ensure_ascii=False, indent=4)
    
    day2_filename = JSON_PATHS[1]
    if not os.path.exists(day2_filename):
        with open(day2_filename, 'w', encoding='utf-8') as file:
            r = requests.get('https://ocv.me/bp/106/lkrxy2.json')
            res = r.json()
            json.dump(res, file, ensure_ascii=False, indent=4)

    