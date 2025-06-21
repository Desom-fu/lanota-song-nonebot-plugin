import requests
import mwparserfromhell
import json
import re
import time
from bs4 import BeautifulSoup
from urllib.parse import unquote

BASE_URL = "https://lanota.fandom.com"
API_URL = f"{BASE_URL}/api.php"
SONGS_JSON = 'song_list.json'

# ---------- 工具函数 ----------

def clean_ref(text):
    """移除所有 <ref>...</ref> 块"""
    return re.sub(r"<ref.*?>.*?<\/ref>", "", text or "", flags=re.DOTALL)

def clean_wiki_links(text):
    """将 [[Target|Display]] 或 [[Target]] 转为纯文本"""
    if not text:
        return ""
    text = re.sub(r"\[\[[^\]|]+\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return text.strip()

def replace_br(text):
    """将 <br> 或 <br/> 替换为  | """
    return re.sub(r"<br\s*/?>", " | ", text or "")

def classify(chap_left):
    """按规则分类 chapter 左侧"""
    left = chap_left.lower()
    if left in ['time limited', 'event']:
        return 'event'
    if left.isdigit():
        return 'main'
    if re.match(r'^[A-Za-z]\d+$', left):
        return 'side'
    if re.match(r'^[A-Za-z]{1,2}$', left):
        return 'expansion'
    if left in ['∞', 'inf']:
        return 'subscription'
    return 'other'

def get_final_url(session, url, max_retries=3):
    """获取最终跳转后的真实URL"""
    for _ in range(max_retries):
        try:
            resp = session.head(url, allow_redirects=True, timeout=10)
            return unquote(resp.url)
        except requests.exceptions.RequestException:
            time.sleep(1)
    return url

# ---------- 主程序 ----------

def main():
    # 初始化会话
    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    
    # 断点续传
    processed_ids = set()
    try:
        with open(SONGS_JSON, 'r', encoding='utf-8') as f:
            data = json.load(f)
            processed_ids = {item['id'] for item in data}
    except FileNotFoundError:
        data = []

    # 获取主列表并解析真实URL
    print("Fetching main song list...")
    resp = session.get(f"{BASE_URL}/wiki/Songs")
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    songs_info = []
    for row in soup.find('table', {'class': 'wikitable'}).find_all('tr')[1:]:
        a = row.find('a', href=re.compile(r"^/wiki/.+"))
        if a and a.get('href'):
            songs_info.append({
                'href': f"{BASE_URL}{a['href']}",
                'display_title': a.get('title', '').strip()
            })

    total = len(songs_info)
    print(f"共找到 {total} 首歌曲，已处理 {len(processed_ids)} 首")

    for idx, song_info in enumerate(songs_info, start=1):
        if idx in processed_ids:
            continue

        # 获取最终跳转URL
        final_url = get_final_url(session, song_info['href'])
        page_name = unquote(final_url.split('/wiki/')[-1])
        print(f"\nProcessing {idx}/{total}: {page_name}")

        try:
            # 获取页面内容
            params = {'action': 'parse', 'page': page_name, 'prop': 'wikitext', 'format': 'json'}
            r = session.get(API_URL, params=params, timeout=15)
            r.raise_for_status()
            wikitext = r.json().get('parse', {}).get('wikitext', {}).get('*', '')
            
            if not wikitext:
                print(f"警告：页面 {page_name} 内容为空")
                continue

            wikicode = mwparserfromhell.parse(wikitext)
            tmpl = next((t for t in wikicode.filter_templates() if t.name.strip().lower() == 'song'), None)
            if not tmpl:
                print(f"跳过：页面 {page_name} 没有song模板")
                continue

            # 提取字段
            def get(field):
                val = str(tmpl.get(field).value) if tmpl.has(field) else ''
                val = clean_ref(val)
                val = clean_wiki_links(val)
                return replace_br(val).strip()

            raw_chap = get('Chapter')
            seq = get('Id')
            real_chapter = f'{raw_chap}-{seq}'
            category = classify(real_chapter.split('-')[0].lower()) if raw_chap else 'other'

            # 构建歌曲数据
            song = {
                'id': idx,
                'title': get('Song') or song_info['display_title'],
                'artist': get('Artist'),
                'chapter': real_chapter,
                'category': category,
                'difficulty': {
                    'whisper': get('DiffWhisper'),
                    'acoustic': get('DiffAcoustic'),
                    'ultra': get('DiffUltra'),
                    'master': get('DiffMaster')
                },
                'time': get('Time'),
                'bpm': get('BPM'),
                'version': get('Version'),
                'area': get('Area'),
                'genre': get('Genre'),
                'vocals': get('Vocals'),
                'chart_design': get('Chart Design'),
                'cover_art': get('Cover Art'),
                'notes': {
                    'whisper': get('MaxWhisper'),
                    'acoustic': get('MaxAcoustic'),
                    'ultra': get('MaxUltra'),
                    'master': get('MaxMaster')
                },
                'source_url': final_url
            }

            # 处理附加信息
            if '==Trivia==' in wikitext:
                trivia = [clean_wiki_links(clean_ref(l.strip())) 
                         for l in re.findall(r"\*([^\n]+)", wikitext.split('==Trivia==')[1])]
                song['Trivia'] = trivia
            
            # 保存数据
            data.append(song)
            with open(SONGS_JSON, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            print(f"已保存 ID {idx}: {song['title']} (Chapter: {real_chapter})")
            time.sleep(0.5)

        except Exception as e:
            print(f"处理 {page_name} 时出错: {str(e)}")
            continue

    print(f"\n所有歌曲处理完成，共保存 {len(data)} 首歌曲到 {SONGS_JSON}")

if __name__ == "__main__":
    main()