from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, Message
from nonebot.params import CommandArg
from nonebot.typing import T_State
from .config import *
from .function import *
from .whitelist import whitelist_rule
from .text_image_text import send_image_or_text
from .jiaoben.fandom_pachong import main as update_songs

# 初始化命令
la_today = on_command("la today", aliases={"la 今日曲", "lanota today", "lanota 今日曲"}, rule=whitelist_rule, priority=5)
la_random = on_command("la random", aliases={"la 随机", "lanota random", "lanota 随机"}, rule=whitelist_rule, priority=5)
la_alias = on_command("la alias", aliases={"la 别名", "lanota 别名", "lanota alias"}, rule=whitelist_rule, priority=5)
la_find = on_command("la find", aliases={"la 查找", "lanota find", "lanota 查找", "lanota info", "la info"}, rule=whitelist_rule, priority=5)
la_help = on_command("la help", aliases={"la 帮助", "lanota help", "lanota 帮助"}, rule=whitelist_rule, priority=5)
la_time = on_command("la time", aliases={"la 时长", "lanota time", "lanota 时长"}, rule=whitelist_rule, priority=5)
la_all = on_command("la all", aliases={"la 全部", "lanota all", "lanota 全部"}, rule=whitelist_rule, priority=5)
la_update = on_command("la update", aliases={"la 更新", "lanota update", "lanota 更新"}, priority=5)

# 添加update命令处理函数
@la_update.handle()
async def handle_update(bot: Bot, event: MessageEvent):
    user_id = event.get_user_id()
    
    # 检查是否为超级用户
    if user_id not in bot.config.superusers:
        await la_update.finish("权限不足，只有超级用户可以使用此命令")
        return
    
    try:
        # 执行爬虫脚本
        await la_update.send("开始更新歌曲数据……")
        
        # 运行爬虫并获取结果
        result = update_songs()
        
        # 解析结果并发送
        if isinstance(result, dict):
            message = (
                f"歌曲数据更新完成！\n"
                f"更新前歌曲: {result.get('before', 0)}首\n"
                f"新增歌曲: {result.get('added', 0)}首\n"
                f"当前总歌曲: {result.get('total', 0)}首"
            )
        else:
            message = "歌曲数据更新完成！"
            
        await la_update.finish(message)
        return
        
    except Exception as e:
        if str(e) == "FinishedException()":
            return
        await la_update.finish(f"更新过程中发生错误: {str(e)}")

# 处理today命令
@la_today.handle()
async def handle_today(bot: Bot, event: MessageEvent):
    user_id = event.get_user_id()
    today_song = get_user_today_song(user_id)
    
    if not today_song:
        await send_image_or_text(user_id, la_today, "今日歌曲获取失败，可能是歌曲数据未加载")
        return
    
    nickname = await get_nickname(bot, user_id)
    message = f"[{nickname}]的今日歌曲：\n\n{format_song_info(today_song)}"
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
                await send_image_or_text(user_id, la_random, f"没有找到难度为[{level}]的歌曲")
                return
            
            random_number = await get_random_number_from_org(0, len(filtered_songs) - 1)
            selected_song = filtered_songs[random_number]
            message = f"随机歌曲(难度{level}):\n\n{format_song_info(selected_song)}"
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
                await send_image_or_text(user_id, la_random, f"没有找到[{category}]分类的歌曲")
                return
            
            random_number = await get_random_number_from_org(0, len(category_songs) - 1)
            selected_song = category_songs[random_number]
            message = f"随机歌曲({category}):\n\n{format_song_info(selected_song)}"
            await send_image_or_text(user_id, la_random, message)
            return
    
    # 默认随机选择
    random_number = await get_random_number_from_org(0, len(song_data) - 1)
    selected_song = song_data[random_number]
    message = f"随机歌曲:\n\n{format_song_info(selected_song)}"
    await send_image_or_text(user_id, la_random, message)

