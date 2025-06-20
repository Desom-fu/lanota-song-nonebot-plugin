import requests
from bs4 import BeautifulSoup
import time
import os
import json

def get_song_details(song_url):
    try:
        response = requests.get(song_url)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 初始化字典存储所有信息
            song_data = {
                'title': '',
                'artist': '',
                'basic_info': {},
                'difficulty_info': {}
            }
            
            # 获取歌曲标题和艺术家
            title_tag = soup.find('h1', {'class': 'page-header__title'})
            if title_tag:
                title_parts = title_tag.get_text(strip=True).split('|')
                song_data['title'] = title_parts[0].strip()
                if len(title_parts) > 1:
                    song_data['artist'] = title_parts[1].strip()
            
            # 获取主信息表格
            info_table = soup.find('table', {'class': 'wikitable'})
            if info_table:
                rows = info_table.find_all('tr')
                
                # 确保表格有足够的行
                if len(rows) >= 6:
                    # 提取基本信息
                    song_data['basic_info'] = {
                        'Area': safe_extract(rows[0], 1),
                        'Chapter': safe_extract(rows[0], 3),
                        'Genre': safe_extract(rows[0], 5),
                        'BPM': safe_extract(rows[1], 1),
                        'Time': safe_extract(rows[1], 3),
                        'Vocals': safe_extract(rows[1], 5),
                        'Chart Design': safe_extract(rows[2], 1),
                        'Cover Art': safe_extract(rows[2], 3),
                        'Version': safe_extract(rows[3], 1) if len(rows) > 3 else 'No Info'
                    }
                    
                    # 提取难度信息
                    if len(rows) >= 6:
                        difficulties = safe_extract_list(rows[4], slice(1, None))  # 跳过第一个"Difficulty"单元格
                        levels = safe_extract_list(rows[5], slice(1, None))       # 跳过第一个"Level"单元格
                        notes = safe_extract_list(rows[6], slice(1, None))       # 跳过第一个"Notes"单元格
                        
                        song_data['difficulty_info'] = {
                            'difficulties': difficulties,
                            'levels': levels,
                            'notes': notes
                        }
                
                return song_data
        return None
    except Exception as e:
        print(f"Error processing {song_url}: {str(e)}")
        return None

def safe_extract(row, index):
    try:
        cells = row.find_all('td')
        if isinstance(index, int):
            return cells[index].get_text(strip=True) if len(cells) > index else 'No Info'
        elif isinstance(index, slice):
            return [cell.get_text(strip=True) for cell in cells[index]]
    except:
        return 'No Info'

def safe_extract_list(row, index):
    try:
        cells = row.find_all('td')
        if isinstance(index, slice):
            return [cell.get_text(strip=True) for cell in cells[index]]
        return []
    except:
        return []

def save_to_txt(data, filename='lanota_songs.txt'):
    """保存数据到TXT文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        for song in data:
            f.write(f"{song['title']}\n")
            f.write(f"{song['artist']}\n\n")
            
            # 基本信息
            f.write("Area\t" + song['basic_info']['Area'] + "\t")
            f.write("Chapter\t" + song['basic_info']['Chapter'] + "\t")
            f.write("Genre\t" + song['basic_info']['Genre'] + "\n")
            
            f.write("BPM\t" + song['basic_info']['BPM'] + "\t")
            f.write("Time\t" + song['basic_info']['Time'] + "\t")
            f.write("Vocals\t" + song['basic_info']['Vocals'] + "\n")
            
            f.write("Chart Design\t" + song['basic_info']['Chart Design'] + "\t")
            f.write("Cover Art\t" + song['basic_info']['Cover Art'] + "\n")
            
            f.write("Version\t" + song['basic_info']['Version'] + "\n\n")
            
            # 难度信息
            f.write("Difficulty\t")
            f.write("\t".join(song['difficulty_info']['difficulties']) + "\n")
            
            f.write("Level\t")
            f.write("\t".join(song['difficulty_info']['levels']) + "\n")
            
            f.write("Notes\t")
            f.write("\t".join(song['difficulty_info']['notes']) + "\n\n")
            
            f.write("="*80 + "\n\n")

def save_to_json(data, filename='lanota_songs.json'):
    """保存数据到JSON文件"""
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    base_url = "https://lanota.fandom.com/wiki/Songs"
    txt_file = 'lanota_songs.txt'
    json_file = 'lanota_songs.json'
    all_songs_data = []
    
    # 如果JSON文件已存在，加载已有数据
    if os.path.exists(json_file):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
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
                start_idx = len(all_songs_data)
                
                for i, row in enumerate(rows[start_idx:], start_idx + 1):
                    cols = row.find_all('td')
                    if cols and len(cols) > 0:
                        title_cell = cols[0]
                        link = title_cell.find('a')
                        if link and link.has_attr('href'):
                            song_url = "https://lanota.fandom.com" + link['href']
                            title = link.text.strip()
                            
                            print(f"Processing {i}/{total_songs}: {title}")
                            details = get_song_details(song_url)
                            
                            if details:
                                all_songs_data.append(details)
                                # 每次成功爬取后立即保存
                                save_to_json(all_songs_data, json_file)
                                print(f"Successfully processed and saved (Song {i})")
                            else:
                                print("Skipped due to processing error")
                            
                            time.sleep(1)  # 礼貌性延迟
                
                # 最终保存TXT格式
                if all_songs_data:
                    save_to_txt(all_songs_data, txt_file)
                    print(f"\nSuccess! Data saved to both {txt_file} and {json_file}")
                    print(f"Total songs processed: {len(all_songs_data)}")
                else:
                    print("No song data was collected.")
            else:
                print("Could not find the songs table on the page.")
        else:
            print(f"Failed to access main page (HTTP {response.status_code})")
    except Exception as e:
        print(f"Error: {str(e)}")
        if all_songs_data:
            save_to_json(all_songs_data, json_file)
            print(f"Saved {len(all_songs_data)} songs before error occurred")

if __name__ == "__main__":
    main()