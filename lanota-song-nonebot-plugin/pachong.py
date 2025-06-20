import requests
from bs4 import BeautifulSoup
import time
import json
import os
import re

def classify_song(chapter_str):
    """根据章节字符串分类歌曲"""
    if not chapter_str:
        return "other"
    
    # 处理∞/inf情况
    normalized = chapter_str.lower().replace('∞', 'inf')
    if normalized == "inf":
        return "subscription"
    
    # 分割章节字符串
    parts = re.split(r'[-_]', chapter_str)
    if len(parts) < 3:
        return "other"
    
    # 获取第三部分并分割
    third_part = parts[2]
    sub_parts = third_part.split('-')
    left_part = sub_parts[0].lower()
    
    # 分类逻辑
    if left_part.isdigit():
        return "main"
    elif re.fullmatch(r'[a-z]+\d+', left_part):
        return "side"
    elif re.fullmatch(r'[a-z]{1,2}', left_part):
        return "expansion"
    elif left_part == "event":
        return "event"
    elif left_part == "inf":
        return "subscription"
    else:
        return "other"

def sanitize_chapter(chapter_str):
    """将∞替换为inf并清理字符串"""
    if not chapter_str:
        return ""
    return chapter_str.replace('∞', 'inf').strip()

def get_song_details(song_url, song_id):
    try:
        response = requests.get(song_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 初始化歌曲数据字典
            song_data = {
                "id": song_id,
                "title": "",
                "artist": "",
                "chapter": "",
                "category": "other",  # 默认分类
                "difficulty": {
                    "whisper": "",
                    "acoustic": "",
                    "ultra": "",
                    "master": ""
                },
                "time": "",
                "bpm": "",
                "version": "",
                "area": "",
                "genre": "",
                "vocals": "",
                "chart_design": "",
                "cover_art": "",
                "notes": {
                    "whisper": "",
                    "acoustic": "",
                    "ultra": "",
                    "master": ""
                }
            }
            
            # 获取歌曲标题和艺术家
            title_tag = soup.find('h1', {'class': 'page-header__title'})
            if title_tag:
                title_parts = [part.strip() for part in title_tag.get_text().split('|') if part.strip()]
                song_data["title"] = title_parts[0] if len(title_parts) > 0 else ""
                song_data["artist"] = title_parts[1] if len(title_parts) > 1 else ""
            
            # 获取主信息表格
            info_table = soup.find('table', {'class': 'wikitable'})
            if info_table:
                rows = info_table.find_all('tr')
                
                # 确保表格有足够的行
                if len(rows) >= 6:
                    # 提取基本信息行
                    try:
                        # 第一行: Area, Chapter, Genre
                        cells = rows[0].find_all('td')
                        song_data["area"] = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        chapter = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                        song_data["chapter"] = sanitize_chapter(chapter)
                        song_data["category"] = classify_song(song_data["chapter"])
                        song_data["genre"] = cells[5].get_text(strip=True) if len(cells) > 5 else ""
                        
                        # 第二行: BPM, Time, Vocals
                        cells = rows[1].find_all('td')
                        song_data["bpm"] = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        song_data["time"] = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                        song_data["vocals"] = cells[5].get_text(strip=True) if len(cells) > 5 else ""
                        
                        # 第三行: Chart Design, Cover Art
                        cells = rows[2].find_all('td')
                        song_data["chart_design"] = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        song_data["cover_art"] = cells[3].get_text(strip=True) if len(cells) > 3 else ""
                        
                        # 第四行: Version
                        cells = rows[3].find_all('td')
                        song_data["version"] = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                        
                        # 第五行: Difficulty
                        cells = rows[4].find_all('td')[1:]  # 跳过第一个"Difficulty"单元格
                        difficulties = [cell.get_text(strip=True).lower() for cell in cells]
                        
                        # 第六行: Level
                        cells = rows[5].find_all('td')[1:]  # 跳过第一个"Level"单元格
                        levels = [cell.get_text(strip=True) for cell in cells]
                        
                        # 第七行: Notes
                        cells = rows[6].find_all('td')[1:]  # 跳过第一个"Notes"单元格
                        notes = [cell.get_text(strip=True) for cell in cells]
                        
                        # 填充难度和音符数据
                        for i, diff in enumerate(difficulties):
                            if i < len(levels) and diff in song_data["difficulty"]:
                                song_data["difficulty"][diff] = levels[i]
                            if i < len(notes) and diff in song_data["notes"]:
                                song_data["notes"][diff] = notes[i]
                        
                    except Exception as e:
                        print(f"Error parsing table for {song_url}: {str(e)}")
                        return None
                    
                    return song_data
        return None
    except Exception as e:
        print(f"Error processing {song_url}: {str(e)}")
        return None

def save_to_json(data, filename='lanota_songs.json'):
    """保存数据到JSON文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    base_url = "https://lanota.fandom.com/wiki/Songs"
    output_file = 'lanota_songs.json'
    all_songs_data = []
    
    # 如果文件已存在，加载已有数据
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                all_songs_data = json.load(f)
            print(f"Loaded existing data with {len(all_songs_data)} songs")
        except:
            all_songs_data = []
    
    try:
        # 获取主页面
        print("Fetching main song list...")
        response = requests.get(base_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            song_table = soup.find('table', {'class': 'wikitable'})
            
            if song_table:
                # 提取所有歌曲链接
                rows = song_table.find_all('tr')[1:]  # 跳过表头
                total_songs = len(rows)
                print(f"Found {total_songs} songs to process")
                
                # 从上次停止的地方继续，或者从1开始
                start_id = len(all_songs_data) + 1 if all_songs_data else 1
                
                for i, row in enumerate(rows[start_id-1:], start_id):
                    cols = row.find_all('td')
                    if cols and len(cols) > 0:
                        title_cell = cols[0]
                        link = title_cell.find('a')
                        if link and link.has_attr('href'):
                            song_url = "https://lanota.fandom.com" + link['href']
                            title = link.text.strip()
                            
                            print(f"Processing {i}/{total_songs}: {title}")
                            details = get_song_details(song_url, i)
                            
                            if details:
                                all_songs_data.append(details)
                                # 每次成功爬取后都保存到文件
                                save_to_json(all_songs_data, output_file)
                                print(f"Successfully processed and saved (ID: {i}, Category: {details['category']})")
                            else:
                                print("Skipped due to processing error")
                            
                            time.sleep(1)  # 礼貌性延迟
                
                # 分类统计
                category_count = {}
                for song in all_songs_data:
                    category = song.get('category', 'other')
                    category_count[category] = category_count.get(category, 0) + 1
                
                print("\n=== Classification Summary ===")
                for cat, count in category_count.items():
                    print(f"{cat}: {count} songs")
                
                print(f"\nFinished! Total songs processed: {len(all_songs_data)}")
                print(f"Data saved to {output_file}")
            else:
                print("Could not find the songs table on the page.")
        else:
            print(f"Failed to access main page (HTTP {response.status_code})")
    except Exception as e:
        print(f"Error: {str(e)}")
        # 出错时也尝试保存已收集的数据
        if all_songs_data:
            save_to_json(all_songs_data, output_file)
            print(f"Saved {len(all_songs_data)} songs before error occurred")

if __name__ == "__main__":
    main()