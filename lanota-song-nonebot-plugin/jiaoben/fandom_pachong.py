import requests
import mwparserfromhell
import json
import re
import time
import os
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import unquote

BASE_URL = "https://lanota.fandom.com"
API_URL = f"{BASE_URL}/api.php"
def get_output_path():
    # 获取上层文件夹的config.py中的lanota_full_path
    config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.py')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"找不到config.py文件: {config_path}")
    
    # 动态导入config模块
    import importlib.util
    spec = importlib.util.spec_from_file_location("config", config_path)
    config = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config)
    
    if not hasattr(config, 'lanota_full_path'):
        raise AttributeError("config.py中没有定义lanota_full_path")
    
    SONGS_JSON = config.lanota_full_path
    
    return SONGS_JSON

# ---------- 工具函数 ----------

def clean_ref(text):
    return re.sub(r"<ref.*?>.*?<\/ref>", "", text or "", flags=re.DOTALL)

def clean_wiki_links(text):
    if not text:
        return ""
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return text.strip()

def replace_br(text):
    return re.sub(r"<br\s*/?>", " | ", text or "")

def classify(chap_left):
    left = chap_left.lower()
    if left in ('time limited', 'event'):
        return 'event'
    if left.isdigit():
        return 'main'
    if re.match(r'^[A-Za-z]+\d+$', chap_left):
        return 'side'
    if re.match(r'^[A-Za-z]{1,2}$', chap_left):
        return 'expansion'
    if left in ('∞', 'inf', 'Inf'):
        return 'subscription'
    return 'other'

def get_final_url(session, url, max_retries=3):
    for _ in range(max_retries):
        try:
            resp = session.get(url, allow_redirects=True, timeout=10)
            return resp.url
        except requests.exceptions.RequestException:
            time.sleep(1)
    return url

def check_missing_fields(song):
    """检查歌曲的缺失字段，返回缺失字段列表"""
    missing = []
    
    # 检查 bpm
    if not song.get('bpm') or song.get('bpm', '').strip() == '':
        missing.append('bpm')
    
    # 检查 time
    if not song.get('time') or song.get('time', '').strip() == '':
        missing.append('time')
    
    # 检查 notes（各个难度）
    notes = song.get('notes', {})
    notes_missing = []
    for difficulty in ['whisper', 'acoustic', 'ultra', 'master']:
        if not notes.get(difficulty) or notes.get(difficulty, '').strip() == '':
            notes_missing.append(difficulty)
    
    if notes_missing:
        missing.append(f"notes({','.join(notes_missing)})")
    
    # 检查 Legacy 中的 notes（只有当 Legacy 存在且非空时才检查）
    if 'Legacy' in song and isinstance(song['Legacy'], dict) and song['Legacy']:
        legacy = song['Legacy']
        legacy_notes_missing = []
        for field in ['MaxWhisper', 'MaxAcoustic', 'MaxUltra', 'MaxMaster']:
            if not legacy.get(field) or legacy.get(field, '').strip() == '':
                legacy_notes_missing.append(field)
        
        if legacy_notes_missing:
            missing.append(f"legacy_notes({','.join(legacy_notes_missing)})")
    
    return missing

def update_song_from_wiki(session, song):
    """从 wiki 更新歌曲信息"""
    if 'source_url' not in song:
        return None, []
    
    try:
        final_url = get_final_url(session, song['source_url'])
        raw_page = final_url.rsplit('/wiki/', 1)[-1]
        page_name = unquote(raw_page)

        params = {'action': 'parse', 'page': page_name, 'prop': 'wikitext', 'format': 'json'}
        r = session.get(API_URL, params=params, timeout=15)
        wikitext = r.json().get('parse', {}).get('wikitext', {}).get('*', '')
        wikicode = mwparserfromhell.parse(wikitext)
        tmpl = next((t for t in wikicode.filter_templates() if t.name.strip().lower() == 'song'), None)

        def get_field(field):
            if not tmpl or not tmpl.has(field):
                return ''
            val = str(tmpl.get(field).value)
            val = clean_ref(val)
            val = clean_wiki_links(val)
            return replace_br(val).strip()

        updated_fields = []
        
        # 更新 bpm
        new_bpm = get_field('BPM')
        if new_bpm and (not song.get('bpm') or song.get('bpm', '').strip() == ''):
            song['bpm'] = new_bpm
            updated_fields.append('bpm')
        
        # 更新 time
        new_time = get_field('Time')
        if new_time and (not song.get('time') or song.get('time', '').strip() == ''):
            song['time'] = new_time
            updated_fields.append('time')
        
        # 更新 notes
        notes_updated = []
        if 'notes' not in song:
            song['notes'] = {}
        
        for difficulty, field_name in [('whisper', 'MaxWhisper'), ('acoustic', 'MaxAcoustic'), 
                                       ('ultra', 'MaxUltra'), ('master', 'MaxMaster')]:
            new_value = get_field(field_name)
            if new_value and (not song['notes'].get(difficulty) or song['notes'].get(difficulty, '').strip() == ''):
                song['notes'][difficulty] = new_value
                notes_updated.append(difficulty)
        
        if notes_updated:
            updated_fields.append(f"notes({','.join(notes_updated)})")
        
        # 更新 Legacy notes（只有当 Legacy 存在且非空时才更新）
        if 'Legacy' in song and isinstance(song['Legacy'], dict) and song['Legacy']:
            legacy_updated = []
            for t in wikicode.filter_templates():
                if t.name.strip().lower() == 'legacytable':
                    for field in ['MaxWhisper', 'MaxAcoustic', 'MaxUltra', 'MaxMaster']:
                        if t.has(field):
                            new_value = replace_br(clean_ref(str(t.get(field).value).strip()))
                            if new_value and (not song['Legacy'].get(field) or song['Legacy'].get(field, '').strip() == ''):
                                song['Legacy'][field] = new_value
                                legacy_updated.append(field)
            
            if legacy_updated:
                updated_fields.append(f"legacy_notes({','.join(legacy_updated)})")
        
        return song, updated_fields
    
    except Exception as e:
        print(f"  更新失败: {e}")
        return None, []

