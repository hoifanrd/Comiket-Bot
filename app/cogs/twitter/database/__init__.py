import os
import json
import cogs.twitter.utils as utils

data_folder = os.environ.get("DATA_FOLDER")
curr_event = os.environ.get("CURR_EVENT")
# 檢查環境變數 DATA_FOLDER 是否設置
if data_folder is None:
    raise ValueError("DATA_FOLDER environment variable is not set.")

if curr_event is None:
    raise ValueError("CURR_EVENT environment variable is not set.")

CIRCLE_DATA_PATH = os.path.join(data_folder, curr_event, "circle_data.json")
with open(CIRCLE_DATA_PATH, 'r', encoding='utf-8') as file:
    CIRCLE_DATA = json.load(file)

HALL_DATA_PATH = os.path.join(data_folder, curr_event, "hall_data.json")
with open(HALL_DATA_PATH, 'r', encoding='utf-8') as file:
    HALL_DATA = json.load(file)


def preprocess_data():
    hash_map = {}
    for hall, booth_items in HALL_DATA.items():
        hash_map[hall] = {}
        for booth, booth_data in booth_items.items():
            # If isLocationLabel is True, then skip this "space"
            if booth_data['isLocationLabel']: continue

            location = (booth_data['locate'][0], booth_data['locate'][1])
            hash_map[hall][location] = (booth, booth_data)
            booth_data['isExteriorSpace'] = False         # 外島


    for hall, loc_booths in hash_map.items():

        # Store min&max of x/y in all row/col to find 外島
        exterior_x = dict()
        exterior_y = dict()

        for (x, y), (booth, booth_data) in loc_booths.items():
            
            # 下右上左
            have_adj_booths = [False] * 4

            for i, (dx, dy) in enumerate([(0, 1), (1, 0), (0, -1), (-1, 0)]):
                if (x + dx, y + dy) in loc_booths:
                    have_adj_booths[i] = True
            
            num_of_adj = sum(have_adj_booths)

            # If have 0-1 adjacent booths, then it's 壁攤
            if num_of_adj <= 1:
                booth_data['space_cat'] = '壁攤'
            
            # If have 2 adjacent booths, then it's 壁攤 or 島頭
            elif num_of_adj == 2:
                if have_adj_booths[0] and have_adj_booths[2]:
                    booth_data['space_cat'] = '壁攤'
                elif have_adj_booths[1] and have_adj_booths[3]:
                    booth_data['space_cat'] = '壁攤'
                else:
                    booth_data['space_cat'] = '島頭'

            # If have 3 adjacent booths, then it's 島攤
            elif num_of_adj == 3:
                booth_data['space_cat'] = '島攤'
            else:
                booth_data['space_cat'] = '未知'

            
            # Handle 外島
            if booth_data['space_cat'] != '壁攤':
                if x not in exterior_x:
                    exterior_x[x] = [float('inf'), float('-inf')]
                if y not in exterior_y:
                    exterior_y[y] = [float('inf'), float('-inf')]

                exterior_x[x][0] = min(exterior_x[x][0], y)
                exterior_x[x][1] = max(exterior_x[x][1], y)
                exterior_y[y][0] = min(exterior_y[y][0], x)
                exterior_y[y][1] = max(exterior_y[y][1], x)
    

            # Handle 門攤 or 角攤
            row = booth[0]
            try:
                space_no = int(booth[1:])
            except ValueError:
                space_no = booth[1:]

            if row in utils.DOOR_BOOTHS and space_no in utils.DOOR_BOOTHS[row]:
                booth_data['space_cat'] = '門攤'
            elif row in utils.CORNER_BOOTHS and space_no in utils.CORNER_BOOTHS[row]:
                booth_data['space_cat'] = '角攤'
            

        # Handle 外島
        for x, ys in exterior_x.items():
            for y in ys:
                if y == float('inf') or y == float('-inf'): continue
                booth_data = loc_booths[(x, y)][1]
                booth_data['isExteriorSpace'] = True
        
        for y, xs in exterior_y.items():
            for x in xs:
                if y == float('inf') or y == float('-inf'): continue
                booth_data = loc_booths[(x, y)][1]
                booth_data['isExteriorSpace'] = True
            


def get_space_cat(circle_data: utils.CircleForm):
    space = circle_data.row + circle_data.booth[:2]
    for _, booth_datas in HALL_DATA.items():
        if space in booth_datas:
            booth_data = booth_datas[space]
            return booth_data['space_cat']
    return "未知"


def get_all_specific_halls():
    res = []
    for hall in HALL_DATA.keys():
        hall_letter = hall[0]
        hall_numbers = hall[1:]
        for number in hall_numbers:
            res.append(hall_letter + number)
    return res


def find_circle_by_user_name(link_domain: str, username: str, day: int):

    def is_twitter_match(booth_data) -> bool:
        return booth_data['IsTwitterRegistered'] and ('https://twitter.com/' + username == booth_data['TwitterUrl'] or \
            'https://x.com/' + username == booth_data['TwitterUrl'])
    
    def is_pixiv_match(booth_data) -> bool:
        return booth_data['IsPixivRegistered'] and ('https://www.pixiv.net/users/' + username == booth_data['PixivUrl'] or \
            'https://www.pixiv.net/member.php?id=' + username == booth_data['PixivUrl'])

    check_func = {
        'Twitter': is_twitter_match,
        'Pixiv': is_pixiv_match
    }

    day_data = CIRCLE_DATA.get(str(day), {})

    res = utils.CircleForm()
    for hall, booth_datas in day_data.items():
        for booth, booth_data in booth_datas.items():
            if check_func[link_domain](booth_data):
                res.circle_name = booth_data['Name']
                res.author_name = booth_data['Author']
                res.row = booth[0]
                res.booth = booth[1:]
                res.circle_id = booth_data['CircleId']
                res.hall = HALL_DATA[hall][booth_data['Space'][:3]]['hall']
                break
            
        else:
            continue
        break
    else:
        return res


    # 如果當天找到，則檢查下一天都有沒有
    another_day_data = CIRCLE_DATA.get(str(day % 2 + 1), {})

    for _, booth_datas in another_day_data.items():
        for booth, booth_data in booth_datas.items():
            if check_func[link_domain](booth_data):
                res.has_two_days = True
                break
            
        else:
            continue
        break

    return res



def find_circle_by_row_booth(row: str, need_booth: str, day: int):
    
    res = utils.CircleForm()
    
    if not row or not need_booth:
        return res
    
    day_data = CIRCLE_DATA.get(str(day), {})
    
    for hall, booth_datas in day_data.items():
        for booth, booth_data in booth_datas.items():

            cur_row = booth[0]
            cur_booth = booth[1:]

            if cur_row == row and cur_booth == need_booth:
                res.circle_name = booth_data['Name']
                res.author_name = booth_data['Author']
                res.row = booth[0]
                res.booth = booth[1:]
                res.circle_id = booth_data['CircleId']
                res.hall = HALL_DATA[hall][booth_data['Space'][:3]]['hall']

                break
            
        else:
            continue
        break

    return res
