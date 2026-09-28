import os
import shutil
import csv
import json
import sqlite3
import time
from urllib.parse import urljoin
import xml.etree.ElementTree as ET
from xml.dom import minidom
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://lpnu.ua"
INSTITUTES_URL = f"{BASE_URL}/institutes"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

session = requests.Session()
session.headers.update(HEADERS)

files_to_remove = ["lpnu_data.txt", "institutes.xml", "staff.json", "images_list.csv", "images_list.txt", "lpnu.db"]
for f in files_to_remove:
    if os.path.exists(f):
        os.remove(f)

if os.path.exists("downloaded_images"):
    shutil.rmtree("downloaded_images")
os.makedirs("downloaded_images", exist_ok=True)

db_institutes = []
db_departments = []
db_staff = []
db_images = []
img_counter = 1
downloaded_img_urls = set()

def get_html(url):
    try:
        response = session.get(url, timeout=10)
        if response.status_code == 200:
            return BeautifulSoup(response.content, "html.parser")
    except Exception:
        pass
    return None

print("Запуск скрапінгу...")
soup_inst = get_html(INSTITUTES_URL)
institutes = []

if soup_inst:
    view_content = soup_inst.find("div", class_="view-content")
    if view_content:
        for div in view_content.find_all("div", recursive=False):
            a_tag = div.find("a")
            if a_tag and a_tag.get("href"):
                name = a_tag.get_text(strip=True)
                url = urljoin(BASE_URL, a_tag.get("href").strip())
                institutes.append({"name": name, "url": url})

with open("lpnu_data.txt", "w", encoding="utf-8") as file_txt:
    for inst in institutes:
        file_txt.write(f"Назва інституту: {inst['name']}\nURL: {inst['url']}\n\n")
        db_institutes.append(inst)

        soup_dep = get_html(inst['url'])
        if not soup_dep: 
            continue

        departments = []
        for a_tag in soup_dep.find_all("a"):
            text = a_tag.get_text(" ", strip=True)
            href = a_tag.get("href", "").strip() 
            
            if "кафедр" in text.lower() and href and not href.startswith("#"):
                if "/news/" not in href.lower() and "/events/" not in href.lower():
                    d_url = urljoin(BASE_URL, href)
                    if not any(d["url"] == d_url for d in departments):
                        departments.append({"name": text, "url": d_url, "institute_url": inst['url']})

        for dep in departments:
            print(f"Обробка кафедри: {dep['name']}")
            file_txt.write(f"    Назва кафедри: {dep['name']}\n    URL: {dep['url']}\n")
            db_departments.append(dep)

            soup_single_dep = get_html(dep['url'])
            
            if soup_single_dep:
                news_teasers = soup_single_dep.find_all("div", class_="news_teaser")
                for teaser in news_teasers:
                    img = teaser.find("img")
                    if img:
                        src = img.get("src")
                        if src:
                            img_url = urljoin(BASE_URL, src.strip())
                            if img_url not in downloaded_img_urls:
                                img_filename = f"dep_img_{img_counter}.jpg"
                                try:
                                    res_img = session.get(img_url, timeout=5)
                                    if res_img.status_code == 200:
                                        with open(os.path.join("downloaded_images", img_filename), "wb") as f_img:
                                            f_img.write(res_img.content)
                                        db_images.append({
                                            "unit": dep['name'],
                                            "filename": img_filename,
                                            "url": img_url
                                        })
                                        downloaded_img_urls.add(img_url)
                                        img_counter += 1
                                        break
                                except:
                                    pass
            
            staff_url = f"{dep['url']}/kolektyv-pratsivnykiv-kafedry"
            if soup_single_dep:
                for a_tag in soup_single_dep.find_all("a"):
                    a_text = a_tag.get_text(strip=True).lower()
                    if "колектив" in a_text or "склад" in a_text or "працівники" in a_text:
                        staff_url = urljoin(BASE_URL, a_tag.get("href").strip())
                        break
            
            soup_staff = get_html(staff_url)
            staff_found = []
            
            if soup_staff:
                staff_cards = soup_staff.find_all("div", class_="dep_staff_info")
                
                for card in staff_cards:
                    h3_tag = card.find("h3")
                    name = ""
                    profile_url = ""
                    
                    if h3_tag:
                        a_tag = h3_tag.find("a")
                        if a_tag:
                            name = a_tag.get_text(strip=True)
                            profile_url = urljoin(BASE_URL, a_tag.get("href").strip())
                        else:
                            name = h3_tag.get_text(strip=True)
                    
                    div_pos = card.find("div", class_="dep_staff_infod")
                    position = div_pos.get_text(strip=True) if div_pos else ""
                    
                    if name:
                        full_name = f"{name} ({position})" if position else name
                        if full_name not in staff_found:
                            staff_found.append(full_name)
                            db_staff.append({
                                "department_url": dep['url'],
                                "name": name,
                                "position": position,
                                "profile_url": profile_url
                            })

            file_txt.write("    Працівники:\n")
            if staff_found:
                for person in staff_found:
                    file_txt.write(f"      - {person}\n")
            else:
                file_txt.write("      (Працівників не знайдено)\n")
            
            file_txt.write("\n")
            time.sleep(0.3)

