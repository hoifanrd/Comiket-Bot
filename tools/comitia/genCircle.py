from urllib.parse import unquote
from const import *
import json
import unicodedata
import requests
import time

from bs4 import BeautifulSoup

MAIN_HALL = "e456"
WALL_BLOCKS = ["ね"]

# M in the "init" of the website
MAP_FACTOR = 54
XY_GROUPS = {
    "e456": {
        "e4": [0, 989],
        "e5": [990, 1899],
        "e6": [1900, 3000],
    }
}

def get_circle_list():
    pt = ""
    for c in c1:
        pt += chr(ord(c) - 3)

    pt = unquote(pt)
    return json.loads(pt)


def gen_hall_data(circle_list):
    res = dict()
    for l in circle_list:
        for circle in l:
            
            block = unicodedata.normalize('NFKC', circle[1])
            space_no = circle[2]
            ab = circle[3]
            x = circle[7]
            y = circle[8]
            w = circle[9]
            h = circle[10]

            hall_data = {
                "isLocationLabel": False,
                "locate": [x, y, w, h]
            }

            hall_key = block+space_no
        
            if hall_key not in res:
                res[hall_key] = hall_data

            # Handle ab space
            else:

                if ab == 'a':
                    a_data = hall_data
                    b_data = res[hall_key]
                elif ab == 'b':
                    a_data = res[hall_key]
                    b_data = hall_data

                ab_x_diff = a_data['locate'][0] - b_data['locate'][0]
                ab_y_diff = a_data['locate'][1] - b_data['locate'][1]

                if abs(ab_x_diff) > abs(ab_y_diff):    # Left right ab
                    # a space on right of b space
                    if ab_x_diff > 0:
                        res[hall_key]['dirbase'] = '右'
                        res[hall_key]['direction'] = 4
                        
                        res[hall_key]['locate'][0] = b_data['locate'][0]
                        res[hall_key]['locate'][1] = b_data['locate'][1]
                        res[hall_key]['locate'][2] = a_data['locate'][2] + b_data['locate'][2]
                        res[hall_key]['locate'][3] = b_data['locate'][3]

                    else:
                        res[hall_key]['dirbase'] = '左'
                        res[hall_key]['direction'] = 2
                        
                        res[hall_key]['locate'][0] = a_data['locate'][0]
                        res[hall_key]['locate'][1] = a_data['locate'][1]
                        res[hall_key]['locate'][2] = a_data['locate'][2] + b_data['locate'][2]
                        res[hall_key]['locate'][3] = a_data['locate'][3]

                # Up down ab
                else:
                    # a space on bottom of b space
                    if ab_y_diff > 0:
                        res[hall_key]['dirbase'] = '下'
                        res[hall_key]['direction'] = 3
                        
                        res[hall_key]['locate'][0] = b_data['locate'][0]
                        res[hall_key]['locate'][1] = b_data['locate'][1]
                        res[hall_key]['locate'][2] = b_data['locate'][2]
                        res[hall_key]['locate'][3] = a_data['locate'][3] + b_data['locate'][3]

                    else:
                        res[hall_key]['dirbase'] = '上'
                        res[hall_key]['direction'] = 1
                        
                        res[hall_key]['locate'][0] = a_data['locate'][0]
                        res[hall_key]['locate'][1] = a_data['locate'][1]
                        res[hall_key]['locate'][2] = a_data['locate'][2]
                        res[hall_key]['locate'][3] = a_data['locate'][3] + b_data['locate'][3]
                
    return {MAIN_HALL: res}


