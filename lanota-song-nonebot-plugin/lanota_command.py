from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, Message
from nonebot.params import CommandArg, ArgPlainText
from nonebot.typing import T_State
from pathlib import Path
import random
import json
import datetime
from .config import *
from .function import *
from .whitelist import whitelist_rule
from .text_image_text import send_image_or_text

# 初始化命令
la_today = on_command("la today", aliases={"la 今日曲", "lanota today", "lanota 今日曲"}, rule=whitelist_rule, priority=5)
la_random = on_command("la random", aliases={"la 随机", "lanota random", "lanota 随机"}, rule=whitelist_rule, priority=5)
la_alias = on_command("la alias", aliases={"la 别名", "lanota 别名", "lanota alias"}, rule=whitelist_rule, priority=5)
la_find = on_command("la find", aliases={"la 查找", "lanota find", "lanota 查找"}, rule=whitelist_rule, priority=5)
la_help = on_command("la help", aliases={"la 帮助", "lanota help", "lanota 帮助"}, rule=whitelist_rule, priority=5)
la_time = on_command("la time", aliases={"la 时长", "lanota time", "lanota 时长"}, rule=whitelist_rule, priority=5)
la_all = on_command("la all", aliases={"la 全部", "lanota all", "lanota 全部"}, rule=whitelist_rule, priority=5)

# 处理today命令
@la_today.handle()
async def handle_today(bot: Bot, event: MessageEvent):
    user_id = event.get_user_id()
    today_song = get_user_today_song(user_id)
    
    if not today_song:
        await send_image_or_text(user_id, la_today, "今日曲目获取失败，可能是歌曲数据未加载")
        return
    
    nickname = await get_nickname(bot, user_id)
    message = f"[{nickname}]的今日曲目：\n{format_song_info(today_song)}"
    await send_image_or_text(user_id, la_today, message)

# 处理random命令
@la_random.handle()
async def handle_random(bot: Bot, event: MessageEvent, state: T_State, args: Message = CommandArg()):
    user_id = event.get_user_id()
    arg = args.extract_plain_text().strip().lower()
    
    song_data = load_song_data()
    
    if not song_data:
        await send_image_or_text(user_id, la_random, "没有可用的歌曲数据")
        return
    
    # 处理子命令
    if arg:
        parts = arg.split()
        sub_command = parts[0]
        
        # level 数字
        if sub_command == "level" and len(parts) > 1:
            level = parts[1]
            filtered_songs = get_songs_by_level(song_data, level)
            
            if not filtered_songs:
                await send_image_or_text(user_id, la_random, f"没有找到难度为 {level} 的曲目")
                return
            
            random_number = await get_random_number_from_org(0, len(filtered_songs) - 1)
            selected_song = filtered_songs[random_number]
            message = f"随机曲目(难度 {level}):\n{format_song_info(selected_song)}"
            await send_image_or_text(user_id, la_random, message)
            return
        
        # 分类筛选
        category_map = {
            "main": "main",
            "主线": "main",
            "side": "side",
            "支线": "side",
            "expansion": "expansion",
            "扩展": "expansion",
            "扩展包": "expansion",
            "曲包": "expansion",
            "event": "event",
            "活动": "event",
            "限时活动": "event",
            "subscription": "subscription",
            "书房": "subscription",
            "订阅": "subscription"
        }
        
        if sub_command in category_map:
            category = category_map[sub_command]
            category_songs = get_songs_by_category(song_data, category)
            
            if not category_songs:
                await send_image_or_text(user_id, la_random, f"没有找到 {category} 分类的曲目")
                return
            
            random_number = await get_random_number_from_org(0, len(category_songs) - 1)
            selected_song = category_songs[random_number]
            message = f"随机曲目({category}):\n{format_song_info(selected_song)}"
            await send_image_or_text(user_id, la_random, message)
            return
    
    # 默认随机选择
    random_number = await get_random_number_from_org(0, len(song_data) - 1)
    selected_song = song_data[random_number]
    message = f"随机曲目:\n{format_song_info(selected_song)}"
    await send_image_or_text(user_id, la_random, message)