# ---------- 主程序 ----------

def main():
    SONGS_JSON = get_output_path()
    SONGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0'})

    # 读取已处理数据
    try:
        with open(SONGS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = []

    # 记录原始数据长度
    original_count = len(data)
    
    # ========== 第一步：检查并更新缺失信息 ==========
    print("=" * 60)
    print("第一步：检查现有歌曲的缺失信息")
    print("=" * 60)
    
    songs_to_update = []
    update_results = []  # 在外层定义
    success_count = 0    # 在外层定义
    
    for song in data:
        missing = check_missing_fields(song)
        if missing:
            songs_to_update.append({
                'song': song,
                'missing': missing
            })
    
    if songs_to_update:
        print(f"\n发现 {len(songs_to_update)} 首歌曲存在缺失信息：")
        for item in songs_to_update:
            print(f"  - {item['song']['title']} (章节: {item['song']['chapter']})")
            print(f"    缺失: {', '.join(item['missing'])}")
        
        print(f"\n开始更新缺失信息...")
        
        for idx, item in enumerate(songs_to_update, 1):
            song = item['song']
            missing = item['missing']
            print(f"\n[{idx}/{len(songs_to_update)}] 正在更新: {song['title']}")
            print(f"  缺失项: {', '.join(missing)}")
            
            updated_song, updated_fields = update_song_from_wiki(session, song)
            
            if updated_song and updated_fields:
                # 在原数据中找到并更新
                for i, s in enumerate(data):
                    if s['chapter'] == song['chapter']:
                        data[i] = updated_song
                        break
                
                update_results.append({
                    'title': song['title'],
                    'chapter': song['chapter'],
                    'missing': missing,
                    'updated': updated_fields,
                    'success': True
                })
                print(f"  ✓ 成功更新: {', '.join(updated_fields)}")
            else:
                update_results.append({
                    'title': song['title'],
                    'chapter': song['chapter'],
                    'missing': missing,
                    'updated': [],
                    'success': False
                })
                print(f"  ✗ 更新失败或无新数据")
            
            time.sleep(0.5)
        
        # 保存更新后的数据
        with open(SONGS_JSON, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # 输出更新报告
        print("\n" + "=" * 60)
        print("缺失信息更新报告")
        print("=" * 60)
        for result in update_results:
            status = "✓ 成功" if result['success'] else "✗ 失败"
            print(f"\n{status} | {result['title']} (章节: {result['chapter']})")
            print(f"  原缺失: {', '.join(result['missing'])}")
            if result['updated']:
                print(f"  已更新: {', '.join(result['updated'])}")
            else:
                print(f"  已更新: 无")
        
        success_count = sum(1 for r in update_results if r['success'])
        print(f"\n总计: {len(update_results)} 首需要更新，{success_count} 首成功更新")
    else:
        print("\n✓ 所有歌曲信息完整，无需更新")
    
    # ========== 第二步：添加新歌曲 ==========
    print("\n" + "=" * 60)
    print("第二步：检查并添加新歌曲")
    print("=" * 60)

    # 构建去重集合：真实标题和外部标题
    existing_titles = {item['title'].lower() for item in data}
    existing_outside = {item.get('title_outside', '').lower() for item in data if item.get('title_outside')}
    existing_chapters_lower = {item['chapter'].lower() for item in data}

    print("正在搜索乐曲列表……")
    resp = session.get(f"{BASE_URL}/wiki/Songs")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    # 收集页面上的所有乐曲链接及初步标题
    songs_info = []
    for row in soup.find('table', {'class': 'wikitable'}).find_all('tr')[1:]:
        cols = row.find_all('td')
        if len(cols) < 3:
            continue
        link = cols[0].find('a', href=re.compile(r"^/wiki/.+"))
        if not link:
            continue
        songs_info.append({
            'href': f"{BASE_URL}{link['href']}",
            'display_title': link.get('title', '').strip()
        })

    print(f"共找到 {len(songs_info)} 首乐曲")

    # 第一轮：按 title 初步匹配，包括外部title
    candidates = [info for info in songs_info
                  if info['display_title'].lower() not in existing_titles
                  and info['display_title'].lower() not in existing_outside]
    skipped = len(songs_info) - len(candidates)
    print(f"{skipped} 首已通过初步匹配，跳过；剩余 {len(candidates)} 首待进一步核对")

    new_count = 0

    for info in candidates:
        final_url = get_final_url(session, info['href'])
        raw_page = final_url.rsplit('/wiki/', 1)[-1]
        page_name = unquote(raw_page)

        params = {'action': 'parse', 'page': page_name, 'prop': 'wikitext', 'format': 'json'}
        r = session.get(API_URL, params=params, timeout=15)
        wikitext = r.json().get('parse', {}).get('wikitext', {}).get('*', '')
        wikicode = mwparserfromhell.parse(wikitext)
        tmpl = next((t for t in wikicode.filter_templates() if t.name.strip().lower() == 'song'), None)

        def get_field(field):
            if not tmpl or not tmpl.has(field):
                return ''
            val = str(tmpl.get(field).value)
            val = clean_ref(val)
            val = clean_wiki_links(val)
            return replace_br(val).strip()

        # 处理章节：time limited 转 Event
        raw_chap_left = get_field('Chapter')
        left_standard = raw_chap_left.replace('∞', 'Inf')
        chap_left_clean = 'Event' if left_standard.lower() == 'time limited' else left_standard
        chap_right = get_field('Id')
        real_chapter = f"{chap_left_clean}-{chap_right}"
        
        # 处理谱师：SYM -> None
        chart_design = get_field('Chart Design')
        if chart_design.strip().upper() == 'SYM':
            chart_design = None

        # 深度匹配：按章节小写匹配
        if real_chapter.lower() in existing_chapters_lower:
            print(f"已存在章节 '{real_chapter}'，跳过")
            # 记录外部标题以免下次再深度匹配
            # 在已存在条目里找到对应章节，添加title_outside字段
            for item in data:
                if item['chapter'].lower() == real_chapter.lower():
                    if 'title_outside' not in item:
                        item['title_outside'] = info['display_title']
                    break
            continue

        # 解析标题：取更长的那个
        field_title = get_field('Song') or ''
        display_title = info['display_title'] or ''
        real_title = field_title if len(field_title) >= len(display_title) else display_title

        category = 'event' if chap_left_clean == 'Event' else classify(chap_left_clean)

        new_count += 1
        print(f"添加新乐曲 #{new_count}: '{real_title}' (章节 {real_chapter})")

        song = {
            'id': len(data) + 1,
            'title': real_title,
            'title_outside': info['display_title'],
            'artist': get_field('Artist'),
            'chapter': real_chapter,
            'category': category,
            'difficulty': {
                'whisper': get_field('DiffWhisper'),
                'acoustic': get_field('DiffAcoustic'),
                'ultra': get_field('DiffUltra'),
                'master': get_field('DiffMaster')
            },
            'time': get_field('Time'),
            'bpm': get_field('BPM'),
            'version': get_field('Version'),
            'area': get_field('Area'),
            'genre': get_field('Genre'),
            'vocals': get_field('Vocals'),
            'chart_design': chart_design,
            'cover_art': get_field('Cover Art'),
            'notes': {
                'whisper': get_field('MaxWhisper'),
                'acoustic': get_field('MaxAcoustic'),
                'ultra': get_field('MaxUltra'),
                'master': get_field('MaxMaster')
            },
            'source_url': final_url
        }

        # 附加 Trivia
        if '==Trivia==' in wikitext:
            trivia = [clean_wiki_links(clean_ref(item.strip())) for item in re.findall(r"\*([^\n]+)", wikitext.split('==Trivia==')[1])]
            song['Trivia'] = trivia

        # 附加 Legacy Table
        legacy = {}
        for t in wikicode.filter_templates():
            if t.name.strip().lower() == 'legacytable':
                for param in t.params:
                    key = clean_wiki_links(str(param.name).strip())
                    val = replace_br(clean_ref(str(param.value).strip()))
                    legacy[key] = val
        song['Legacy'] = legacy

        # 写入并更新去重集合
        data.append(song)
        existing_chapters_lower.add(real_chapter.lower())
        existing_titles.add(real_title.lower())
        existing_outside.add(info['display_title'].lower())

        with open(SONGS_JSON, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        time.sleep(0.5)

    # 保存可能更新的已存在条目的 title_outside
    with open(SONGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("\n" + "=" * 60)
    print("处理完成总结")
    print("=" * 60)
    print(f"原有歌曲数: {original_count}")
    if songs_to_update:
        print(f"缺失信息更新: {len(songs_to_update)} 首待更新，{success_count} 首成功")
    print(f"新增歌曲: {new_count} 首")
    print(f"当前总数: {len(data)} 首")
    
    return {
        'before': original_count,
        'missing_songs': len(songs_to_update),
        'missing_updated': success_count,
        'missing_results': update_results,
        'added': new_count,
        'total': len(data)
    }

if __name__ == '__main__':
    main()
