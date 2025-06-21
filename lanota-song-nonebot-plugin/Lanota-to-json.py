# 不用看这个，废弃了

import re
import json
from pathlib import Path

def clean_line(line):
    line = re.sub(r'data.*?\|', '', line)
    line = re.sub(r"'''(.*?)'''", r'\1', line)
    line = re.sub(r'\|\[\[(.*?)\]\]', r'\1', line)
    line = re.sub(r'\|-', '', line)
    return line.strip()

def get_category(part):
    sections = part.split('-')
    left_side = sections[0].strip()
    
    if left_side.isdigit():
        return "main"
    elif re.match(r'[a-zA-Z]+[0-9]+', left_side):
        return "side"
    elif re.match(r'^[a-zA-Z]{1,2}$', left_side):
        return "expansion"
    elif left_side.lower() == "event":
        return "event"
    elif left_side == "∞":
        return "subscription"
    else:
        return "other"

def parse_line(line, song_id):
    cleaned = clean_line(line)
    if not cleaned:
        return None, song_id
    
    parts = cleaned.split('||')
    if len(parts) != 10:
        return None, song_id
    
    category = get_category(parts[2])
    
    song_data = {
        "id": song_id,
        "title": parts[0].strip(),
        "artist": parts[1].strip(),
        "chapter": parts[2].strip(),
        "difficulty": {
            "whisper": parts[3].strip(),
            "acoustic": parts[4].strip(),
            "ultra": parts[5].strip(),
            "master": parts[6].strip()
        },
        "time": parts[7].strip(),
        "bpm": parts[8].strip(),
        "version": parts[9].strip(),
        "category": category
    }
    
    return song_data, song_id + 1  # 返回当前歌曲数据和下一个ID

def convert_to_json(input_file):
    results = {
        "main": [],
        "side": [],
        "expansion": [],
        "event": [],
        "subscription": [],
        "other": []
    }
    
    current_id = 1  # ID计数器从1开始
    
    with open(input_file, 'r', encoding='utf-8') as file:
        for line in file:
            if not line.strip() or line.startswith('!'):
                continue
            
            entry, current_id = parse_line(line, current_id)  # 传递和接收更新后的ID
            if entry:
                # 只在chapter字段中替换∞为inf
                if 'chapter' in entry:
                    entry['chapter'] = entry['chapter'].replace('∞', 'inf')
                
                category = entry.pop("category")
                results[category].append(entry)
                
    return results

def get_input_path():
    """交互式获取文件路径"""
    while True:
        path = input("请输入TXT文件路径（或拖拽文件到此处）：").strip(' "\'')
        if not path:
            print("路径不能为空，请重新输入")
            continue
            
        path = Path(path)
        if not path.exists():
            print(f"错误：路径 '{path}' 不存在")
            continue
        if path.suffix != '.txt':
            print(f"错误：仅支持.txt文件（当前文件：{path.suffix}）")
            continue
            
        return path

if __name__ == "__main__":
    try:
        print("=== TXT转JSON工具 ===")
        input_path = get_input_path()
        print(f"正在处理文件: {input_path}")
        
        json_data = convert_to_json(input_path)
        
        # 自动生成输出路径（同目录下同名.json文件）
        output_path = input_path.with_suffix('.json')
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, indent=2, ensure_ascii=False)
            
        print(f"转换完成！结果已保存到: {output_path}")
        print("按Enter键退出...")
        input()
        
    except Exception as e:
        print(f"处理失败: {str(e)}")
        print("按Enter键退出...")
        input()