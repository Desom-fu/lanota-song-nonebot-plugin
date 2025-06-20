from nonebot.log import logger
from nonebot import get_driver
from nonebot.adapters.onebot.v11 import Bot
from nonebot.adapters.onebot.v11 import MessageSegment, Message
from .config import *
from pathlib import Path
import random
import math
import re
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
            json.dump({}, f)


def extract_mixed_qq(args: Message, param_count: int) -> list:
    """解析混合包含@消息和纯文本的参数
    :param args: 原始消息对象
    :param param_count: 期望的参数数量
    :return: 参数列表(QQ号或文本)，若参数数量不匹配则返回空列表
    """
    arg_list = []
    text_args = args.extract_plain_text().strip().split()
    text_ptr = 0  # 纯文本参数的指针
    
    # 遍历所有消息段
    for seg in args:
        if seg.type == 'at':
            arg_list.append(seg.data['qq'])
        elif seg.type == 'text':
            # 处理纯文本部分
            seg_text = seg.data['text'].strip()
            if seg_text:  # 非空文本
                for word in seg_text.split():
                    if text_ptr < len(text_args) and word == text_args[text_ptr]:
                        arg_list.append(word)
                        text_ptr += 1
    
    # 参数数量验证
    if len(arg_list) != param_count:
        return []
    return arg_list

# 获取QQ昵称
async def get_nickname(bot: Bot, user_id: str) -> str:
    try:
        user_info = await bot.get_stranger_info(user_id=int(user_id))
        return user_info.get("nickname", f"{user_id}")
    except:
        return f"玩家{user_id}"  # 获取失败时使用默认名称

# 辅助函数：获取标准名称
def get_alias_name(name, item_dict, alias_dict):
    """
    智能别名匹配（支持任意位置的别名替换）
    修改后的逻辑：
        1. 直接匹配完整名称（优先检查）
        2. 检查字符串中是否已经包含任何全称，如果有则返回None
        3. 扫描整个字符串，查找最长的别名匹配
        4. 替换匹配到的别名，保留其余部分
    """
    # 1. 直接匹配完整名称（优先检查）
    if name in item_dict:
        return name
    
    # 2. 检查字符串中是否已经包含任何全称
    for std_name in alias_dict.keys():
        if std_name in name:
            return None  # 如果已经包含全称，则不进行别名匹配
    
    max_len = max(len(alias) for aliases in alias_dict.values() for alias in aliases) if alias_dict else 0
    best_match = None
    best_len = 0
    
    # 3. 扫描整个字符串，查找最长的别名匹配
    for i in range(len(name)):
        for l in range(min(max_len, len(name) - i), 0, -1):
            substring = name[i:i+l]
            
            for std_name, aliases in alias_dict.items():
                if substring in aliases and l > best_len:
                    best_match = (i, l, std_name)
                    best_len = l
    
    # 4. 替换匹配到的别名
    if best_match:
        i, l, std_name = best_match
        return name[:i] + std_name + name[i+l:]
    
    return None  # 未找到匹配

# 打开数据文件
def open_data(file):
    data = {}
    with lock:  # 在读写文件时加锁，确保只有一个线程/协程能执行此操作
        with open(file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    return data

# 保存数据结构到数据文件内
def save_data(file, data):
    with lock:  # 在读写文件时加锁，确保只有一个线程/协程能执行此操作
        with open(file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
            
# 保存别名数据
def save_alias_data(alias_data):
    """保存别名数据"""
    try:
        with open(lanota_alias_full_path, 'w', encoding='utf-8') as f:
            json.dump(alias_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"保存别名数据失败: {str(e)}")

# 获取今日日期作为随机种子
def get_today_seed():
    """获取今日日期作为随机种子"""
    today = datetime.date.today()
    return int(today.strftime("%Y%m%d"))

# 获取用户今日曲目
def get_user_today_song(user_id: str):
    """获取用户今日曲目"""
    user_data = open_data(full_path)
    today_seed = get_today_seed()
    
    if str(user_id) not in user_data:
        user_data[str(user_id)] = {}
    
    user_info = user_data[str(user_id)]
    
    # 检查是否有今日曲目且日期匹配
    if "today_song" in user_info and "today_date" in user_info:
        if user_info["today_date"] == today_seed:
            return user_info["today_song"]
    
    # 需要生成新的今日曲目
    song_data = load_song_data()
    all_songs = []
    for category in song_data.values():
        all_songs.extend(category)
    
    if not all_songs:
        return None
    
    # 使用日期作为随机种子
    random.seed(today_seed + int(user_id))
    today_song = random.choice(all_songs)
    
    # 保存到用户数据
    user_info["today_song"] = today_song
    user_info["today_date"] = today_seed
    save_data(full_path, user_data)
    
    return today_song

# 格式化歌曲信息
def format_song_info(song):
    """格式化歌曲信息为字符串"""
    if not song:
        return "未找到歌曲信息"
    
    return (
        f"ID: {song['id']}\n"
        f"章节: {song['chapter']}\n"
        f"曲名: {song['title']}\n"
        f"曲师: {song['artist']}\n"
        f"难度: \n"
        f"    - Whisper: {song['difficulty']['whisper']}\n"
        f"    - Acoustic: {song['difficulty']['acoustic']}\n"
        f"    - Ultra: {song['difficulty']['ultra']}\n"
        f"    - Master: {song['difficulty']['master']}\n"
        f"时长: {song['time']}\n"
        f"BPM: {song['bpm']}\n"
        f"版本: {song['version']}"
    )

# 从random.org获取随机数
async def get_random_number_from_org(min_num, max_num):
    """从random.org获取随机数"""
    try:
        import requests
        url = f"https://www.random.org/integers/?num=1&min={min_num}&max={max_num}&col=1&base=10&format=plain&rnd=new"
        response = requests.get(url)
        if response.status_code == 200:
            return int(response.text.strip())
    except:
        pass
    return random.randint(min_num, max_num)

# 加载歌曲数据
def load_song_data():
    """加载歌曲数据和别名数据"""
    try:
        with open(lanota_full_path, 'r', encoding='utf-8') as f:
            song_data = json.load(f)
        
        # 确保所有分类都存在
        for category in ["main", "side", "expansion", "event", "subscription"]:
            if category not in song_data:
                song_data[category] = []
        
        return song_data
    except Exception as e:
        print(f"加载歌曲数据失败: {str(e)}")
        return {
            "main": [],
            "side": [],
            "expansion": [],
            "event": [],
            "subscription": []
        }

# 加载别名数据
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