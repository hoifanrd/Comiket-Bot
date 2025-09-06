from .comitia153_const import *
from urllib.parse import urlparse
import os
import discord

from app_const import *

SOCIAL_LINK_PREFIX = {
    'Twitter': 'https://x.com/',
    'Pixiv': 'https://www.pixiv.net/users/'
}

class CircleForm(object):
    def __init__(self):
        self.circle_name = ""
        self.author_name = ""

        self.row = ""
        self.booth = ""
        self.circle_id = ""
        self.hall = ""
        self.space_cat = ""

        self.remarks = ""
        self.has_two_days = False

        # self.user_id = ""
        # self.link_domain = ""     # 'Twitter' or 'Pixiv'
        self.social_link = ""
        self.day = 0
        self.shinagaki_img_urls = []

        self.channel_id = 0
    
    def get_social_id(self) -> str:
        if not self.social_link:
            return ""
        parsed_url = urlparse(self.social_link)
        socialID = parsed_url.path.strip('/').split('/')[-1]
        return socialID

    def get_link_domain(self) -> str:
        if not self.social_link:
            return ""
        parsed_url = urlparse(self.social_link)
        domain = parsed_url.netloc.lower()
        for key, prefix in SOCIAL_LINK_PREFIX.items():
            if domain in prefix:
                return key
        return ""

    def __bool__(self):
        return bool(self.circle_id)


def gen_thread_title(circle_data: CircleForm) -> str:
    return f"{circle_data.circle_name} / {circle_data.day} 日目 / {circle_data.row} {circle_data.booth} / {circle_data.author_name}"

def gen_thread_msg(circle_data: CircleForm) -> str:
    msg_title = gen_thread_title(circle_data)
    return f"{msg_title}\n{circle_data.social_link}\n攤位級別 : {circle_data.space_cat}\n備註 : {circle_data.remarks}"

def gen_thread_circle_id(circle_data: CircleForm) -> str:
    event_name = os.environ.get('CURR_EVENT')
    circle_id = circle_data.circle_id
    if not circle_id:
        circle_id = "00000"
    return f"{event_name}-{circle_data.day}-{circle_data.row}{circle_data.booth}-{circle_id}"


def check_execute_permission(interaction: discord.Interaction) -> bool:
    """檢查用戶是否有權限"""
    # 檢查是否為服務器成員
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False

    # 檢查用戶是否擁有任一指定身份組
    user_roles = interaction.user.roles
    voter_roles = [interaction.guild.get_role(rid) for rid in VOTER_ROLE_IDS]
    voter_roles = [role for role in voter_roles if role is not None]
    
    return any(role in user_roles for role in voter_roles)

def check_admin_permission(interaction_ctx: discord.Interaction | discord.ext.commands.Context) -> bool:
    """檢查用戶是否為特殊用戶"""
    if isinstance(interaction_ctx, discord.Interaction):
        user = interaction_ctx.user
    else:
        user = interaction_ctx.author
    user_roles = user.roles
    special_roles = [interaction_ctx.guild.get_role(rid) for rid in SPECIAL_ROLE_IDS]
    special_roles = [role for role in special_roles if role is not None]
    
    return any(role in user_roles for role in special_roles)