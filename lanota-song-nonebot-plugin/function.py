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

def format_song_info(song):
    """格式化歌曲信息为字符串，空值显示为未知"""
    if not song:
        return "未找到歌曲信息"
    
    # 为所有可能为空的字段设置默认值
    def get_value(value):
        return value if value and str(value).strip() else "N/A"
    
    # 处理Legacy数据
    legacy_info = song.get('Legacy', {})
    
    info = (
        f"歌曲ID: {song['id']}\n"
        f"章节: {get_value(song['chapter'])}\n"
        f"分类: {get_value(song['category'])}\n"
        f"曲名: {get_value(song['title'])}\n"
        f"曲风: {get_value(song['genre'])}\n"
        f"曲师: {get_value(song['artist'])}\n"
        f"歌手: {get_value(song['vocals'])}\n"
        f"谱师: {get_value(song['chart_design'])}\n"
        f"难度: \n"
        f"    - Whisper: {get_value(song['difficulty']['whisper'])} (物量: {get_value(song['notes']['whisper'])})\n"
        f"    - Acoustic: {get_value(song['difficulty']['acoustic'])} (物量: {get_value(song['notes']['acoustic'])})\n"
        f"    - Ultra: {get_value(song['difficulty']['ultra'])} (物量: {get_value(song['notes']['ultra'])})\n"
        f"    - Master: {get_value(song['difficulty']['master'])} (物量: {get_value(song['notes']['master'])})\n"
    )
    
    # 添加Legacy信息
    if legacy_info:
        info += "旧谱信息:\n"
        info += f"    旧谱谱师: {get_value(legacy_info.get('Chart Design'))}\n"
        
        if any(key in legacy_info for key in ['DiffWhisper', 'DiffAcoustic', 'DiffUltra', 'DiffMaster']):
            info += "    旧谱难度:\n"
            info += f"        - Whisper: {get_value(legacy_info.get('DiffWhisper'))} (物量: {get_value(legacy_info.get('MaxWhisper'))})\n"
            info += f"        - Acoustic: {get_value(legacy_info.get('DiffAcoustic'))} (物量: {get_value(legacy_info.get('MaxAcoustic'))})\n"
            info += f"        - Ultra: {get_value(legacy_info.get('DiffUltra'))} (物量: {get_value(legacy_info.get('MaxUltra'))})\n"
            info += f"        - Master: {get_value(legacy_info.get('DiffMaster'))} (物量: {get_value(legacy_info.get('MaxMaster'))})\n"
    
    info += (
        f"时长: {get_value(song['time'])}\n"
        f"BPM: {get_value(song['bpm'])}\n"
        f"版本: {get_value(song['version'])}"
    )
    
    return info

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
        match_type = "章节号"
    
    # 2. 完全匹配ID
    if not matched_songs:
        try:
            song_id = int(search_term)
            id_matches = [song for song in song_data if song['id'] == song_id]
            if id_matches:
                matched_songs = id_matches
                match_type = "ID"
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
            match_type = "别名"
    
    # 4. 完全匹配曲名
    if not matched_songs:
        title_matches = [song for song in song_data if song['title'].lower() == search_term.lower()]
        if title_matches:
            matched_songs = title_matches
            match_type = "曲名"
    
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
            match_type = "模糊匹配"
    
    total_count = len(matched_songs)
    if total_count > max_display:
        matched_songs = matched_songs[:max_display]
    
    return matched_songs, match_type, total_count