import discord

from app_const import *

def is_special_item(item: str) -> bool:
    """檢查項目是否為SET"""
    return 'SET' in item.upper()


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


def check_endall_permission(interaction_ctx: discord.Interaction | discord.ext.commands.Context) -> bool:
    if isinstance(interaction_ctx, discord.Interaction):
        user = interaction_ctx.user
    else:
        user = interaction_ctx.author
    return user.id in ENDALL_ALLOWED_USERS


def check_voting_permission(interaction: discord.Interaction) -> bool:
    """檢查用戶是否有投票權限"""
    # 檢查是否為服務器成員
    if not interaction.guild or not isinstance(interaction.user, discord.Member):
        return False

    # 檢查用戶是否擁有任一指定身份組
    user_roles = interaction.user.roles
    voter_roles = [interaction.guild.get_role(rid) for rid in VOTER_ROLE_IDS]
    voter_roles = [role for role in voter_roles if role is not None]
    
    return any(role in user_roles for role in voter_roles)