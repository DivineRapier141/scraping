import json
import csv
from playwright.sync_api import sync_playwright

URL = "https://webscraper.io/test-sites/load-more"

cars = []

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()
    page.goto(URL)
    page.wait_for_selector(".test-sites-card")

    while True:
        button = page.locator(".load-more-btn")

        if not button.is_visible():
            print("Кнопки більше немає")
            break

        old_count = page.locator(".test-sites-card").count()

        button.click()
        print("Натиснув Load More")

        try:
            page.wait_for_function(
                "count => document.querySelectorAll('.test-sites-card').length > count",
                arg=old_count,
                timeout=10000,
            )
        except Exception:
            print("Нові картки не з'явились")
            break

    cards = page.locator(".test-sites-card")
    total = cards.count()
    print("Всього карток:", total)

    for i in range(total):
        card = cards.nth(i)

        name = card.locator(".card-title").inner_text().strip()
        price = card.locator(".price").inner_text().strip()
        availability = card.locator(".availability").inner_text().strip()
        rating = card.locator(".ws-icon-star.active").count()

        car = {
            "name": name,
            "price": price,
            "availability": availability,
            "rating": rating,
        }
        cars.append(car)
        print(car)

    browser.close()


with open("dynamic_scrap/data/cars.json", "w", encoding="utf-8") as f:
    json.dump(cars, f, ensure_ascii=False, indent=4)


with open("dynamic_scrap/data/cars.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["name", "price", "availability", "rating"])
    writer.writeheader()
    writer.writerows(cars)

print("Готово! Збережено", len(cars), "машин у cars.json і cars.csv")