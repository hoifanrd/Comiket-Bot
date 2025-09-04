from .comitia153_const import *
import os

class CircleForm(object):
    def __init__(self):
        self.circle_name = ""
        self.author_name = ""

        self.row = ""
        self.booth = ""
        self.circle_id = ""
        self.hall = ""

        self.remarks = ""
        self.has_two_days = False

        self.user_id = ""
        self.link_domain = ""     # 'Twitter' or 'Pixiv'
        self.day = 0
        self.shinagaki_img_urls = []

        self.channel_id = 0
    
    def __bool__(self):
        return bool(self.circle_id)


def gen_thread_title(circle_data: CircleForm) -> str:
    return f"{circle_data.circle_name} / {circle_data.day} 日目 / {circle_data.row} {circle_data.booth} / {circle_data.author_name}"

def gen_thread_circle_id(circle_data: CircleForm) -> str:
    event_name = os.environ.get('CURR_EVENT')
    circle_id = circle_data.circle_id
    if not circle_id:
        circle_id = "00000"
    return f"{event_name}-{circle_data.day}-{circle_data.row}{circle_data.booth}-{circle_id}"