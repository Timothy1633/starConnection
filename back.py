import requests
from bs4 import BeautifulSoup
import json
import time
import os
import re

# ================= 配置区 =================
START_YEAR = 2000
CACHE_FILE = 'hollywood_cache.json'
FINAL_DATA = 'network_data.json'
LIMIT_STARS = 3

# ================= 功能函数 =================

def get_nominees_since_2000():
    """根据 Wiki 源码结构精准提取演员名单"""
    urls = [
        "https://en.wikipedia.org/wiki/Academy_Award_for_Best_Actor",
        "https://en.wikipedia.org/wiki/Academy_Award_for_Best_Actress",
        "https://en.wikipedia.org/wiki/Academy_Award_for_Best_Supporting_Actor",
        "https://en.wikipedia.org/wiki/Academy_Award_for_Best_Supporting_Actress"
    ]
    headers = {'User-Agent': 'Mozilla/5.0'}
    all_stars = set()

    print(f" 开始精准扫描维基百科表格 (年份 >= {START_YEAR})...")
    
    for url in urls:
        try:
            res = requests.get(url, headers=headers, timeout=15)
            soup = BeautifulSoup(res.text, 'html.parser')
            tables = soup.find_all('table', class_='wikitable')
            
            for table in tables:
                rows = table.find_all('tr')
                current_year = 0
                
                for row in rows:
                    # 1. 尝试寻找年份单元格 (th scope="row")
                    year_cell = row.find('th', scope='row')
                    if year_cell:
                        year_text = year_cell.get_text(strip=True)
                        year_match = re.search(r'(\d{4})', year_text)
                        if year_match:
                            current_year = int(year_match.group(1))
                    
                    # 2. 如果当前年份符合要求，寻找演员
                    if current_year >= START_YEAR:
                        # 演员永远在当前行的第一个 <td> 里
                        tds = row.find_all('td')
                        if tds:
                            actor_td = tds[0]
                            # 提取 <td> 里的第一个 <a> 标签
                            link = actor_td.find('a')
                            if link:
                                name = link.get_text(strip=True)
                                # 排除干扰项（如只有姓氏或带注释的链接）
                                if len(name.split()) >= 2 and "Award" not in name:
                                    all_stars.add(name)
                                    
        except Exception as e:
            print(f"读取 {url} 失败: {e}")
            
    print(f"✅ 精准抓取完成，共获得 {len(all_stars)} 位影星。")
    return list(all_stars)

def get_actor_details(actor_name):
    """抓取演员详情（年份+作品）"""
    name_path = actor_name.replace(' ', '_')
    main_url = f"https://en.wikipedia.org/wiki/{name_path}"
    film_url = f"https://en.wikipedia.org/wiki/{name_path}_filmography"
    headers = {'User-Agent': 'Mozilla/5.0'}
    
    data = {"films": [], "birth_year": None}
    
    try:
        # 1. 出生年份
        res_main = requests.get(main_url, headers=headers, timeout=10)
        if res_main.status_code == 200:
            soup = BeautifulSoup(res_main.text, 'html.parser')
            bday = soup.find("span", class_="bday")
            if bday: data["birth_year"] = bday.get_text()[:4]
            else:
                info = soup.find("table", class_="infobox")
                if info:
                    m = re.search(r'(19\d{2}|20\d{2})', info.get_text())
                    if m: data["birth_year"] = m.group(1)

        # 2. 作品集
        res_f = requests.get(film_url, headers=headers, timeout=10)
        f_soup = BeautifulSoup(res_f.text, 'html.parser') if res_f.status_code == 200 else BeautifulSoup(res_main.text, 'html.parser')
        
        films = set()
        for table in f_soup.find_all('table', class_='wikitable'):
            for tr in table.find_all('tr'):
                i = tr.find('i') # 电影名在斜体里
                if i:
                    fname = i.get_text(strip=True)
                    if len(fname) > 1: films.add(fname)
        data["films"] = list(films)
    except:
        pass
    return data

def main():
    # 执行流程
    names = get_nominees_since_2000()
    
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, 'r', encoding='utf-8') as f:
            cache = json.load(f)
    else:
        cache = {}

    to_crawl = [n for n in names if n not in cache][:LIMIT_STARS]
    
    for i, name in enumerate(to_crawl):
        print(f"[{i+1}/{len(to_crawl)}] 正在获取详情: {name}")
        details = get_actor_details(name)
        if details["films"]:
            cache[name] = details
        time.sleep(0.8)
        if (i+1) % 10 == 0:
            with open(CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache, f, indent=4)

    # 生成最终网络
    nodes = []
    links = []
    keys = list(cache.keys())
    for i, a1 in enumerate(keys):
        nodes.append({"id": a1, "birth_year": cache[a1]["birth_year"], "count": len(cache[a1]["films"])})
        for j in range(i + 1, len(keys)):
            a2 = keys[j]
            common = list(set(cache[a1]["films"]) & set(cache[a2]["films"]))
            if common:
                links.append({"source": a1, "target": a2, "value": len(common), "movies": common})

    with open(FINAL_DATA, 'w', encoding='utf-8') as f:
        json.dump({"nodes": nodes, "links": links}, f, ensure_ascii=False, indent=4)
    print(f"🎉 任务完成！生成了 {len(nodes)} 个节点。")

if __name__ == "__main__":
    main()