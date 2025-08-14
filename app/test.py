import pygsheets

"""
SPREADSHEET_IDS = [
    "https://docs.google.com/spreadsheets/d/1vo3ThT61vGmsuKQTLMndRxaUdnMphNmGZIuatL1Z59M",   # Day 1
    "https://docs.google.com/spreadsheets/d/10P60Q-KyI9Q-zMdb1G1XlUUDZWXEkRnIzB1GmxyhOU4"    # Day 2
]
"""

AUTHOR_NAME_COL = 0
AUTHOR_TWITTER_COL = 1
ROW_COL = 2
BOOTH_COL = 3
BOTH_DAY_COL = 7
ADDITIONAL_COL = 8
DISCORD_CHAN_COL = 11


SPREADSHEET_IDS = [
    "https://docs.google.com/spreadsheets/d/1TlUJMUO6oeBbDh5_HPjXbcUr4etvlVFe3HaJi04jL-s",
    "https://docs.google.com/spreadsheets/d/1TlUJMUO6oeBbDh5_HPjXbcUr4etvlVFe3HaJi04jL-s"
]


def fill_in_spreadsheet_from_circle(circle_data: dict):

    cur_day = circle_data['day']

    sheet_name = f"Day{cur_day}-{circle_data['circle_hall']}"

    gc = pygsheets.authorize(service_file='creds.json')
    sht = gc.open_by_url(SPREADSHEET_IDS[cur_day - 1])

    wks = sht.worksheet_by_title(sheet_name)
    exist_rows = wks.range("A1:L300", returnas='matrix')
    for row_idx, row in enumerate(exist_rows):
        if row[ROW_COL] == circle_data['row'] and row[BOOTH_COL] == circle_data['booth']:
            return False, row[DISCORD_CHAN_COL]

        if not row[0]:
            break
    
    wks.update_value(f'{chr(65+AUTHOR_NAME_COL)}{row_idx+1}', circle_data['author_name'])
    wks.update_value(f'{chr(65+AUTHOR_TWITTER_COL)}{row_idx+1}', circle_data['author_link'])
    wks.update_value(f'{chr(65+ROW_COL)}{row_idx+1}', circle_data['row'])
    wks.update_value(f'{chr(65+BOOTH_COL)}{row_idx+1}', circle_data['booth'])
    wks.update_value(f'{chr(65+BOTH_DAY_COL)}{row_idx+1}', '是' if circle_data['has_two_days'] else '不是')
    wks.update_value(f'{chr(65+ADDITIONAL_COL)}{row_idx+1}', circle_data['addition'])
    
if __name__ == "__main__":
    circle_data = {
        'has_two_days': True,
        'addition': 'Sample addition text',
        'day': 1,
        'circle_hall': '東5',
        'circle_name': 'Sample Circle',
        'author_name': 'Sample Author',
        'row': 'A',
        'booth': '01',
        'author_link': 'https://x.com/sample_author',
        'media_links': ['https://example.com/image1.jpg', 'https://example.com/image2.jpg']
    }
    fill_in_spreadsheet_from_circle(circle_data)