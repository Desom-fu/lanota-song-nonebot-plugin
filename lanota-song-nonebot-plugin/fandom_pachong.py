import requests
import mwparserfromhell
import json
import re
from bs4 import BeautifulSoup

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
    if left in ['time limited', 'event']:  # 合并time limited和event
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

# ---------- 断点续传 ----------
processed_ids = set()
try:
    with open(SONGS_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
        processed_ids = {item['id'] for item in data}
except FileNotFoundError:
    data = []

# ---------- 获取主页面链接 ----------
print("Fetching main song list...")
resp = requests.get(f"{BASE_URL}/wiki/Songs")
resp.raise_for_status()
soup = BeautifulSoup(resp.text, 'html.parser')
# 提取 wikitable
song_table = soup.find('table', {'class': 'wikitable'})
rows = song_table.find_all('tr')[1:]
total = len(rows)
print(f"共找到 {total} 首歌曲，已处理 {len(processed_ids)} 首，待处理 {total - len(processed_ids)} 首")

titles = []
for row in rows:
    a = row.find('a', href=re.compile(r"^/wiki/.+"))
    if a and a.get('title'):
        titles.append(a.get('title'))

# 章节计数器
category_counters = {}

# ---------- 循环处理每首歌曲 ----------
for idx, title in enumerate(titles, start=1):
    if idx in processed_ids:
        continue  # 跳过已处理
    print(f"Processing {idx}/{total}: {title}")

    # 获取 Wikitext
    params = {'action': 'parse', 'page': title, 'prop': 'wikitext', 'format': 'json'}
    r = requests.get(API_URL, params=params)
    r.raise_for_status()
    wikitext = r.json().get('parse', {}).get('wikitext', {}).get('*', '')
    wikicode = mwparserfromhell.parse(wikitext)
    tmpl = next((t for t in wikicode.filter_templates() if t.name.strip().lower() == 'song'), None)
    if not tmpl:
        continue

    # 提取字段并清洗
    def get(field):
        val = str(tmpl.get(field).value) if tmpl.has(field) else ''
        val = clean_ref(val)
        val = clean_wiki_links(val)
        val = replace_br(val)
        return val

    # 基础字段
    raw_chap = get('Chapter')
    chap_code = raw_chap.lower().replace('∞', 'inf').replace('time limited', 'event')  # 将time limited替换为event
    left = chap_code.split('-')[0]
    seq = category_counters.get(chap_code, 0) + 1
    category_counters[chap_code] = seq

    song = {
        'id': idx,
        'title': get('Song'),
        'artist': get('Artist'),
        'chapter': f"{chap_code}-{seq}",
        'category': classify(left),
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
        }
    }

    # 提取 Trivia
    trivia = []
    if '==Trivia==' in wikitext:
        sec = wikitext.split('==Trivia==', 1)[1]
        lines = re.findall(r"\*([^\n]+)", sec)
        trivia = [clean_wiki_links(clean_ref(l).strip()) for l in lines]
    song['Trivia'] = trivia

    # 提取 Legacy Table
    legacy = {}
    for t in wikicode.filter_templates():
        if t.name.strip().lower() == 'legacytable':
            for param in t.params:
                key = clean_wiki_links(str(param.name).strip())
                val = replace_br(clean_ref(str(param.value).strip()))
                legacy[key] = val
    song['Legacy'] = legacy

    # 写入并保存
    data.append(song)
    with open(SONGS_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"已保存 {idx} 首歌曲")

print(f"所有处理完成，共保存 {idx} 首歌曲到 {SONGS_JSON}")