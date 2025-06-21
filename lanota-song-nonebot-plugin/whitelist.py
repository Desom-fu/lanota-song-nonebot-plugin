from nonebot.rule import Rule
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent

# 定义允许的群组 ID 白名单
allowed_groups = {1037559220,551374760,565752728}

async def group_whitelist(bot: Bot, event: GroupMessageEvent) -> bool:
    return event.group_id in allowed_groups

whitelist_rule = Rule(group_whitelist)