# 处理alias命令
@la_alias.handle()
async def handle_alias(bot: Bot, event: MessageEvent, state: T_State, args: Message = CommandArg()):
    user_id = event.get_user_id()
    arg = args.extract_plain_text().strip().lower()
    
    if not arg:
        await send_image_or_text(user_id, la_alias, "用法:\n"
                                  "/la alias add <别名>|<章节号或原名>\n"
                                  "/la alias remove <别名>")
        return
    
    parts = arg.split(maxsplit=1)
    if len(parts) < 1:
        await send_image_or_text(user_id, la_alias, "参数不足\n"
                                  "用法:\n"
                                  "/la alias add <别名>|<章节号或原名>\n"
                                  "/la alias remove <别名>")
        return
    
    action = parts[0]
    alias_data = load_alias_data()
    song_data = load_song_data()
    all_titles = {song['title'].lower() for song in song_data}
    
    if action == "add":
        if len(parts) < 2:
            await send_image_or_text(user_id, la_alias, "添加别名需要别名和章节号/原名参数，用|分隔")
            return
        
        alias_original = parts[1].split('|', 1)
        if len(alias_original) < 2:
            await send_image_or_text(user_id, la_alias, "格式错误，请使用 <别名>|<章节号或原名> 格式")
            return
        
        alias = alias_original[0].strip()
        search_term = alias_original[1].strip()
        
        # 优先按章节号查找
        matched_songs = [song for song in song_data if song['chapter'].lower() == search_term.lower()]
        
        # 如果没有找到章节号匹配，则按原名模糊查找
        if not matched_songs:
            search_term_lower = search_term.lower()
            matched_songs = [song for song in song_data if search_term_lower in song['title'].lower()]
        
        if not matched_songs:
            await send_image_or_text(user_id, la_alias, f"没有找到章节号或原名为 '{search_term}' 的歌曲")
            return
        
        if len(matched_songs) > 1:
            await send_image_or_text(user_id, la_alias, f"找到多个匹配的歌曲，请使用更精确的章节号或原名:\n"
                                  + "\n".join(f"{song['chapter']} - {song['title']}" for song in matched_songs))
            return
        
        std_name = matched_songs[0]['title']
        
        if alias.lower() in all_titles:
            await send_image_or_text(user_id, la_alias, f"'{alias}' 已经是歌曲原名，不能作为别名")
            return
        
        for existing_std_name, aliases in alias_data.items():
            if alias in aliases:
                await send_image_or_text(user_id, la_alias, f"别名 '{alias}' 已经被 '{existing_std_name}' 使用")
                return
        
        if std_name not in alias_data:
            alias_data[std_name] = []
        
        if alias not in alias_data[std_name]:
            alias_data[std_name].append(alias)
            save_alias_data(alias_data)
            await send_image_or_text(user_id, la_alias, f"成功为 '{std_name}' 添加别名 '{alias}'")
        else:
            await send_image_or_text(user_id, la_alias, f"别名 '{alias}' 已经存在")
    
    elif action == "remove":
        alias = parts[1].split('|')[0].strip()
        
        removed = False
        for std_name, aliases in alias_data.items():
            if alias in aliases:
                aliases.remove(alias)
                removed = True
                break
        
        if removed:
            save_alias_data(alias_data)
            await send_image_or_text(user_id, la_alias, f"成功删除别名 '{alias}'")
        else:
            await send_image_or_text(user_id, la_alias, f"未找到别名 '{alias}'")
    
    else:
        await send_image_or_text(user_id, la_alias, "无效操作，只能使用 add 或 remove")

# 处理find命令
@la_find.handle()
async def handle_find(bot: Bot, event: MessageEvent, state: T_State, args: Message = CommandArg()):
    user_id = event.get_user_id()
    arg = args.extract_plain_text().strip()
    
    if not arg:
        await send_image_or_text(user_id, la_find, "用法:\n"
                              "/la find <曲名> (模糊匹配)\n"
                              "/la find chapter <章节号> (精确匹配)\n"
                              "/la find songid <ID> (精确匹配)")
        return
    
    parts = arg.split(maxsplit=1)
    song_data = load_song_data()
    alias_data = load_alias_data()
    
    if len(parts) > 1:
        sub_command = parts[0].lower()
        search_term = parts[1]
        
        if sub_command == "chapter":
            chapter_id = search_term
            matched_songs = [song for song in song_data if song['chapter'].lower() == chapter_id.lower()]
            
            if matched_songs:
                message = f"找到Chapter为 {chapter_id} 的曲目:\n{format_song_info(matched_songs[0])}"
                await send_image_or_text(user_id, la_find, message)
            else:
                await send_image_or_text(user_id, la_find, f"没有找到章节号为 '{search_term}' 的曲目")
            return
        
        elif sub_command == "songid":
            try:
                song_id = int(search_term)
                matched_songs = [song for song in song_data if song['id'] == song_id]
                
                if matched_songs:
                    message = f"找到ID为 {song_id} 的曲目:\n{format_song_info(matched_songs[0])}"
                    await send_image_or_text(user_id, la_find, message)
                else:
                    await send_image_or_text(user_id, la_find, f"没有找到ID为 {song_id} 的曲目")
                return
            except ValueError:
                await send_image_or_text(user_id, la_find, "ID必须是数字")
                return
    
    # 默认曲名模糊匹配
    search_term = arg.lower()
    matched_songs = []
    
    for song in song_data:
        if search_term in song['title'].lower():
            matched_songs.append(song)
            continue
        
        std_name = song['title']
        if std_name in alias_data:
            for alias in alias_data[std_name]:
                if search_term in alias.lower():
                    matched_songs.append(song)
                    break
    
    if not matched_songs:
        await send_image_or_text(user_id, la_find, f"没有找到包含 '{search_term}' 的曲目")
        return
    
    if len(matched_songs) == 1:
        message = f"找到1首包含 '{search_term}' 的曲目:\n{format_song_info(matched_songs[0])}"
    else:
        message = f"找到 {len(matched_songs)} 首包含 '{search_term}' 的曲目:\n"
        for i, song in enumerate(matched_songs, 1):
            message += f"\n{i}. {song['title']} (Chapter: {song['chapter']})"
    
    await send_image_or_text(user_id, la_find, message)

