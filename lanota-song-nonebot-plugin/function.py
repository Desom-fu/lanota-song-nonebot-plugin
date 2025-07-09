from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11 import MessageSegment, Message
from .config import *
from pathlib import Path
import random
import datetime
import json
import threading
import json

# 创建同步锁
lock = threading.Lock()

def init_data():
    """初始化全部数据文件"""
    user_path.mkdir(parents=True, exist_ok=True)
    save_dir.mkdir(parents=True, exist_ok=True)
    backup_path.mkdir(parents=True, exist_ok=True)
    lanota_data_path.mkdir(parents=True, exist_ok=True)
    if not full_path.exists():
        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    if not lanota_alias_full_path.exists():
        with open(full_path, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    if not lanota_table_full_path.exists():
        with open(lanota_table_full_path, 'w', encoding='utf-8') as f:
            json.dump({}, f)
    if not lanota_full_path.exists():
        with open(lanota_full_path, 'w', encoding='utf-8') as f:
            json.dump([], f)

def extract_mixed_qq(args: Message, param_count: int) -> list:
    """解析混合包含@消息和纯文本的参数"""
    arg_list = []
    text_args = args.extract_plain_text().strip().split()
    text_ptr = 0
    
    for seg in args:
        if seg.type == 'at':
            arg_list.append(seg.data['qq'])
        elif seg.type == 'text':
            seg_text = seg.data['text'].strip()
            if seg_text:
                for word in seg_text.split():
                    if text_ptr < len(text_args) and word == text_args[text_ptr]:
                        arg_list.append(word)
                        text_ptr += 1
    
    if len(arg_list) != param_count:
        return []
    return arg_list

async def get_nickname(bot: Bot, user_id: str) -> str:
    try:
        user_info = await bot.get_stranger_info(user_id=int(user_id))
        return user_info.get("nickname", f"{user_id}")
    except:
        return f"玩家{user_id}"

def get_alias_name(name, item_dict, alias_dict):
    """智能别名匹配"""
    if name in item_dict:
        return name
    
    for std_name in alias_dict.keys():
        if std_name in name:
            return None
    
    max_len = max(len(alias) for aliases in alias_dict.values() for alias in aliases) if alias_dict else 0
    best_match = None
    best_len = 0
    
    for i in range(len(name)):
        for l in range(min(max_len, len(name) - i), 0, -1):
            substring = name[i:i+l]
            
            for std_name, aliases in alias_dict.items():
                if substring in aliases and l > best_len:
                    best_match = (i, l, std_name)
                    best_len = l
    
    if best_match:
        i, l, std_name = best_match
        return name[:i] + std_name + name[i+l:]
    
    return None

def open_data(file):
    data = {}
    with lock:
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    return data

def save_data(file, data):
    with lock:
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
def save_alias_data(alias_data):
    try:
        with open(lanota_alias_full_path, 'w', encoding='utf-8') as f:
            json.dump(alias_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"保存别名数据失败: {str(e)}")

def get_today_seed():
    today = datetime.date.today()
    return int(today.strftime("%Y%m%d"))

def get_user_today_song(user_id: str):
    user_data = open_data(full_path)
    today_seed = get_today_seed()
    
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {}
    
    user_info = user_data[str(user_id)]
    
    # 检查是否有今日曲目且日期匹配
    if "today_chapter" in user_info and "today_date" in user_info:
        if user_info["today_date"] == today_seed:
            # 根据存储的chapter查找歌曲
            chapter = user_info["today_chapter"].lower()
            song_data = load_song_data()
            for song in song_data:
                if song['chapter'].lower() == chapter:
                    return song
            return None
    
    # 需要生成新的今日曲目
    song_data = load_song_data()
    
    if not song_data:
        return None
    
    # 使用日期作为随机种子
    random.seed(today_seed + int(user_id))
    today_song = random.choice(song_data)
    
    # 只存储chapter和日期
    user_info["today_chapter"] = today_song['chapter']
    user_info["today_date"] = today_seed
    save_data(full_path, user_data)
    
    return today_song

def load_table_data():
    """加载定数表数据"""
    try:
        with open(lanota_table_full_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载定数表数据失败: {str(e)}")
        return {}

def format_song_info(song):
    """处理歌曲格式"""
    # 处理数据的辅助函数
    def get_value(value):
        if not value or str(value).strip().lower() in ["none", "no", "n/a", "unknown", "未知", '', "no info"]:
            return "未知"
        return value
    
    def get_chinese(value):
        if value == "main":
            return "主线"
        elif value == "side":
            return "支线"
        elif value == "expansion":
            return "曲包"
        elif value == "event":
            return "活动"
        elif value == "subscription":
            return "书房"
        else:
            return value
    
    table_data = load_table_data()
    
    # 获取章节定数
    chapter = get_value(song.get('chapter'))
    chapter_difficulty = {}
    if chapter:
        # 定数表 table_data
        chapter_difficulty = table_data.get(chapter, {})
    
    # 获取旧谱信息
    legacy_info = song.get('Legacy', {})
    
    # 难度信息格式化函数
    def format_difficulty_info(diff_type):
        """格式化难度信息"""
        # 获取难度值
        difficulty_value = song['difficulty'].get(diff_type)
        # 获取物量值
        notes_value = song['notes'].get(diff_type)
        # 获取定数
        table_key = diff_type.capitalize()
        table_diff = chapter_difficulty.get(table_key)
        
        diff_str = get_value(difficulty_value)
        notes_str = f"物量: {get_value(notes_value)}"
        
        if table_diff:
            return f"{diff_str}({table_diff}) ({notes_str})"
        return f"{diff_str} ({notes_str})"
    
    # 旧谱难度格式化函数
    def format_legacy_difficulty(diff_key, max_key):
        """格式化旧谱难度信息"""
        diff_value = legacy_info.get(diff_key)
        max_value = legacy_info.get(max_key)
        
        if diff_value or max_value:
            return f"{get_value(diff_value)} (物量: {get_value(max_value)})"
        return "无信息"
    
    # 构建信息主体
    info_lines = [
        "══════════ 歌曲信息 ══════════",
        f"▪ 歌曲ID: {get_value(song.get('id'))}",
        f"▪ 曲名: {get_value(song.get('title'))}",
        f"▪ 分类: {get_chinese(song.get('category'))}",
        f"▪ 章节: {chapter}",
        f"▪ 曲师: {get_value(song.get('artist'))}",
        f"▪ 歌手: {get_value(song.get('vocals'))}",
        f"▪ 曲风: {get_value(song.get('genre'))}",
        f"▪ 歌曲BPM: {get_value(song.get('bpm'))}",
        f"▪ 时长: {get_value(song.get('time'))}",
        f"▪ 更新版本: {get_value(song.get('version'))}",
        "══════════ 难度信息 ══════════",
        f"▪ 谱师: {get_value(song.get('chart_design'))}",
        f"    ┌ Whisper: {format_difficulty_info('whisper')}",
        f"    ├ Acoustic: {format_difficulty_info('acoustic')}",
        f"    ├ Ultra: {format_difficulty_info('ultra')}",
        f"    └ Master: {format_difficulty_info('master')}",
    ]
    
    # 添加旧谱信息（如果有）
    if legacy_info:
        info_lines.extend([
            "══════════ 旧谱信息 ══════════",
            f"▪ 谱师: {get_value(legacy_info.get('Chart Design'))}",
            f"    ┌ Whisper: {format_legacy_difficulty('DiffWhisper', 'MaxWhisper')}",
            f"    ├ Acoustic: {format_legacy_difficulty('DiffAcoustic', 'MaxAcoustic')}",
            f"    ├ Ultra: {format_legacy_difficulty('DiffUltra', 'MaxUltra')}",
            f"    └ Master: {format_legacy_difficulty('DiffMaster', 'MaxMaster')}",
        ])
    
    # 添加其他信息
    info_lines.extend([
        "══════════ 其他信息 ══════════",
        f"▪ 全曲列表: https://lanota.fandom.com/wiki/Songs",
        f"▪ 信息来源: {get_value(song.get('source_url'))}",
        "═════════════════════════"
    ])
    
    # 合并所有行并返回
    return "\n".join(info_lines)

async def get_random_number_from_org(min_num, max_num):
    try:
        import requests
        url = f"https://www.random.org/integers/?num=1&min={min_num}&max={max_num}&col=1&base=10&format=plain&rnd=new"
        response = requests.get(url)
        if response.status_code == 200:
            return int(response.text.strip())
    except:
        pass
    return random.randint(min_num, max_num)

def load_song_data():
    """加载歌曲数据"""
    try:
        with open(lanota_full_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载歌曲数据失败: {str(e)}")
        return []

def load_alias_data():
    """加载别名数据"""
    try:
        if not lanota_alias_full_path.exists():
            return {}
        
        with open(lanota_alias_full_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"加载别名数据失败: {str(e)}")
        return {}

def get_songs_by_category(song_data, category):
    """按分类获取歌曲"""
    return [song for song in song_data if song['category'] == category]

def get_songs_by_level(song_data, level):
    """按难度获取歌曲"""
    return [song for song in song_data 
            if (song['difficulty']['whisper'] == level or
                song['difficulty']['acoustic'] == level or
                song['difficulty']['ultra'] == level or
                song['difficulty']['master'] == level)]

def find_song_by_search_term(search_term, song_data, alias_data=None, max_display=10):
    """按照优先级查找歌曲
    Args:
        search_term: 搜索词
        song_data: 歌曲数据
        alias_data: 别名数据(可选)
        max_display: 最大显示数量
    Returns:
        tuple: (matched_songs, match_type, total_count)
    """
    if alias_data is None:
        alias_data = load_alias_data()
    
    matched_songs = []
    match_type = None
    
    # 1. 完全匹配章节号
    chapter_matches = [song for song in song_data if song['chapter'].lower() == search_term.lower()]
    if chapter_matches:
        matched_songs = chapter_matches
        match_type = "章节号匹配"
    
    # 2. 完全匹配ID
    if not matched_songs:
        try:
            song_id = int(search_term)
            id_matches = [song for song in song_data if song['id'] == song_id]
            if id_matches:
                matched_songs = id_matches
                match_type = "ID匹配"
        except ValueError:
            pass
    
    # 3. 完全匹配别名
    if not matched_songs and alias_data:
        alias_matches = []
        for song in song_data:
            std_name = song['title']
            if std_name in alias_data and search_term.lower() in [a.lower() for a in alias_data[std_name]]:
                alias_matches.append(song)
        if alias_matches:
            matched_songs = alias_matches
            match_type = "别名匹配"
    
    # 4. 完全匹配曲名
    if not matched_songs:
        title_matches = [song for song in song_data if song['title'].lower() == search_term.lower()]
        if title_matches:
            matched_songs = title_matches
            match_type = "曲名匹配"
    
    # 5. 模糊匹配曲名或别名
    if not matched_songs:
        search_term_lower = search_term.lower()
        # 模糊匹配曲名
        title_fuzzy_matches = [song for song in song_data if search_term_lower in song['title'].lower()]
        # 模糊匹配别名
        alias_fuzzy_matches = []
        if alias_data:
            for song in song_data:
                std_name = song['title']
                if std_name in alias_data:
                    for alias in alias_data[std_name]:
                        if search_term_lower in alias.lower():
                            alias_fuzzy_matches.append(song)
                            break
        # 合并结果并去重
        matched_songs = list({song['id']: song for song in title_fuzzy_matches + alias_fuzzy_matches}.values())
        if matched_songs:
            match_type = "模糊搜索"
    
    total_count = len(matched_songs)
    if total_count > max_display:
        matched_songs = matched_songs[:max_display]
    
    return matched_songs, match_type, total_count

def calculate_rating(harmony: int, tune: int, fail: int, notes: int, level: str) -> tuple:
    """
    计算单曲 rating
    :param harmony: harmony 数目
    :param tune: tune 数目
    :param fail: fail 数目
    :param notes: 总物量
    :param level: 难度等级 (1-16, 13+, 14+, 15+, 16+)
    :return: (rating, adjusted_fail, adjustment, is_exceeded, is_negative, bonus, base_level) 元组
    """
    try:
        notes = int(notes)  # 确保notes是整数
    except (ValueError, TypeError):
        return (0.0, fail, 0, False, False, 0, 0)
    
    # 验证输入是否为负数
    if harmony < 0 or tune < 0 or fail < 0 or notes < 0:
        return (0.0, fail, 0, False, True, 0, 0)
    
    # 验证其他输入
    if not (harmony >= 0 and tune >= 0 and fail >= 0 and notes > 0):
        return (0.0, fail, 0, False, False, 0, 0)
    
    input_total = harmony + tune + fail
    
    # 检查输入物量是否超过总物量
    if input_total > notes:
        return (0.0, fail, 0, True, False, 0, 0)
    
    # 解析难度等级
    base_level = 0.0
    bonus = 0.0
    
    if level.endswith('+'):
        try:
            base_level = float(level[:-1])
        except ValueError:
            return (0.0, fail, 0, False, False, 0, 0)
        
        if level == '13+':
            bonus = 0.5
        elif level == '14+':
            bonus = 0.5
        elif level == '15+':
            bonus = 0.75
        elif level == '16+':
            bonus = 1.25
    else:
        try:
            base_level = float(level)
        except ValueError:
            return (0.0, fail, 0, False, False, 0, 0)

        if base_level == 16:
            bonus = 0.5
        else:
            bonus = 0  # 其他等级无加成
    
    # 验证难度范围
    if not (1 <= base_level <= 16):
        return (0.0, fail, 0, False, False, 0, 0)
    
    # 计算物量调整
    adjustment = 0
    adjusted_fail = fail
    
    if input_total != notes:
        adjustment = notes - (harmony + tune + fail)
        adjusted_fail = fail + adjustment
    
    # 计算 rating
    rating = (harmony + tune / 3) / notes * (base_level + 1 + bonus)
    return (round(rating, 5), adjusted_fail, adjustment, False, False, bonus, base_level)