root_xml = ET.Element("institutes")
for inst in db_institutes:
    node = ET.SubElement(root_xml, "institute")
    ET.SubElement(node, "name").text = inst["name"]
    ET.SubElement(node, "url").text = inst["url"]

with open("institutes.xml", "wb") as f_xml:
    xml_str = ET.tostring(root_xml, "utf-8")
    f_xml.write(minidom.parseString(xml_str).toprettyxml(indent="  ", encoding="utf-8"))

with open("staff.json", "w", encoding="utf-8") as f_json:
    json.dump(db_staff, f_json, ensure_ascii=False, indent=4)

if db_images:
    with open("images_list.csv", "w", encoding="utf-8", newline="") as f_csv:
        writer = csv.DictWriter(f_csv, fieldnames=["unit", "filename", "url"])
        writer.writeheader()
        writer.writerows(db_images)

    with open("images_list.txt", "w", encoding="utf-8") as f_img_txt:
        for img in db_images:
            f_img_txt.write(f"{img['filename']} | {img['unit']} | {img['url']}\n")

conn = sqlite3.connect("lpnu.db")
cursor = conn.cursor()

cursor.executescript("""
CREATE TABLE institutes (id INTEGER PRIMARY KEY, name TEXT, url TEXT UNIQUE);
CREATE TABLE departments (id INTEGER PRIMARY KEY, institute_id INTEGER, name TEXT, url TEXT UNIQUE);
CREATE TABLE staff (id INTEGER PRIMARY KEY, department_id INTEGER, name TEXT, position TEXT, url TEXT);
CREATE TABLE images (id INTEGER PRIMARY KEY, unit_name TEXT, filename TEXT, url TEXT);
""")

for inst in db_institutes:
    cursor.execute("INSERT OR IGNORE INTO institutes (name, url) VALUES (?, ?)", (inst["name"], inst["url"]))
conn.commit()

cursor.execute("SELECT url, id FROM institutes")
inst_map = dict(cursor.fetchall())

for dep in db_departments:
    inst_id = inst_map.get(dep["institute_url"])
    if inst_id:
        cursor.execute("INSERT OR IGNORE INTO departments (institute_id, name, url) VALUES (?, ?, ?)", (inst_id, dep["name"], dep["url"]))
conn.commit()

cursor.execute("SELECT url, id FROM departments")
dep_map = dict(cursor.fetchall())

for st in db_staff:
    dep_id = dep_map.get(st["department_url"])
    if dep_id:
        cursor.execute("INSERT INTO staff (department_id, name, position, url) VALUES (?, ?, ?, ?)", 
                       (dep_id, st["name"], st["position"], st["profile_url"]))

for img in db_images:
    cursor.execute("INSERT INTO images (unit_name, filename, url) VALUES (?, ?, ?)", (img["unit"], img["filename"], img["url"]))

conn.commit()
conn.close()

print("Готово!")