# I HAVE NO IDEA WTF I HAVE WRITTEN
# PLEASE DON'T TRY TO REFRACTOR OR UNDERSTAND IT
def normalize_locate(hall_data: dict):
    
    ESP = 2

    loc_map = dict()
    xs = set()
    ys = set()
    for booth, space in hall_data.items():
        loc = space['locate']
        xs.add(loc[0])
        ys.add(loc[1])
        loc_map[(loc[0], loc[1])] = [booth, space]

    xs = list(xs)
    ys = list(ys)

    xs.sort()
    ys.sort()

    loc_keys = list(loc_map.keys())
    loc_keys.sort()

    # Find the starting point except wall blocks
    for loc in loc_keys:
        if loc_map[loc][0][0] in WALL_BLOCKS: continue
        loc_map[loc][1]['new_locate'] = [10, 10]
        break
    
    def spread_loc(skip_walls = True):
        # Spread from the starting point
        for loc in loc_keys:

            if skip_walls and loc_map[loc][0][0] in WALL_BLOCKS:
                continue
            
            # Find closest booth with known new_locate
            # Similar to BFS
            if 'new_locate' not in loc_map[loc][1]:
                closest_booth = None
                for other_loc in loc_keys:
                    if 'new_locate' in loc_map[other_loc][1]:
                        dist = abs(loc[0] - other_loc[0]) + abs(loc[1] - other_loc[1])
                        if closest_booth is None or dist < closest_booth[0]:
                            closest_booth = (dist, loc_map[other_loc])
                
                # print(loc_map[loc][0], 'from', closest_booth[1][0])
                closest_booth = closest_booth[1]
                xx = closest_booth[1]['locate'][0]
                yy = closest_booth[1]['locate'][1]

                loc_map[loc][1]['new_locate'] = [closest_booth[1]['new_locate'][0], closest_booth[1]['new_locate'][1]]
                if abs(xx - loc[0]) > ESP:
                    if xx < loc[0]:
                        loc_map[loc][1]['new_locate'][0] += 2
                    else:
                        loc_map[loc][1]['new_locate'][0] -= 2
                
                if abs(yy - loc[1]) > ESP:
                    if yy < loc[1]:
                        loc_map[loc][1]['new_locate'][1] += 2
                    else:
                        loc_map[loc][1]['new_locate'][1] -= 2

            # Update the locate
            # Find nearby space
            for dx in range(-ESP, ESP+1):
                for dy in range(-ESP, ESP+1):
                    n_loc = (loc[0]+loc_map[loc][1]['locate'][2]+dx, loc[1]+dy)
                    if n_loc in loc_map and 'new_locate' not in loc_map[n_loc][1]:
                        # print(loc_map[loc][0], '->', loc_map[n_loc][0])
                        loc_map[n_loc][1]['new_locate'] = [loc_map[loc][1]['new_locate'][0] + 1, loc_map[loc][1]['new_locate'][1]]
                    
                    n_loc = (loc[0]+dx, loc[1]+loc_map[loc][1]['locate'][3]+dy)
                    if n_loc in loc_map and 'new_locate' not in loc_map[n_loc]:
                        # print(loc_map[loc][0], '->', loc_map[n_loc][0])
                        loc_map[n_loc][1]['new_locate'] = [loc_map[loc][1]['new_locate'][0], loc_map[loc][1]['new_locate'][1] + 1]
    
    # handle non wall blocks
    spread_loc(True)
    # handle wall blocks afterwards
    spread_loc(False)

    # Determine specific hall
    for elem in hall_data.values():
        x = elem['locate'][0]
        for spec_hall, (start, end) in XY_GROUPS[MAIN_HALL].items():
            if start <= x*MAP_FACTOR//100 <= end:
                elem['hall'] = spec_hall
                break


    for elem in hall_data.values():
        elem['locate'] = elem['new_locate']
        del elem['new_locate']



def gen_circle_data(circle_list):

    res = dict()
    for _, l in enumerate(circle_list):
        for circle in l:
            
            circle_id = circle[0]
            block = unicodedata.normalize('NFKC', circle[1])
            space_no = circle[2]
            ab = circle[3]
            circle_name = circle[4]
            author_name = circle[5]

            circle_key = block+space_no+ab
            circle_data = {
                "Author": author_name,
                "Block": block,
                "CircleId": circle_id,
                "Name": circle_name,
                "Space": circle_key
            }

            res[circle_key] = circle_data


    # Get circle details
    session = requests.Session()
    main_page = session.get(
        url="https://comitia-webcatalog.net/catalog",
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36"
        }
    )

    soup = BeautifulSoup(main_page.text, 'html.parser')
    csrf_token = soup.find('meta', attrs={'name': 'csrf-token'})['content']

    num_pages = len(circle_list)
    for page in range(1, num_pages+1):
        print(f"Fetching page {page}/{num_pages}")
        resp = session.post(
            url="https://comitia-webcatalog.net/catalog/load",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Safari/537.36",
                "X-CSRF-Token": csrf_token,
            },
            data={"page": str(page)}
        )
        resp_json = resp.json()
        page_circle_data = json.loads(resp_json[0])
        
        for circle in page_circle_data:
            circle_key = unicodedata.normalize('NFKC', circle['block']) + circle['no'] + circle['ab']
            if circle_key not in res:
                raise Exception(f"Circle {circle_key} not found in circle list")
            
            additional_data = {
                "IsPixivRegistered": bool(circle['url_pi']),
                "PixivUrl": circle['url_pi'] if circle['url_pi'] else '',
                "IsTwitterRegistered": bool(circle['url_tw']),
                "TwitterUrl": circle['url_tw'] if circle['url_tw'] else '',
            }

            res[circle_key].update(additional_data)

        time.sleep(1)       # Be nice to the server

    return {"1": {MAIN_HALL: res}}


def main():
    circle_list = get_circle_list()

    hall_data = gen_hall_data(circle_list)
    normalize_locate(hall_data[MAIN_HALL])

    circle_data = gen_circle_data(circle_list)

    json.dump(
        hall_data,
        open('output/hall_data.json', 'w', encoding='utf-8'),
        ensure_ascii=False,
        indent=4,
        sort_keys=True
    )

    json.dump(
        circle_data,
        open('output/circle_data.json', 'w', encoding='utf-8'),
        ensure_ascii=False,
        indent=4,
        sort_keys=True
    )


if __name__ == "__main__":
    main()


    