# 处理alias命令
@la_alias.handle()
async def handle_alias(bot: Bot, event: MessageEvent, state: T_State, args: Message = CommandArg()):
    user_id = event.get_user_id()
    arg = args.extract_plain_text().strip()
    
    if not arg:
        await send_image_or_text(user_id, la_alias, "用法:\n"
                              "/la alias add <别名>/<章节号或原名>\n"
                              "/la alias del <别名>\n"
                              "/la alias show <章节号/ID/别名/曲名>")
        return
    
    parts = arg.split(maxsplit=1)
    if len(parts) < 1:
        await send_image_or_text(user_id, la_alias, "参数不足\n"
                              "用法:\n"
                              "/la alias add <别名>/<章节号或原名>\n"
                              "/la alias del <别名>\n"
                              "/la alias show <章节号/ID/别名/曲名>")
        return
    
    action = parts[0].lower()
    alias_data = load_alias_data()
    song_data = load_song_data()
    all_titles = {song['title'].lower() for song in song_data}
    
    if action == "add":
        if len(parts) < 2:
            await send_image_or_text(user_id, la_alias, "添加别名需要别名和章节号/原名参数，用/分隔")
            return
        
        # 只分割第一个斜杠
        split_result = parts[1].split('/', 1)
        if len(split_result) < 2:
            await send_image_or_text(user_id, la_alias, "格式错误，请使用 <别名>/<章节号或原名> 格式")
            return
        
        alias = split_result[0].strip()
        search_term = split_result[1].strip()
        
        matched_songs, _, total_count = find_song_by_search_term(search_term, song_data, alias_data)
        
        if not matched_songs:
            await send_image_or_text(user_id, la_alias, f"没有找到章节号、ID或原名为[{search_term}]的歌曲")
            return
        
        if total_count > 1:
            message = f"找到多个匹配的歌曲({total_count}个)，请使用更精确的章节号、ID或原名:\n"
            for i, song in enumerate(matched_songs, 1):
                message += f"{i}. {song['chapter']} - {song['title']} (ID: {song['id']})\n"
            if total_count > 10:
                message += f"……共{total_count}个"
            await send_image_or_text(user_id, la_alias, message.strip())
            return
        
        std_name = matched_songs[0]['title']
        
        if alias.lower() in all_titles:
            await send_image_or_text(user_id, la_alias, f"[{alias}]已经是歌曲原名，不能作为别名")
            return
        
        for existing_std_name, aliases in alias_data.items():
            if alias in aliases:
                await send_image_or_text(user_id, la_alias, f"别名[{alias}]已经被[{existing_std_name}]使用")
                return
        
        if std_name not in alias_data:
            alias_data[std_name] = []
        
        if alias not in alias_data[std_name]:
            alias_data[std_name].append(alias)
            save_alias_data(alias_data)
            await send_image_or_text(user_id, la_alias, f"成功为[{std_name}]添加别名[{alias}]")
        else:
            await send_image_or_text(user_id, la_alias, f"别名[{alias}]已经存在")
    
    elif action == "del":
        alias = parts[1].split('/')[0].strip()
        
        deld = False
        for std_name, aliases in alias_data.items():
            if alias in aliases:
                aliases.remove(alias)
                deld = True
                break
        
        if deld:
            save_alias_data(alias_data)
            await send_image_or_text(user_id, la_alias, f"成功删除别名[{alias}]")
        else:
            await send_image_or_text(user_id, la_alias, f"未找到别名[{alias}]")
    
    elif action == "show":
        if len(parts) < 2:
            await send_image_or_text(user_id, la_alias, "请指定要查询的章节号、ID、别名或曲名")
            return
        
        search_term = parts[1].strip()
        matched_songs, _, total_count = find_song_by_search_term(search_term, song_data, alias_data)
        
        if not matched_songs:
            await send_image_or_text(user_id, la_alias, f"没有找到章节号、ID、别名或原名为[{search_term}]的歌曲")
            return
        
        if total_count > 1:
            message = f"找到多个匹配的歌曲({total_count}个):\n"
            for i, song in enumerate(matched_songs, 1):
                message += f"{i}. {song['chapter']} - {song['title']} (ID: {song['id']})\n"
            if total_count > 10:
                message += f"……共{total_count}个"
            await send_image_or_text(user_id, la_alias, message.strip())
            return
        
        std_name = matched_songs[0]['title']
        aliases = alias_data.get(std_name, [])
        
        if not aliases:
            message = f"歌曲[{std_name}]目前没有设置别名"
        else:
            message = f"歌曲[{std_name}]的别名({len(aliases)}个):\n" + "\n".join(f"{i+1}. {alias}" for i, alias in enumerate(aliases))
        
        await send_image_or_text(user_id, la_alias, message)
    
    else:
        await send_image_or_text(user_id, la_alias, "无效操作，只能使用 add/del/show")

