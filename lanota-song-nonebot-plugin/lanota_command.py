from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, MessageEvent, Message
from nonebot.params import CommandArg
from nonebot.typing import T_State
import asyncio
from concurrent.futures import ThreadPoolExecutor
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
la_cal = on_command("la cal", aliases={"la 计算", "lanota cal", "lanota 计算"}, rule=whitelist_rule, priority=5)
la_notes = on_command("la notes", aliases={"la 物量", "lanota notes", "lanota 物量"}, rule=whitelist_rule, priority=5)
la_rating = on_command("la rating", aliases={"la rating", "lanota rating"}, rule=whitelist_rule, priority=5)
la_category = on_command("la category", aliases={"la cate", "lanota category", "lanota cate"}, rule=whitelist_rule, priority=5)

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
    "订阅": "subscription",
    "inf": "inf",
    "无限": "inf"
}

# 创建线程池执行器
executor = ThreadPoolExecutor(max_workers=1)

async def run_in_threadpool(func, *args):
    """将同步函数放入线程池执行"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, func, *args)

# 处理手动更新命令
@la_update.handle()
async def handle_update(bot: Bot, event: MessageEvent):
    user_id = event.get_user_id()
    
    # 检查是否为超级用户
    if user_id not in bot.config.superusers:
        await la_update.finish("权限不足，只有超级用户可以使用此命令")
        return
    
    try:
        # 执行爬虫脚本（异步方式）
        await la_update.send("开始更新乐曲数据，请稍候...")
        
        # 在单独的线程中运行同步爬虫函数
        result = await run_in_threadpool(update_songs)
        
        # 解析结果并发送
        if isinstance(result, dict):
            message = (
                f"乐曲数据更新完成！\n"
                f"更新前乐曲: {result.get('before', 0)}首\n"
                f"新增乐曲: {result.get('added', 0)}首\n"
                f"当前总乐曲: {result.get('total', 0)}首"
            )
        else:
            message = "乐曲数据更新完成！"
            
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
        await send_image_or_text(user_id, la_today, "今日乐曲获取失败，可能是乐曲数据未加载")
        return
    
    nickname = await get_nickname(bot, user_id)
    message = f"[{nickname}]的今日乐曲：\n\n{format_song_info(today_song)}"
    await send_image_or_text(user_id, la_today, message)

# 处理random命令
@la_random.handle()
async def handle_random(bot: Bot, event: MessageEvent, state: T_State, args: Message = CommandArg()):
    user_id = event.get_user_id()
    arg = args.extract_plain_text().strip().lower()
    
    song_data = load_song_data()
    
    if not song_data:
        await send_image_or_text(user_id, la_random, "没有可用的乐曲数据")
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
                await send_image_or_text(user_id, la_random, f"没有找到难度为[{level}]的乐曲")
                return
            
            random_number = await get_random_number_from_org(0, len(filtered_songs) - 1)
            selected_song = filtered_songs[random_number]
            message = f"随机乐曲(难度{level}):\n\n{format_song_info(selected_song)}"
            await send_image_or_text(user_id, la_random, message)
            return
        
        if sub_command in category_map:
            category = category_map[sub_command]
            category_songs = get_songs_by_category(song_data, category)
            
            if not category_songs:
                await send_image_or_text(user_id, la_random, f"没有找到[{category}]分类的乐曲")
                return
            
            random_number = await get_random_number_from_org(0, len(category_songs) - 1)
            selected_song = category_songs[random_number]
            message = f"随机乐曲({category}):\n\n{format_song_info(selected_song)}"
            await send_image_or_text(user_id, la_random, message)
            return
    
    # 默认随机选择
    random_number = await get_random_number_from_org(0, len(song_data) - 1)
    selected_song = song_data[random_number]
    message = f"随机乐曲:\n\n{format_song_info(selected_song)}"
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
            await send_image_or_text(user_id, la_alias, f"没有找到章节号、ID或原名为[{search_term}]的乐曲")
            return
        
        if total_count > 1:
            message = f"找到多个匹配的乐曲({total_count}个)，请使用更精确的章节号、ID或原名:\n"
            for i, song in enumerate(matched_songs, 1):
                message += f"{i}. {song['chapter']} - {song['title']} (ID: {song['id']})\n"
            if total_count > 10:
                message += f"……共{total_count}个"
            await send_image_or_text(user_id, la_alias, message.strip())
            return
        
        std_name = matched_songs[0]['title']
        
        if alias.lower() in all_titles:
            await send_image_or_text(user_id, la_alias, f"[{alias}]已经是乐曲原名，不能作为别名")
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
            await send_image_or_text(user_id, la_alias, f"[{alias}]已经是[{std_name}]的别名")
    
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
            await send_image_or_text(user_id, la_alias, f"没有找到章节号、ID、别名或原名为[{search_term}]的乐曲")
            return
        
        if total_count > 1:
            message = f"找到多个匹配的乐曲({total_count}个):\n"
            for i, song in enumerate(matched_songs, 1):
                message += f"{i}. {song['chapter']} - {song['title']} (ID: {song['id']})\n"
            if total_count > 10:
                message += f"……共{total_count}个"
            await send_image_or_text(user_id, la_alias, message.strip())
            return
        
        std_name = matched_songs[0]['title']
        aliases = alias_data.get(std_name, [])
        
        if not aliases:
            message = f"乐曲[{std_name}]目前没有设置别名"
        else:
            message = f"乐曲[{std_name}]的别名({len(aliases)}个):\n" + "\n".join(f"{i+1}. {alias}" for i, alias in enumerate(aliases))
        
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
        await send_image_or_text(user_id, la_find, f"没有找到与[{search_term}]相关的乐曲")
        return
    
    if total_count == 1:
        message = f"通过搜索词[{search_term}]进行[{match_type}]找到这首乐曲:\n\n{format_song_info(matched_songs[0])}"
    else:
        message = f"通过搜索词[{search_term}]进行[{match_type}]找到匹配的乐曲({total_count}首):\n"
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
        await send_image_or_text(user_id, la_time, "没有可用的乐曲数据")
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
        message += f"长于3分钟的乐曲(共{len(long_songs)}首，时长降序):\n"
        for i, song_info in enumerate(long_songs, 1):
            message += f"\n{i}. {song_info['song']['title']} -|- {song_info['time_str']} (Chapter: {song_info['song']['chapter']})"
        message += '\n'
    else:
        message += "没有长于3分钟的乐曲\n"
    
    if short_songs:
        message += f"\n短于2分钟的乐曲(共{len(short_songs)}首，时长升序):"
        for i, song_info in enumerate(short_songs, 1):
            message += f"\n{i}. {song_info['song']['title']} -|- {song_info['time_str']} (Chapter: {song_info['song']['chapter']})"
    else:
        message += "没有短于2分钟的乐曲"
    
    await send_image_or_text(user_id, la_time, message)

# 全部乐曲统计
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
        f"总乐曲数量: {total_songs}首\n\n"
        f"按分类统计:\n"
        + "\n".join(category_info)
    )
    
    await send_image_or_text(user_id, la_all, message)

@la_cal.handle()
async def handle_cal(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    user_id = event.get_user_id()
    arg = args.extract_plain_text().strip()
    
    if not arg:
        await send_image_or_text(user_id, la_cal, 
            "用法:\n"
            "1. 根据曲目计算:\n"
            "   /la cal harmony数目/tune数目/fail数目/难度/曲目\n"
            "   示例: /la cal 900/300/50/Master/7-5\n"
            "2. 直接计算:\n"
            "   /la cal harmony数目/tune数目/fail数目/物量/等级\n"
            "   示例: /la cal 900/300/50/1250/16\n"
            "注意: 如果输入物量总和与总物量不同，会自动调整fail数目\n"
            "注意: 输入的数字不能为负数")
        return
    
    # 解析参数 - 只取前五个斜杠分割的部分
    parts = arg.split('/', 4)  # 最多分割4次，得到5个部分
    if len(parts) < 5:
        await send_image_or_text(user_id, la_cal, "参数格式错误，需要5个参数用/分隔")
        return
    
    try:
        harmony = int(parts[0])
        tune = int(parts[1])
        fail = int(parts[2])
    except ValueError:
        await send_image_or_text(user_id, la_cal, "前三个参数必须是数字")
        return
    
    # 检查是否为负数
    if harmony < 0 or tune < 0 or fail < 0:
        await send_image_or_text(user_id, la_cal, "输入的判定/物量不能为负数！")
        return
    
    # 判断是哪种计算方式
    if parts[3].lower() in ['whisper', 'acoustic', 'ultra', 'master']:
        # 方式1: 根据曲目计算
        difficulty_type = parts[3].lower()
        search_term = parts[4]
        
        song_data = load_song_data()
        alias_data = load_alias_data()
        
        matched_songs, match_type, total_count = find_song_by_search_term(search_term, song_data, alias_data)
        
        if not matched_songs:
            await send_image_or_text(user_id, la_cal, f"没有找到与[{search_term}]相关的乐曲")
            return
        
        if total_count > 1:
            message = f"找到多个匹配的乐曲({total_count}首)，请使用更精确的搜索词:\n"
            for i, song in enumerate(matched_songs, 1):
                message += f"{i}. {song['title']} (Chapter: {song['chapter']}, ID: {song['id']})\n"
            if total_count > 10:
                message += f"……共{total_count}首"
            await send_image_or_text(user_id, la_cal, message.strip())
            return
        
        song = matched_songs[0]
        
        # 获取难度和物量
        difficulty_value = song['difficulty'].get(difficulty_type, "未知")
        notes_value = song['notes'].get(difficulty_type, 0)
        
        if difficulty_value == "未知" or notes_value == 0:
            await send_image_or_text(user_id, la_cal, f"乐曲[{song['title']}]没有{difficulty_type}难度的数据")
            return
        
        # 计算 rating
        rating, adjusted_fail, adjustment, is_exceeded, is_negative, bonus, base_level = calculate_rating(harmony, tune, fail, notes_value, str(difficulty_value))
        
        if is_negative:
            message = "输入的判定/物量不能为负数！"
        elif is_exceeded:
            message = (
                f"乐曲: {song['title']}\n"
                f"难度: {difficulty_type.capitalize()} {difficulty_value}\n"
                f"当前输入总物量为：{harmony + tune + fail}，已经高于本乐曲的物量：{notes_value}，无法计算"
            )
        else:
            message = (
                f"乐曲: {song['title']}\n"
                f"难度: {difficulty_type.capitalize()} {difficulty_value}\n"
                f"总物量: {notes_value}\n"
                f"输入判定: {harmony + tune + fail} (Harmony: {harmony}, Tune: {tune}, Fail: {fail})\n"
            )
            
            if adjustment != 0:
                message += (
                    f"自动调整: Fail {fail} → {adjusted_fail} ({adjustment:+})\n"
                    f"最终结果: {harmony + tune + adjusted_fail} (Harmony: {harmony}, Tune: {tune}, Fail: {adjusted_fail})\n"
                )
            
            message += (
                f"单曲Rating: {rating}\n"
                f"计算方式: ({harmony} + {tune}/3) / {notes_value} * ({base_level} + 1 + 难度加成({bonus}))"
            )
        
    else:
        # 方式2: 直接计算
        try:
            notes = int(parts[3])
        except ValueError:
            await send_image_or_text(user_id, la_cal, "物量参数必须是数字")
            return
        
        level = parts[4]
        
        # 验证等级格式
        valid_levels = [str(i) for i in range(1, 17)] + ['13+', '14+', '15+', '16+']
        if level not in valid_levels:
            await send_image_or_text(user_id, la_cal, "等级必须是1-16或13+,14+,15+,16+")
            return
        
        # 计算 rating
        rating, adjusted_fail, adjustment, is_exceeded, is_negative, bonus, base_level = calculate_rating(harmony, tune, fail, notes, level)
        
        if is_negative:
            message = "输入的判定/物量不能为负数！"
        elif is_exceeded:
            message = (
                f"总物量: {notes}\n"
                f"等级: {level}\n"
                f"当前输入总物量为：{harmony + tune + fail}，已经高于输入的物量：{notes}，无法计算"
            )
        else:
            message = (
                f"总物量: {notes}\n"
                f"等级: {level}\n"
                f"输入判定: {harmony + tune + fail} (Harmony: {harmony}, Tune: {tune}, Fail: {fail})\n"
            )
            
            if adjustment != 0:
                message += (
                    f"自动调整: Fail {fail} → {adjusted_fail} ({adjustment:+})\n"
                    f"最终结果: {harmony + tune + adjusted_fail} (Harmony: {harmony}, Tune: {tune}, Fail: {adjusted_fail})\n"
                )
            
            message += (
                f"单曲Rating: {rating}\n"
                f"计算方式: ({harmony} + {tune}/3) / {notes} * ({base_level} + 1 + 难度加成({bonus}))"
            )
    
    await send_image_or_text(user_id, la_cal, message)

# 物量统计
@la_notes.handle()
async def handle_notes(bot: Bot, event: MessageEvent):
    user_id = event.get_user_id()
    song_data = load_song_data()
    
    if not song_data:
        await send_image_or_text(user_id, la_notes, "没有可用的乐曲数据")
        return
    
    # 收集所有谱面数据
    charts = []
    for song in song_data:
        for diff_type in ['whisper', 'acoustic', 'ultra', 'master']:
            notes_value = song['notes'].get(diff_type, 0)
            difficulty_value = song['difficulty'].get(diff_type, "未知")
            
            if notes_value and difficulty_value != "未知":
                charts.append({
                    'title': song['title'],
                    'notes': int(notes_value),
                    'difficulty': diff_type.capitalize(),
                    'difficulty_value': difficulty_value,
                    'chapter': song['chapter']
                })
    
    # 按物量降序排序
    charts.sort(key=lambda x: -x['notes'])
    
    # 只取前50个
    top_charts = charts[:50]
    
    if not top_charts:
        await send_image_or_text(user_id, la_notes, "没有找到有效的谱面数据")
        return
    
    # 构建消息
    message = "物量最高的前50个谱面:\n"
    for i, chart in enumerate(top_charts, 1):
        message += f"\n{i}. {chart['title']} -|- 物量{chart['notes']} (难度: {chart['difficulty']} {chart['difficulty_value']}, Chapter: {chart['chapter']})"
    
    await send_image_or_text(user_id, la_notes, message)

@la_rating.handle()
async def handle_rating(bot: Bot, event: MessageEvent):
    user_id = event.get_user_id()
    song_data = load_song_data()
    
    if not song_data:
        await send_image_or_text(user_id, la_rating, "没有可用的乐曲数据")
        return
    
    # 1. 获取所有15级以上的Master和Ultra难度谱面
    high_level_charts = []
    for song in song_data:
        for diff_type in ['master', 'ultra']:
            difficulty_value = song['difficulty'].get(diff_type, "未知")
            notes_value = song['notes'].get(diff_type, 0)
            
            if difficulty_value == "未知" or not notes_value:
                continue
            
            # 确保notes是整数
            try:
                notes_value = int(notes_value)
            except (ValueError, TypeError):
                continue
            
            # 解析难度等级
            level_str = str(difficulty_value)
            base_level = 0
            has_plus = False
            
            if level_str.endswith('+'):
                try:
                    base_level = float(level_str[:-1])
                    has_plus = True
                except ValueError:
                    continue
            else:
                try:
                    base_level = float(level_str)
                except ValueError:
                    continue
            
            if base_level >= 15:
                high_level_charts.append({
                    'song': song,
                    'difficulty_type': diff_type.capitalize(),
                    'difficulty_value': difficulty_value,
                    'notes': notes_value,
                    'base_level': base_level,
                    'has_plus': has_plus,
                    'level_str': level_str
                })
    
    if not high_level_charts:
        await send_image_or_text(user_id, la_rating, "没有找到15级以上的Master或Ultra难度谱面")
        return
    
    # 2. 按等级分组
    level_groups = {}
    for chart in high_level_charts:
        level = chart['level_str']
        if level not in level_groups:
            level_groups[level] = []
        level_groups[level].append(chart)
    
    # 3. 按等级排序 (16+ > 16 > 15+ > 15)
    sorted_levels = sorted(level_groups.keys(), key=lambda x: (
        -float(x[:-1] if x.endswith('+') else x),
        -x.endswith('+')
    ))
    
    # 4. 从每个等级组随机抽取谱面构建B30 (不放回)
    b30 = []
    remaining_slots = 30
    
    for level in sorted_levels:
        if remaining_slots <= 0:
            break
        
        charts_in_level = level_groups[level]
        random.shuffle(charts_in_level)
        
        # 计算这个等级的最大rating
        harmony = charts_in_level[0]['notes']
        tune = 0
        fail = 0
        notes = charts_in_level[0]['notes']
        level_value = charts_in_level[0]['difficulty_value']
        
        level_rating, _, _, _, _, _, _ = calculate_rating(
            harmony, tune, fail, notes, level_value
        )
        
        # 确定这个等级可以取多少谱面
        take = min(len(charts_in_level), remaining_slots)
        
        for chart in charts_in_level[:take]:
            b30.append({
                'song': chart['song'],
                'difficulty_type': chart['difficulty_type'],
                'difficulty_value': chart['difficulty_value'],
                'rating': level_rating,
                'level_str': chart['level_str']
            })
        
        remaining_slots -= take
    
    # 如果不足30个，用最后一个等级的rating补全
    if len(b30) < 30:
        last_rating = b30[-1]['rating'] if b30 else 0.0
        while len(b30) < 30:
            b30.append({
                'song': None,
                'difficulty_type': 'N/A',
                'difficulty_value': 'N/A',
                'rating': last_rating,
                'level_str': 'N/A'
            })
    
    # 5. 计算R5 (从最高rating的谱面中重复选择，直到凑满5个)
    r5 = []
    if b30:
        # 找出最高rating
        max_rating = max(item['rating'] for item in b30)
        top_rated = [item for item in b30 if item['rating'] == max_rating]
        
        # 如果最高rating的谱面不足5个，就重复选择
        if len(top_rated) < 5:
            # 计算需要重复多少次
            repeat_times = (5 // len(top_rated)) + 1
            # 生成足够的选择池
            selection_pool = (top_rated * repeat_times)[:5]
            r5 = selection_pool
        else:
            # 如果足够就直接随机选择5个
            r5 = random.sample(top_rated, 5)
    
    # 6. 计算总rating
    b30_sum = sum(item['rating'] for item in b30)
    r5_sum = sum(item['rating'] for item in r5)
    total_rating = (b30_sum + r5_sum) / 35
    
    # 7. 构建消息 - 显示完整的30个B30谱面
    message = "════════════ Rating计算 ══════════════\n"
    message += f"▪ 理论Max Rating: {total_rating:.2f}\n"
    message += f"▪ B30平均: {b30_sum/30:.2f}\n"
    message += f"▪ R5平均: {r5_sum/5:.2f}\n"
    message += "════════════ B30谱面 (随机30个) ══════════════"
    
    # 显示完整的30个B30谱面
    for i, item in enumerate(b30, 1):
        song_name = item['song']['title'] if item['song'] else "N/A"
        message += f"\n{i:2d}. {song_name} -|- {item['difficulty_type']} {item['difficulty_value']} (Rating: {item['rating']:.2f})"
    
    message += "\n════════════ R5谱面 (随机5个) ══════════════\n"
    
    for i, item in enumerate(r5, 1):
        song_name = item['song']['title'] if item['song'] else "N/A"
        message += f"{i}. {song_name} -|- {item['difficulty_type']} {item['difficulty_value']} (Rating: {item['rating']:.2f})\n"
    
    await send_image_or_text(user_id, la_rating, message.strip())

# 处理category命令
@la_category.handle()
async def handle_category(bot: Bot, event: MessageEvent, args: Message = CommandArg()):
    user_id = event.get_user_id()
    arg = args.extract_plain_text().strip().lower()
    
    if not arg:
        await send_image_or_text(user_id, la_category, 
            "用法:\n"
            "/la category <分类或章节前缀> [min[/max]]\n"
            "示例:\n"
            "/la category 0 5 - 展示第0章前5首\n"
            "/la category x - 展示分类x的所有曲目(最多100首)\n"
            "/la category inf 101/200 - 展示inf分类的第101-200首\n"
            "可用分类:\n"
            "main(主线), side(支线), expansion(曲包), event(活动), subscription(书房), inf(无限)")
        return
    
    # 解析参数
    parts = arg.split()
    category_or_chapter = parts[0]
    min_max = "1" if len(parts) < 2 else parts[1]
    
    # 解析min/max
    if "/" in min_max:
        min_val, max_val = min_max.split("/", 1)
    else:
        min_val = min_max
        max_val = "100"
    
    try:
        min_val = int(min_val)
        max_val = int(max_val)
    except ValueError:
        await send_image_or_text(user_id, la_category, "范围参数必须是数字")
        return
    
    # 验证范围
    if min_val < 1:
        await send_image_or_text(user_id, la_category, "最小值不能小于1")
        return
    
    if min_val > max_val:
        await send_image_or_text(user_id, la_category, "最小值不能大于最大值")
        return
    
    # 获取歌曲数据
    song_data = load_song_data()
    if not song_data:
        await send_image_or_text(user_id, la_category, "没有可用的乐曲数据")
        return
    
    # 判断是分类还是章节前缀
    if category_or_chapter in category_map:
        # 是分类
        category = category_map[category_or_chapter]
        filtered_songs = [song for song in song_data if song['category'] == category]
    else:
        # 是章节前缀
        filtered_songs = [song for song in song_data if song['chapter'].split('-')[0].lower() == category_or_chapter.lower()]
    
    if not filtered_songs:
        await send_image_or_text(user_id, la_category, f"没有找到分类或章节为[{category_or_chapter}]的列表")
        return
    
    # 检查范围是否有效
    total_songs = len(filtered_songs)
    if min_val > total_songs:
        await send_image_or_text(user_id, la_category, f"最小值{min_val}超过了该分类的歌曲总数({total_songs})")
        return
    
    # 调整最大值为实际最大值或100
    max_val = min(max_val, total_songs, min_val + 99)  # 最多显示100首
    
    # 获取范围内的歌曲
    songs_to_show = filtered_songs[min_val-1:max_val]
    
    # 构建消息
    message = f"分类/章节: {category_or_chapter} (显示 {min_val}-{max_val}/{total_songs} 首)\n"
    
    # 按章节分组显示
    current_chapter_prefix = None
    for i, song in enumerate(songs_to_show, min_val):
        chapter_prefix = song['chapter'].split('-')[0]
        
        # 如果章节前缀变化，添加换行
        if chapter_prefix != current_chapter_prefix:
            message += "\n"
            current_chapter_prefix = chapter_prefix
        
        message += f"{i}. {song['chapter']} -|- {song['title']} (ID: {song['id']})\n"
    
    if len(songs_to_show) < (max_val - min_val + 1):
        message += f"\n(仅显示前{len(songs_to_show)}首)"
    
    await send_image_or_text(user_id, la_category, message.strip())

# 处理help命令
help_categories = {
    "daily": {
        "name": "今日乐曲",
        "aliases": ["today", "今日曲"],
        "commands": [
            "/la today - 获取今日随机乐曲(每天固定)",
            "/la 今日曲 - 同上"
        ],
        "examples": [
            "/la today"
        ]
    },
    "random": {
        "name": "随机乐曲",
        "aliases": ["random", "随机"],
        "commands": [
            "/la random - 随机获取一首乐曲",
            "/la random level <难度> - 随机指定难度的乐曲",
            "/la random <分类> - 随机指定分类的乐曲"
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
            "/la alias show <搜索词> - 查看乐曲别名"
        ],
        "examples": []
    },
    "search": {
        "name": "查找乐曲",
        "aliases": ["info", "查找", "find"],
        "commands": [
            "/la info - 查找乐曲信息",
            "/la find - 同上"
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
    "calculate": {
        "name": "定数计算功能",
        "aliases": ["cal", "计算", "定数"],
        "commands": [
            "/la cal harmony数目/tune数目/fail数目/难度/曲目 - 根据曲目计算rating",
            "/la cal harmony数目/tune数目/fail数目/物量/等级 - 直接计算rating"
        ],
        "priority": [
            "1. 前三个参数必须是数字",
            "2. 难度可以是: Whisper, Acoustic, Ultra, Master",
            "3. 等级可以是: 1-16, 13+, 14+, 15+, 16+",
            "4. 如果输入的物量之和不正确，将自动补到fail数目"
        ],
        "examples": [
            "/la cal 900/300/50/Master/8-6",
            "/la cal 900/300/50/2000/16"
        ]
    },
    "category": {
        "name": "分类查询",
        "aliases": ["category", "分类", "cate"],
        "commands": [
            "/la category <分类> [min[/max]] - 显示指定分类的歌曲",
            "/la cate - 同上"
        ],
        "examples": [
            "/la category 0 5 - 显示第0章前5首",
            "/la category x - 显示分类x的所有曲目(最多100首)",
            "/la category inf 101/200 - 显示inf分类的第101-200首"
        ]
    },
    "stats": {
        "name": "其它功能",
        "aliases": ["other", "其它"],
        "commands": [
            "/la time - 显示长于3分钟和短于2分钟的乐曲列表",
            "/la all - 显示曲库统计信息",
            "/la notes - 物量最多的前50个谱面",
            "/la rating - 显示当前的Max Rating，并且给出可能的B30和R5"
        ],
        "examples": [
            "/la time",
            "/la all",
            "/la notes",
            "/la rating"
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