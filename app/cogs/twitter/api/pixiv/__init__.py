from pixivpy3 import AppPixivAPI
from bs4 import BeautifulSoup
import os
import asyncio
import io
import traceback
import time

REFRESH_TOKEN = os.environ.get("PIXIV_REFRESH_TOKEN")
AAPI = AppPixivAPI()

expires_in = AAPI.auth(refresh_token=REFRESH_TOKEN).expires_in
last_refresh = time.time()

async def download_image(url: str) -> io.BytesIO:
    
    # Refresh token if needed
    global last_refresh, expires_in
    if time.time() - last_refresh > expires_in - 60:
        expires_in = await asyncio.to_thread(AAPI.auth, refresh_token=REFRESH_TOKEN).expires_in
        last_refresh = time.time()

    image = io.BytesIO()
    await asyncio.to_thread(AAPI.download, url=url, fname=image)
    return image


async def get_pixiv_details(url):

    # Refresh token if needed
    global last_refresh, expires_in
    if time.time() - last_refresh > expires_in - 60:
        expires_in = await asyncio.to_thread(AAPI.auth, refresh_token=REFRESH_TOKEN).expires_in
        last_refresh = time.time()

    post_id = url.split('/')[-1].split('?')[0]

    json_result = await asyncio.to_thread(AAPI.illust_detail, post_id)

    illust = json_result.illust
    user = illust.user

    user_id = str(user.id)
    user_name = user.name
    content = illust.title + '\n' + BeautifulSoup(illust.caption, "lxml").text
    media_links = []

    if illust.meta_single_page.original_image_url:
        media_links.append(illust.meta_single_page.original_image_url)

    extra_pages = illust.meta_pages
    for page in extra_pages:
        if page.image_urls.original:
            media_links.append(page.image_urls.original)

    return user_id, user_name, content, media_links