# 处理find命令
@la_find.handle()
async def handle_find(bot: Bot, event: MessageEvent, state: T_State, args: Message = CommandArg()):
    user_id = event.get_user_id()
    search_term = args.extract_plain_text().strip()
    
    if not search_term:
        await send_image_or_text(user_id, la_find, "用法:\n"
                              "/la info <搜索词> (按优先级匹配章节号、ID、别名和曲名)\n"
                              "匹配优先级:\n"
                              "1. 完全匹配章节号\n"
                              "2. 完全匹配ID\n"
                              "3. 完全匹配别名\n"
                              "4. 完全匹配曲名\n"
                              "5. 模糊匹配曲名或别名")
        return
    
    song_data = load_song_data()
    alias_data = load_alias_data()
    
    matched_songs, match_type, total_count = find_song_by_search_term(search_term, song_data, alias_data)
    
    if not matched_songs:
        await send_image_or_text(user_id, la_find, f"没有找到与[{search_term}]相关的歌曲")
        return
    
    if total_count == 1:
        message = f"通过搜索词[{search_term}]进行[{match_type}]找到这首歌曲:\n\n{format_song_info(matched_songs[0])}"
    else:
        message = f"通过搜索词[{search_term}]进行[{match_type}]找到匹配的歌曲({total_count}首):\n"
        for i, song in enumerate(matched_songs, 1):
            message += f"\n{i}. {song['title']} (Chapter: {song['chapter']}, ID: {song['id']})"
        if total_count > 10:
            message += f"\n……共{total_count}首"
    
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
        message += f"长于3分钟的歌曲(共{len(long_songs)}首，时长降序):\n"
        for i, song_info in enumerate(long_songs, 1):
            message += f"{i}. {song_info['song']['title']} - {song_info['time_str']} (Chapter: {song_info['song']['chapter']})\n"
        message += "\n"
    else:
        message += "没有长于3分钟的歌曲\n\n"
    
    if short_songs:
        message += f"短于2分钟的歌曲(共{len(short_songs)}首，时长升序):\n"
        for i, song_info in enumerate(short_songs, 1):
            message += f"{i}. {song_info['song']['title']} - {song_info['time_str']} (Chapter: {song_info['song']['chapter']})\n"
    else:
        message += "没有短于2分钟的歌曲"
    
    await send_image_or_text(user_id, la_time, message)

# 全部歌曲统计
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
        f"总歌曲数量: {total_songs}首\n\n"
        f"按分类统计:\n"
        + "\n".join(category_info)
    )
    
    await send_image_or_text(user_id, la_all, message)

