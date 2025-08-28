import pygsheets
import asyncio

SPREADSHEET_IDS = [
    "https://docs.google.com/spreadsheets/d/1vo3ThT61vGmsuKQTLMndRxaUdnMphNmGZIuatL1Z59M",   # Day 1
    "https://docs.google.com/spreadsheets/d/10P60Q-KyI9Q-zMdb1G1XlUUDZWXEkRnIzB1GmxyhOU4"    # Day 2
]

AUTHOR_NAME_COL = 0
AUTHOR_TWITTER_COL = 1
ROW_COL = 2
BOOTH_COL = 3
AREA_COL = 5
BOTH_DAY_COL = 7
ADDITIONAL_COL = 8
ID_COL = 9
HAPPY_COL = 10
DISCORD_CHAN_COL = 11

#SPREADSHEET_IDS = [
#    "https://docs.google.com/spreadsheets/d/1TlUJMUO6oeBbDh5_HPjXbcUr4etvlVFe3HaJi04jL-s",
#    "https://docs.google.com/spreadsheets/d/1TlUJMUO6oeBbDh5_HPjXbcUr4etvlVFe3HaJi04jL-s"
#]

async def fill_in_spreadsheet_from_circle(circle_data: dict):

    cur_day = circle_data['day']

    sheet_name = f"Day{cur_day}-{circle_data['circle_hall']}"

    gc = pygsheets.authorize(service_file='creds.json')
    sht = gc.open_by_url(SPREADSHEET_IDS[cur_day - 1])

    wks = sht.worksheet_by_title(sheet_name)
    exist_rows = wks.range("A1:L300", returnas='matrix')
    for row_idx, row in enumerate(exist_rows):
        if row[ROW_COL] == circle_data['row'] and row[BOOTH_COL] == circle_data['booth']:
            return False, {'exist_channel': row[DISCORD_CHAN_COL]}

    # Separate the loop - Avoid blank rows in between
    for row_idx, row in enumerate(exist_rows):
        if not row[0]:
            break
    
    wks.update_value(f'{chr(65+AUTHOR_NAME_COL)}{row_idx+1}', circle_data['author_name'])
    wks.update_value(f'{chr(65+AUTHOR_TWITTER_COL)}{row_idx+1}', circle_data['author_link'])
    wks.update_value(f'{chr(65+ROW_COL)}{row_idx+1}', circle_data['row'])
    wks.update_value(f'{chr(65+BOOTH_COL)}{row_idx+1}', circle_data['booth'])
    wks.update_value(f'{chr(65+BOTH_DAY_COL)}{row_idx+1}', '是' if circle_data['has_two_days'] else '不是')
    wks.update_value(f'{chr(65+ADDITIONAL_COL)}{row_idx+1}', circle_data['addition'])

    await asyncio.sleep(3)  # 確保更新完成

    circle_area = wks.get_value(f'{chr(65+AREA_COL)}{row_idx+1}')
    circle_sheet_id = wks.get_value(f'{chr(65+ID_COL)}{row_idx+1}')

    return True, {'circle_area': circle_area, 'circle_sheet_id': circle_sheet_id, 'excel_row_id': row_idx + 1}


def fill_in_spreadsheet_dc_link(circle_data, row_id, link):
    cur_day = circle_data['day']
    sheet_name = f"Day{cur_day}-{circle_data['circle_hall']}"

    gc = pygsheets.authorize(service_file='creds.json')
    sht = gc.open_by_url(SPREADSHEET_IDS[cur_day - 1])

    wks = sht.worksheet_by_title(sheet_name)
    wks.update_value(f'{chr(65+DISCORD_CHAN_COL)}{row_id}', link)

    circle_sheet_id_formula = wks.get_value(f'{chr(65+ID_COL)}{row_id}', value_render=pygsheets.ValueRenderOption.FORMULA)
    split_formula = circle_sheet_id_formula.split('"')
    split_formula[1] = link
    new_formula = '"'.join(split_formula)
    wks.update_value(f'{chr(65+ID_COL)}{row_id}', new_formula, parse=True)