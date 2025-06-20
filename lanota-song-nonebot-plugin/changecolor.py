from nonebot.adapters.onebot.v11 import MessageSegment, Message
from nonebot.adapters.onebot.v11 import GROUP
from nonebot.adapters.onebot.v11 import Bot, Event, GroupMessageEvent
from nonebot.params import CommandArg
from nonebot.log import logger
from nonebot import on_command, require
import re
from .config import *
from .function import *
from .whitelist import whitelist_rule
from .text_image_text import generate_image_with_text, send_image_or_text


# 自定义背景色命令
set_bgcolor = on_command('color', aliases={'设置背景色', '自定义背景色', 'set_bg', 'bg_set', 'set-bg', 'bg-set', 'set-bgcolor'}, permission=GROUP, priority=1, block=True, rule=whitelist_rule)
@set_bgcolor.handle()
async def set_bgcolor_handle(bot: Bot, event: GroupMessageEvent, arg: Message = CommandArg()):
    # 打开用户数据
    data = open_data(full_path)
    user_id = str(event.get_user_id())
    
    # 初始化用户数据
    if user_id not in data:
        await send_image_or_text(user_id, set_bgcolor, f"你未注册LanotaBot账号哦！", True, None, 20)
    
    # 检查是否有正在进行的事件（除了nothing和changing_bgcolor）
    current_event = data[user_id].get('event', 'nothing')
    if current_event not in ['nothing', 'changing_bgcolor']:
        await send_image_or_text(user_id, set_bgcolor, "你还有正在进行的事件未完成", True, None)
        return
    
    # 解析参数
    color_arg = str(arg).strip().lower()
    
    # 处理默认颜色设置
    if color_arg == 'default':
        # 设置事件
        data[user_id]['event'] = 'changing_bgcolor'
        data[user_id]['temp_bgcolor'] = 'default'  # 特殊标记
        save_data(full_path, data)
        
        
        await send_image_or_text(user_id, set_bgcolor, 
                               f"你确定要将背景色\n重置为默认颜色吗？\n"
                               "请输入 /confirm 确认或 /deny 取消", 
                               True, None)
        return
    
    # 检查色号格式
    if not re.match(r'^#?[0-9a-fA-F]{6}$', color_arg):
        await send_image_or_text(user_id, set_bgcolor, 
                               "请输入正确的色号格式（例如 #1f1e33 或 1f1e33）\n"
                               "或使用 /color default 重置为默认颜色",
                               True, None)
        return
    
    # 标准化色号格式（去掉#，统一小写）
    color_code = color_arg.lstrip('#').lower()
    
    # 设置事件和临时存储色号
    data[user_id]['event'] = 'changing_bgcolor'
    data[user_id]['temp_bgcolor'] = color_code
    # 保存当前颜色以便deny时回退
    if 'previous_bgcolor' not in data[user_id]:
        data[user_id]['previous_bgcolor'] = data[user_id].get('bg_color', "f7dbff")
    data[user_id]['bg_color'] = color_code
    save_data(full_path, data)
    
    # 发送确认提示（此时消息背景已经是新色号）
    await send_image_or_text(user_id, set_bgcolor, 
                           f"当前预览背景色: #{color_code}\n"
                           f"可以随便输入命令预览背景色\n"
                           "请输入 /confirm 确认或 /deny 取消".strip(),
                           True, None)