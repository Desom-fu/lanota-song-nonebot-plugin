from nonebot.rule import Rule
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from .config import allowed_groups

async def group_whitelist(bot: Bot, event: GroupMessageEvent) -> bool:
    return event.group_id in allowed_groups

whitelist_rule = Rule(group_whitelist)