import csv
import re
from decimal import Decimal
from playwright.sync_api import sync_playwright

HEADERS = ["Назва", "Опис", "Ціна", "Місто", "Магазин"]


def get_text(parent, selector):
    element = parent.locator(selector).first
    if element.count() == 0:
        return ""
    return " ".join((element.text_content() or "").split())


def parse_card(card):
    title = get_text(card, ".model-short-title")
    description = get_text(card, ".model-short-description .m-s-f2") or get_text(card, ".model-short-description")

    shop_row = card.locator(".model-hot-prices tr, .model-hot-prices .model-shop-row").first
    if shop_row.count() == 0:
        return None

    raw_shop = get_text(shop_row, ".model-shop-name u, .model-shop-name")

    shop = re.sub(r"\s*\(.*?\)", "", raw_shop)
    shop = re.sub(r"[\s\u2192\->\>]+$", "", shop).strip()
    
    city = get_text(shop_row, ".model-shop-city").strip("() ")

    raw_price = get_text(shop_row, ".model-shop-price a, .model-shop-price")

    digits_only = re.sub(r"\D", "", raw_price)
    if not digits_only:
        return None

    price = Decimal(digits_only)

    if not title or not shop:
        raise ValueError("Не знайдено назву або магазин")

    return [title, description or "Опис відсутній", int(price), city, shop]


def parse_ek_playwright(pages_to_scrape=1):
    base_url = "https://ek.ua/ua/list/30/"
    filename = "ek_tablets.csv"
    total = skipped = 0
    seen = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        try:
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                locale="uk-UA",
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()
            page.set_default_timeout(20000)

            with open(filename, "w", newline="", encoding="utf-8-sig") as file:
                writer = csv.writer(file, delimiter=";")
                writer.writerow(HEADERS)

                for page_num in range(pages_to_scrape):
                    url = base_url if page_num == 0 else f"{base_url}{page_num}/"
                    print(f"Обробка сторінки {page_num + 1}: {url}")
                    
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=20000)
                        page.locator(".model-short-block").first.wait_for(state="attached", timeout=10000)
                    except Exception as e:
                        print(f"Не вдалося завантажити сторінку {url}: {e}")
                        continue

                    page.wait_for_timeout(1500)

                    for card in page.locator(".model-short-block").all():
                        title_elem = card.locator(".model-short-title").first
                        if title_elem.count() == 0:
                            continue

                        model_id = title_elem.get_attribute("href")
                        if not model_id or model_id in seen:
                            continue

                        title = get_text(card, ".model-short-title")
                        try:
                            row = parse_card(card)
                            if row is None:
                                skipped += 1
                                print(f"  Без списку магазинів: {title}")
                                continue
                            
                            writer.writerow(row)
                            seen.add(model_id)
                            total += 1
                            print(f"  {row[0]} | {row[4]} | {row[2]} грн | {row[3]}")
                        except ValueError as error:
                            skipped += 1
                            print(f"  Пропущено {title}: {error}")

                    file.flush()

            print(f"\nЗавершено! Збережено: {total}; пропущено: {skipped}.")
        finally:
            browser.close()


if __name__ == "__main__":
    parse_ek_playwright(pages_to_scrape=10)