import os
import anthropic
import json

CLIENT = anthropic.Anthropic(
    # defaults to os.environ.get("ANTHROPIC_API_KEY")
    api_key=os.environ.get("ANTHROPIC_API_KEY")
)

def gen_circle_by_tweet_data(title, content, day) -> dict:

    message = CLIENT.messages.create(
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
    
    gpt_circle_data = {
        'author_name': '',
        'circle_name': '',
        'row': '',
        'booth': '',
        'has_two_days': False,
    }

    try:
        gpt_circle_data = json.loads(message.content[0].text.replace("<json_output>", "").replace("</json_output>", "").strip())

        gpt_circle_data['author_name'] = gpt_circle_data.get('author_name', '')
        if 'date_joining' in gpt_circle_data:
            for date_data in gpt_circle_data['date_joining']:
                if date_data.get('day', '') == day:
                    gpt_circle_data['has_two_days'] = len(gpt_circle_data['date_joining']) > 1
                    gpt_circle_data['circle_name'] = date_data.get('circle_name', '')
                    gpt_circle_data['row'] = date_data.get('row', '')
                    gpt_circle_data['booth'] = date_data.get('booth', '')
                    break
    except Exception:
        print("Error parsing GPT response:", message.content)
        
    return gpt_circle_data