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

    # 构建去重集合：真实标题和外部标题
    existing_titles = {item['title'].lower() for item in data}
    existing_outside = {item.get('title_outside', '').lower() for item in data if item.get('title_outside')}
    existing_chapters_lower = {item['chapter'].lower() for item in data}

    print("正在搜索歌曲列表……")
    resp = session.get(f"{BASE_URL}/wiki/Songs")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')

    # 收集页面上的所有歌曲链接及初步标题
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

    print(f"共找到 {len(songs_info)} 首歌曲")

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
        print(f"添加新歌曲 #{new_count}: '{real_title}' (章节 {real_chapter})")

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
            'chart_design': get_field('Chart Design'),
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

    print(f"处理完成，新增 {new_count} 首歌曲，当前共 {len(data)} 首")
    return {
        'before': original_count,
        'added': new_count,
        'total': len(data)
    }

if __name__ == '__main__':
    main()
