import requests
from bs4 import BeautifulSoup
import json
import time
import os
import re

# ================= 配置区 =================
START_YEAR = 1950
CACHE_FILE = 'hollywood_cache.json'
FINAL_DATA = 'network_data.json'
# 为了演示，默认限制 100 位。你可以调大到 300+ 以获得更壮观的网络
LIMIT_STARS = 100 

# 内置核心爱称映射表（补充百度百科可能缺失的流行语）
NICKNAME_MAP = {
    "Emma Stone": ["石头姐"],
    "Timothée Chalamet": ["甜茶"],
    "Jennifer Lawrence": ["大表姐"],
    "Tom Hardy": ["汤老湿", "硬汉"],
    "Benedict Cumberbatch": ["卷福", "缺爷"],
    "Michael Fassbender": ["法鲨"],
    "Jessica Chastain": ["劳模姐"],
    "Scarlett Johansson": ["寡姐"],
    "Leonardo DiCaprio": ["小李子"],
    "Tom Hiddleston": ["抖森"],
    "James McAvoy": ["一美"],
    "Ryan Gosling": ["高司令"],
    "Cate Blanchett": ["大魔王"],
    "Anne Hathaway": ["安妮"],
    "Meryl Streep": ["梅姨"],
    "Robert Downey Jr.": ["唐尼", "铁男"],
    "Chris Hemsworth": ["海总", "锤哥"],
    "Chris Evans": ["桃总", "美队"]
}

# ================= 功能函数 =================

def get_cn_info(en_name):
    """通过百度百科获取中文名和爱称"""
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    url = f"https://baike.baidu.com/item/{en_name}"
    
    info = {"cn_name": en_name, "nicknames": []}
    
    # 1. 先查内置表
    if en_name in NICKNAME_MAP:
        info["nicknames"].extend(NICKNAME_MAP[en_name])

    try:
        res = requests.get(url, headers=headers, timeout=5)
        res.encoding = 'utf-8'
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            # 提取主标题作为中文名
            h1 = soup.find('h1')
            if h1:
                info["cn_name"] = h1.get_text().strip()
            
            # 提取基本信息栏里的“别名”
            basic_info = soup.find('div', class_='basic-info')
            if basic_info:
                items = basic_info.find_all('dt', class_='basicInfo-item name')
                values = basic_info.find_all('dd', class_='basicInfo-item value')
                for n, v in zip(items, values):
                    if "别名" in n.get_text() or "昵称" in n.get_text():
                        alias_text = v.get_text().strip()
                        # 简单的分词处理
                        aliases = re.split(r'[,，、；;（）()\s]+', alias_text)
                        for a in aliases:
                            if a and a != en_name and not a.isascii() and a not in info["nicknames"]:
                                info["nicknames"].append(a)
    except:
        pass
    return info

def get_nominees_since_1950():
    """扫描维基百科获取 1950 至今的奥斯卡提名者"""
    urls = [
        "https://en.wikipedia.org/wiki/Academy_Award_for_Best_Actor",
        "https://en.wikipedia.org/wiki/Academy_Award_for_Best_Actress",
        "https://en.wikipedia.org/wiki/Academy_Award_for_Best_Supporting_Actor",
        "https://en.wikipedia.org/wiki/Academy_Award_for_Best_Supporting_Actress"
    ]
    headers = {'User-Agent': 'Mozilla/5.0'}
    all_stars = set()

    print(f"正在扫描奥斯卡名单 (>{START_YEAR})...")
    for url in urls:
        try:
            res = requests.get(url, headers=headers)
            soup = BeautifulSoup(res.text, 'html.parser')
            for table in soup.find_all('table', class_='wikitable'):
                current_year = 0
                for row in table.find_all('tr')[1:]:
                    cols = row.find_all(['td', 'th'])
                    if not cols: continue
                    y_txt = cols[0].get_text().strip()
                    if y_txt[:4].isdigit(): current_year = int(y_txt[:4])
                    
                    if current_year >= START_YEAR:
                        for col in cols:
                            for link in col.find_all('a'):
                                name = link.get_text().strip()
                                if len(name.split()) >= 2 and "Award" not in name:
                                    all_stars.add(name)
        except Exception as e:
            print(f"解析出错: {e}")
    return list(all_stars)

def get_filmography(actor_name):
    """获取影星的作品集"""
    url = f"https://en.wikipedia.org/wiki/{actor_name.replace(' ', '_')}_filmography"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            res = requests.get(f"https://en.wikipedia.org/wiki/{actor_name.replace(' ', '_')}", headers=headers)
        soup = BeautifulSoup(res.text, 'html.parser')
        films = set()
        for table in soup.find_all('table', class_='wikitable'):
            for row in table.find_all('tr'):
                i_tag = row.find('i')
                if i_tag: films.add(i_tag.get_text().strip())
        return list(films)
    except:
        return []

# ================= 主程序 =================

def main():
    # 1. 拿名单
    all_stars = get_nominees_since_1950()
    
    # 2. 加载/更新作品缓存
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
    else:
        cache = {}

    to_crawl = [s for s in all_stars if s not in cache][:LIMIT_STARS]
    print(f"计划补充 {len(to_crawl)} 位影星的作品数据...")
    
    for i, actor in enumerate(to_crawl):
        films = get_filmography(actor)
        if films:
            cache[actor] = films
        print(f"[{i+1}/{len(to_crawl)}] 抓取作品中: {actor}")
        time.sleep(0.5)

    with open(CACHE_FILE, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=4)

    # 3. 构建 D3 数据结构，并注入中文信息
    print("\n正在生成关系网并匹配中文爱称...")
    nodes = []
    links = []
    actors = list(cache.keys())

    # 先批量处理 Node，避免重复抓取中文名
    for i, a1 in enumerate(actors):
        print(f"正在匹配中文信息 ({i+1}/{len(actors)}): {a1}")
        cn_info = get_cn_info(a1)
        nodes.append({
            "id": a1,
            "cn_name": cn_info["cn_name"],
            "nicknames": cn_info["nicknames"],
            "count": len(cache[a1])
        })
        
        # 构建边 (Links)
        for j in range(i + 1, len(actors)):
            a2 = actors[j]
            common = list(set(cache[a1]) & set(cache[a2]))
            if common:
                links.append({
                    "source": a1, "target": a2, 
                    "value": len(common), "movies": common
                })
        # 抓取中文名时也给点延迟，防止被百度封IP
        time.sleep(0.3)

    # 4. 保存最终结果
    final_output = {"nodes": nodes, "links": links}
    with open(FINAL_DATA, 'w', encoding='utf-8') as f:
        json.dump(final_output, f, ensure_ascii=False, indent=4)
    
    print(f"\n🎉 成功！数据已存至 {FINAL_DATA}")
    print(f"节点数: {len(nodes)}, 关系数: {len(links)}")

if __name__ == "__main__":
    main()