# 处理time命令
@la_time.handle()
async def handle_time(bot: Bot, event: MessageEvent):
    user_id = event.get_user_id()
    song_data = load_song_data()
    
    if not song_data:
        await send_image_or_text(user_id, la_time, "没有可用的歌曲数据")
        return
    
    def parse_time(time_str):
        try:
            m, s = map(int, time_str.split(':'))
            return m * 60 + s
        except:
            return 0
    
    processed_songs = []
    for song in song_data:
        try:
            time_str = song['time']
            seconds = parse_time(time_str)
            if seconds > 0:
                processed_songs.append({
                    'song': song,
                    'seconds': seconds,
                    'time_str': time_str
                })
        except:
            continue
    
    long_songs = [s for s in processed_songs if s['seconds'] > 180]
    short_songs = [s for s in processed_songs if s['seconds'] < 120]
    
    long_songs.sort(key=lambda x: -x['seconds'])
    short_songs.sort(key=lambda x: x['seconds'])
    
    message = "时长统计:\n\n"
    
    if long_songs:
        message += f"长于3分钟的曲目(共{len(long_songs)}首，时长降序):\n"
        for i, song_info in enumerate(long_songs, 1):
            message += f"{i}. {song_info['song']['title']} - {song_info['time_str']} (Chapter: {song_info['song']['chapter']})\n"
        message += "\n"
    else:
        message += "没有长于3分钟的曲目\n\n"
    
    if short_songs:
        message += f"短于2分钟的曲目(共{len(short_songs)}首，时长升序):\n"
        for i, song_info in enumerate(short_songs, 1):
            message += f"{i}. {song_info['song']['title']} - {song_info['time_str']} (Chapter: {song_info['song']['chapter']})\n"
    else:
        message += "没有短于2分钟的曲目"
    
    await send_image_or_text(user_id, la_time, message)

# 全部曲目统计
@la_all.handle()
async def handle_all(bot: Bot, event: MessageEvent):
    user_id = event.get_user_id()
    song_data = load_song_data()
    
    category_counts = {}
    for song in song_data:
        category = song['category']
        category_counts[category] = category_counts.get(category, 0) + 1
    
    total_songs = len(song_data)
    
    category_name_map = {
        'main': '主线',
        'side': '支线',
        'expansion': '曲包',
        'event': '活动',
        'subscription': '书房'
    }
    
    category_info = []
    for category, count in category_counts.items():
        name = category_name_map.get(category, category)
        category_info.append(f"{name}: {count}首")
    
    message = (
        f"Lanota曲库统计（Fandom已收录）:\n"
        f"总曲目数量: {total_songs}首\n\n"
        f"按分类统计:\n"
        + "\n".join(category_info)
    )
    
    await send_image_or_text(user_id, la_all, message)

# 处理help命令
@la_help.handle()
async def handle_help(bot: Bot, event: MessageEvent):
    user_id = event.get_user_id()
    
    help_message = """
Lanota 机器人使用帮助:

1. 今日曲目
命令: /la today 或 /la 今日曲
功能: 获取今日随机曲目(每天固定)
示例: /la today

2. 随机曲目
命令: /la random 或 /la 随机
功能: 随机获取一首曲目
子命令:
  - /la random level <难度> - 随机指定难度的曲目
  - /la random <分类> - 随机指定分类的曲目
可用分类: main(主线), side(支线), expansion(曲包), event(活动), subscription(订阅)
示例:
  /la random level 12
  /la random main

3. 别名管理
命令: /la alias 或 /la 别名
功能: 管理歌曲别名
子命令:
  - /la alias add <别名>|<章节号或原名> - 添加别名(优先匹配章节号，其次匹配原名)
  - /la alias remove <别名> - 删除别名
示例:
  /la alias add gmr|0-1  # 为章节0-1的歌曲添加别名gmr
  /la alias add gmr|got more raves?  # 为歌曲got more raves?添加别名gmr
  /la alias remove gmr

4. 查找曲目
命令: /la find 或 /la 查找
功能: 查找曲目信息
子命令:
  - /la find <关键词> - 模糊匹配曲名或别名
  - /la find chapter <章节号> - 精确查找章节
  - /la find songid <ID> - 精确查找ID
示例:
  /la find got more raves?
  /la find chapter 0-1
  /la find songid 101

5. 时长统计
命令: /la time 或 /la 时长
功能: 显示长于3分钟和短于2分钟的曲目列表
示例: /la time

6. 曲库统计
命令: /la all 或 /la 全部
功能: 显示当前曲库的总曲目数量、最大ID和各分类曲目数量
示例: /la all

7.背景色设置
命令: /color 或 /设置背景色
功能: 设置消息背景颜色
示例:
/color 1f1e33 # 设置背景色为#1f1e33
/color default # 重置为默认背景色

8.帮助
命令: /la help 或 /la 帮助
功能: 显示本帮助信息
示例: /la help"""
    await send_image_or_text(user_id, la_help, help_message.strip())