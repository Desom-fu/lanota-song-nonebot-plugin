from nonebot.adapters.onebot.v11 import MessageSegment, Message
from nonebot.adapters.onebot.v11 import GROUP, Bot, Event
from nonebot.adapters.onebot.v11 import GroupMessageEvent
from nonebot.log import logger
from nonebot import on_command
from nonebot.params import CommandArg
from .config import *
from .whitelist import whitelist_rule
from .function import *
from .text_image_text import generate_image_with_text, send_image_or_text_forward, send_image_or_text

#确定一些事件
confirm = on_command('confirm', permission=GROUP, priority=1, block=True, rule=whitelist_rule)
@confirm.handle()
async def confirm_handle(bot: Bot, event: GroupMessageEvent):
    # 打开文件
    data = open_data(full_path)
    user_id = str(event.get_user_id())

    #判断是否开辟event事件栏
    if user_id not in data:
        data[user_id] = {'event': 'nothing'}
    elif 'event' not in data[user_id]:
        data[user_id]['event'] = 'nothing'
        
    if data[user_id]['event'] == 'changing_bgcolor':
        # 处理设置默认颜色或自定义颜色
        if data[user_id]['temp_bgcolor'] == 'default':
            if 'bg_color' in data[user_id]:
                del data[user_id]['bg_color']  # 删除自定义颜色即恢复默认
            message = "背景色已重置为默认颜色"
        else:
            data[user_id]['bg_color'] = data[user_id]['temp_bgcolor']
            message = f"更改背景色成功！\n当前背景色号为：#{data[user_id]['bg_color']}"
        
        # 清除临时数据
        del data[user_id]['temp_bgcolor']
        if 'previous_bgcolor' in data[user_id]:
            del data[user_id]['previous_bgcolor']
        
        data[user_id]['event'] = 'nothing'
        save_data(full_path, data)
        
        await send_image_or_text(user_id, confirm, 
                               f"{message}",
                               True, None)
    else:
        await send_image_or_text(user_id, confirm, "你现在似乎没有需要确定的事情", True, None)

#取消一些事件
deny = on_command('deny', permission=GROUP, priority=1, block=True, rule=whitelist_rule)
@deny.handle()
async def deny_handle(bot: Bot, event: GroupMessageEvent):
    # 打开文件
    data = open_data(full_path)
    user_id = str(event.get_user_id())
    
    if user_id not in data:
        data[user_id] = {'event': 'nothing'}
    else:
        if 'event' not in data[user_id]:
            data[user_id]['event'] = 'nothing'
    if data[user_id]['event'] == 'changing_bgcolor':
        # 如果有之前设置过的颜色，则回退到那个颜色
        if 'previous_bgcolor' in data[user_id]:
            data[user_id]['bg_color'] = data[user_id]['previous_bgcolor']
            del data[user_id]['previous_bgcolor']
            message = "已恢复之前的背景色设置"
        else:
            message = "你取消了更改背景色"
        
        # 清除临时数据
        if 'temp_bgcolor' in data[user_id]:
            del data[user_id]['temp_bgcolor']
        data[user_id]['event'] = 'nothing'
        save_data(full_path, data)
        
        await send_image_or_text(user_id, deny, message, True, None)
    else:
        await send_image_or_text(user_id, deny, "你现在似乎没有需要确定的事情", True, None)