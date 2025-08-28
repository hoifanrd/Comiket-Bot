import os
import anthropic
import json
import unicodedata
import io
import base64
import pathlib


import cogs.twitter.utils as utils

CLIENT = anthropic.AsyncAnthropic(
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)

parent_dir = pathlib.Path(__file__).parent.resolve()
with open(parent_dir.joinpath('shinagaki_example.jpg'), 'br') as f:
    SHINAGAKI_EXAMPLE_B64 = base64.b64encode(f.read()).decode()


async def gen_item_price_list_by_image(image: io.BufferedIOBase) -> tuple[list[str], list[int]]:
    image.seek(0)
    image_b64 = base64.b64encode(image.read()).decode()

    message = await CLIENT.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=20000,
        temperature=1,
        system="Your task is to identify all items with their price in the provided image of menu (品書き) and format the information into a JSON object.\n\nHere is an example of output JSON:\n```json\n[\n  {\n    \"name\": \"\",\n    \"detail\": \"\",\n    \"price\": 0\n    \"type\": \"\",\n    “type_zh”: \"\",\n  }\n]\n```\n\nWhere `type,type_zh` should be one of the followings (one line each). If there are no best fit item, make a short word describe it:\n```\n新刊,新刊\n新刊セット,新刊SET\n既刊,既刊\n既刊セット,既刊SET\n合同本,合同本\nアンソロジー,選集\n総集編,總集編\nアクリルスタンド,立牌\nタペストリー,掛軸\nポスター,海報\n抱き枕カバー,抱枕套\nテーブルマット,桌墊\nカードホルダー,卡盒\n色紙,色紙\nパーカー,連帽衫\nTシャツ,T恤\nステッカー,貼紙\nマグカップ,馬克杯\nキーホルダー,鑰匙扣\nCD,CD\nフォルダー,資料夾\nカード収納ボックス,卡片收納盒\nブランケット,毛毯\nComment,Comment\n```\nWhere `Comment` is a special type, appears in the last of the array, contains any details / terms that are not captured in the output before.\n\nAnd `name` is the item name as shown in the image. Could be left blank. for example (one line each, no newline):\n```\nブルアカ合同\nヒカリ\nC105\n```\n\nThen, `detail` is the item detail shown in the image. Could be left blank. for example (one line each, no newline):\n```\nB5/76P イラスト&漫画\n無くなり次第終了\n```\n\nFinally, `price` is an integer with the price of the item in Japanese Yen.\n\nOutput your final JSON object inside <json_output> tags. Break down into multiple item if the menu contains multiple item with the same price. Use Japanese. Output empty array `[]` if the image is not a 品書き. Do not output any other info.",
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": SHINAGAKI_EXAMPLE_B64
                        }
                    }
                ]
            },
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "text",
                        "text": "<json_output>\n[\n  {\n    \"name\": \"ガキ負け合同\",\n    \"detail\": \"B5/76P イラスト&漫画\",\n    \"type\": \"新刊\",\n    \"type_zh\": \"新刊\",\n    \"price\": 2000\n  },\n  {\n    \"name\": \"\",\n    \"detail\": \"ガキ負け、アクスタセット 無くなり次第終了\",\n    \"type\": \"新刊セット\",\n    \"type_zh\": \"新刊SET\",\n    \"price\": 3000\n  },\n  {\n    \"name\": \"ヒカリ\",\n    \"detail\": \"\",\n    \"type\": \"アクリルスタンド\",\n    \"type_zh\": \"立牌\",\n    \"price\": 800\n  },\n  {\n    \"name\": \"ノゾミ\",\n    \"detail\": \"\",\n    \"type\": \"アクリルスタンド\",\n    \"type_zh\": \"立牌\",\n    \"price\": 800\n  },\n  {\n    \"name\": \"ヒカリ・ノゾミ セット\",\n    \"detail\": \"\",\n    \"type\": \"アクリルスタンド\",\n    \"type_zh\": \"立牌\",\n    \"price\": 1500\n  },\n  {\n    \"name\": \"水着ヒナ\",\n    \"detail\": \"作:たっぷまん（間に合えば自分も出します!!）\",\n    \"type\": \"色紙\",\n    \"type_zh\": \"色紙\",\n    \"price\": 2000\n  },\n  {\n    \"name\": \"ヒマリ\",\n    \"detail\": \"作:たっぷまん（間に合えば自分も出します!!）\",\n    \"type\": \"色紙\",\n    \"type_zh\": \"色紙\",\n    \"price\": 2000\n  },\n  {\n    \"name\": \"カンナ\",\n    \"detail\": \"作:たっぷまん（間に合えば自分も出します!!）\",\n    \"type\": \"色紙\",\n    \"type_zh\": \"色紙\",\n    \"price\": 2000\n  },\n  {\n    \"name\": \"モモイ\",\n    \"detail\": \"作:たっぷまん（間に合えば自分も出します!!）\",\n    \"type\": \"色紙\",\n    \"type_zh\": \"色紙\",\n    \"price\": 2000\n  },\n  {\n    \"name\": \"\",\n    \"detail\": \"ラインナップ: 水着ヒナ・ヒマリ/カンナ・モモイ 全商品対応 購入された方に先着で限定ブロマイドを配布します!!（間に合えば）\",\n    \"type\": \"Comment\",\n    \"type_zh\": \"Comment\",\n    \"price\": 0\n  }\n]\n</json_output>"
                    }
                ]
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/jpeg",
                            "data": image_b64
                        }
                    }
                ]
            }
        ]
    )

    try:
        items_prices = json.loads(message.content[0].text.replace("<json_output>", "").replace("</json_output>", "").strip())
        print(items_prices)
        items = []
        prices = []

        for elem in items_prices:
            # Filter out items that are not 新刊 or 既刊 or SET
            if '新刊' not in elem['type_zh'] and '既刊' not in elem['type_zh'] and 'SET' not in elem['type_zh']:
                continue
            
            if len(elem['name']) > 0:
                elem['name'] = '〔' + elem['name'] + '〕'

            items.append(elem['type_zh'] + elem['name'])
            prices.append(elem['price'])
        
        return items, prices
    
    except Exception:
        print("Error parsing GPT response:", message.content)


