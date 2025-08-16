from nonebot.rule import Rule
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent, PrivateMessageEvent
from .config import allowed_groups, allowed_users

async def check_whitelist(bot: Bot, event: Event) -> bool:
    if isinstance(event, GroupMessageEvent):
        # 群聊检查群白名单
        return event.group_id in allowed_groups
    elif isinstance(event, PrivateMessageEvent):
        # 私聊检查用户白名单
        return str(event.user_id) in allowed_users
    return False

whitelist_rule = Rule(check_whitelist)