# 处理help命令
help_categories = {
    "daily": {
        "name": "今日歌曲",
        "aliases": ["today", "今日曲"],
        "commands": [
            "/la today - 获取今日随机歌曲(每天固定)",
            "/la 今日曲 - 同上"
        ],
        "examples": [
            "/la today"
        ]
    },
    "random": {
        "name": "随机歌曲",
        "aliases": ["random", "随机"],
        "commands": [
            "/la random - 随机获取一首歌曲",
            "/la random level <难度> - 随机指定难度的歌曲",
            "/la random <分类> - 随机指定分类的歌曲"
        ],
        "sub_commands": {
            "分类": ["main(主线)", "side(支线)", "expansion(曲包)", "\nevent(活动)", "subscription(订阅)"]
        },
        "examples": [
            "/la random level 12",
            "/la random main"
        ]
    },
    "alias": {
        "name": "别名管理",
        "aliases": ["alias", "别名"],
        "commands": [
            "/la alias add <别名>/<搜索词> - 添加别名",
            "/la alias del <别名> - 删除别名",
            "/la alias show <搜索词> - 查看歌曲别名"
        ],
        "examples": []
    },
    "search": {
        "name": "查找歌曲",
        "aliases": ["find", "查找", "info"],
        "commands": [
            "/la find - 查找歌曲信息",
            "/la info - 同上"
        ],
        "priority": [
            "1. 完全匹配章节号",
            "2. 完全匹配ID",
            "3. 完全匹配别名",
            "4. 完全匹配曲名",
            "5. 模糊匹配曲名或别名"
        ],
        "examples": []
    },
    "stats": {
        "name": "统计功能",
        "aliases": ["time", "时长", "all", "全部"],
        "commands": [
            "/la time - 显示长于3分钟和短于2分钟的歌曲列表",
            "/la all - 显示曲库统计信息"
        ],
        "examples": [
            "/la time",
            "/la all"
        ]
    },
    "color": {
        "name": "背景色设置",
        "aliases": ["color", "设置背景色"],
        "commands": [
            "/color <色号> - 设置消息背景颜色",
            "/color default - 重置为默认背景色"
        ],
        "examples": [
            "/color #1f1e33 - 设置背景色为#1f1e33",
            "/color default - 重置为默认背景色"
        ]
    },
    "help": {
        "name": "帮助",
        "aliases": ["help", "帮助"],
        "commands": [
            "/la help - 显示本帮助信息"
        ],
        "examples": [
            "/la help"
        ]
    }
}

# 处理help命令
@la_help.handle()
async def handle_help(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    user_id = event.get_user_id()
    category = args.extract_plain_text().strip().lower()
    
    # 如果没有指定分类，显示主帮助菜单
    if not category:
        main_help = (
            "Lanota 机器人使用帮助\n"
            "══════════════\n"
            "输入以下分类指令查看详细帮助：\n"
        )
        
        # 添加所有分类的入口
        for cat in help_categories.values():
            main_help += f"- /la help {cat['aliases'][0]} - {cat['name']}\n"
        
        main_help += (
            "══════════════\n"
            "输入 /la help <分类> 查看详细帮助\n"
            "示例: /la help random"
        )
        
        await send_image_or_text(user_id, la_help, main_help)
        return
    
    # 查找匹配的分类
    matched_category = None
    for cat in help_categories.values():
        if category in cat["aliases"]:
            matched_category = cat
            break
    
    if matched_category:
        # 构建分类详细帮助
        help_text = f"【{matched_category['name']}】\n"
        help_text += "══════════════\n"
        help_text += "命令:\n"
        help_text += "\n".join(matched_category["commands"]) + "\n"
        
        # 添加子命令说明
        if "sub_commands" in matched_category:
            help_text += "\n可用子命令:\n"
            for key, values in matched_category["sub_commands"].items():
                help_text += f"{key}: {', '.join(values)}\n"
        
        # 添加匹配优先级说明
        if "priority" in matched_category:
            help_text += "\n匹配优先级:\n"
            help_text += "\n".join(matched_category["priority"]) + "\n"
        
        # 添加示例
        if matched_category["examples"]:
            help_text += "\n示例:\n"
            help_text += "\n".join(matched_category["examples"]) + "\n"
        
        help_text += "══════════════\n"
        help_text += "输入 /la help 查看主菜单"
        
        await send_image_or_text(user_id, la_help, help_text)
    else:
        await send_image_or_text(user_id, la_help, "未找到该分类，\n请输入 /la help\n查看所有分类")