async def gen_circle_by_tweet_data(title, content, day) -> utils.CircleForm:

    message = await CLIENT.messages.create(
    model="claude-3-5-haiku-20241022",
    max_tokens=8192,
    temperature=1,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "<examples>\n<example>\n<TWITTER_POST>\n桜井まこと🌸1日目東ク-18a (@makoto_sakurai)\n\n【C106お品書き】\n8/16(土) 東7ホール ク-18a 「さくらもち工房」\n\nお待ちしております！✨\n</TWITTER_POST>\n<ideal_output>\n<json_output>\n{\n  \"date_joining\": [\n    {\n      \"day\": 1,\n      \"circle_name\": \"さくらもち工房\",\n      \"venue\": \"東\",\n      \"row\": \"ク\",\n      \"booth\": \"18a\"\n    }\n  ],\n  \"author_name\": \"桜井まこと\"\n}\n</json_output>\n</ideal_output>\n</example>\n<example>\n<TWITTER_POST>\nシロガネヒナ*C106 土*東4ア-76ab/日*東6ア-21a \n#C106 8/17（日）2日目\n🌈東6ホール ア-21a 【MILK BAR】お品書き🌈\n新作は、どうぞよろしくお願い...\n</TWITTER_POST>\n<ideal_output>\n<json_output>\n{\n  \"date_joining\": [\n    {\n      \"day\": 1,\n      \"circle_name\": null,\n      \"venue\": \"東\",\n      \"row\": \"ア\",\n      \"booth\": \"76ab\"\n    },\n    {\n      \"day\": 2,\n      \"circle_name\": \"MILK BAR\",\n      \"venue\": \"東\",\n      \"row\": \"ア\",\n      \"booth\": \"21a\"\n    }\n  ],\n  \"author_name\": \"シロガネヒナ\"\n}\n</json_output>\n</ideal_output>\n</example>\n</examples>\n\n"
                },
                {
                    "type": "text",
                    "text": "You will be extracting specific information from a Twitter post related to Comiket. Your task is to identify and format the information into a JSON object.\n\nFirst, here are the Comiket dates for reference:\n1日目 8/16(土), 2日目 8/17(日)\n\nNow, here is the Twitter post:\n<twitter_post>\n{{TWITTER_POST}}\n</twitter_post>\n\nYour task is to extract the information from the provided post, output this information as a JSON object with the following structure:\n\n```json\n{\n  \"date_joining\": [\n    {\n      \"day\": 1,\n      \"circle_name\": null,\n      \"venue\": null,\n      \"row\": null,\n      \"booth\": null\n    },\n   {\n      \"day\": 2,\n      \"circle_name\": null,\n      \"venue\": null,\n      \"row\": null,\n      \"booth\": null\n    ]\n  },\n  \"author_name\": null\n}\n```\n\nFollow these steps to extract and format the information:\n\n1. Identify the author's name from the first line of the post.\n\n2. Look for the date that matches Comiket dates provided from the whole post, including first line. Notice the date indicator 土, 日, 1日目, etc. This will be the date of joining.\n\n3. Find the circle location information, which typically follows the date and includes:\n   - Venue: 東 (East), 西 (West), 南 (South) or null only\n   - Row: A single character, either hiragana (あ, い, う, etc.) or Latin alphabet (a-z, A-Z)\n   - Booth: A number followed by a letter (e.g., 52a, 1b, 2ab). Omit dash \"-\".\n\n4. If a circle name is provided, include it. It is often written after the circle location, sometimes quoted with 「」. Not first line of the post. Otherwise, set it to null.\n\n5. Determine which day (day 1 and/or day 2) the circle is participating based on the date. Only output the date_joining object they are joining. \n6. Fill in the JSON structure with the extracted information. Set any fields you couldn't find information for to null.\n\nOutput your final JSON object inside <json_output> tags. Do not output any other info.\n\nRemember:\n- Only include information explicitly stated in the Twitter post.\n- If information for either day 1 and/or day 2 is not provided, do not output the object for the day.\n- The author_name should be the name at the beginning of the tweet, without any emojis or additional text.".replace("{{TWITTER_POST}}", title + "\n\n" + content)
                }
            ]
        }
    ]
    )
    
    res = utils.CircleForm()

    try:
        gpt_circle_data = json.loads(message.content[0].text.replace("<json_output>", "").replace("</json_output>", "").strip())

        res.author_name = gpt_circle_data.get('author_name', '')
        if 'date_joining' in gpt_circle_data:
            for date_data in gpt_circle_data['date_joining']:
                if date_data.get('day', '') == day:
                    res.has_two_days = len(gpt_circle_data['date_joining']) > 1
                    res.circle_name = date_data.get('circle_name', '')
                    res.row = unicodedata.normalize('NFKC', date_data.get('row', ''))
                    res.booth = unicodedata.normalize('NFKC', date_data.get('booth', ''))
                    break
    except Exception:
        print("Error parsing GPT response:", message.content)
        
    return res