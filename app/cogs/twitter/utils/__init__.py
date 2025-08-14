from cogs.twitter import database

DEFAULT_DAY1_CHANNELS = [
    1405538869956579402
]

DEFAULT_DAY2_CHANNELS = [

]

XY_GROUPS = {
    "東456": {
        "東4": [0, 370],
        "東5": [390, 760],
        "東6": [780, 2000],
    },
    "東7": {
        "東7": [0, 2000],
    },
    "西12": {
        "西1": [0, 490],
        "西2": [500, 2000],
    },
    "南12": {
        "南1": [0, 310],
        "南2": [320, 1000],
    },
}

CHAR_GROUPS = {
    "東456": "アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホマミムメモヤユヨ",
    "東7": "ABCDEFGHIJKLMNOPQRSTUVW",
    "西12": "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめ",
    "南12": "abcdefghijklmnopqrst",
}


def get_hall(circle_data):
    circle_x = int(database.find_circle_by_row_booth(circle_data['row'], circle_data['booth'], circle_data['day'])['x'])
    
    for halls, chars in CHAR_GROUPS.items():
        if circle_data['row'] in chars:
            for hall, (start, end) in XY_GROUPS[halls].items():
                if start <= circle_x <= end:
                    return hall

