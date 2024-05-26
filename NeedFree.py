from concurrent.futures import ThreadPoolExecutor, wait, ALL_COMPLETED
import requests
import datetime
import queue
import time
import json
import pytz
import bs4


API_URL_TEMPLATE = "https://store.steampowered.com/search/results/?query&start={pos}&count=100&infinite=1"
THREAD_CNT = 8

free_list = queue.Queue()

def fetch_Steam_json_response(url):
    ''' Fetch json response from Steam API
    URL:            Steam WebAPI url

    return:         json content
    '''
    while True:
        try:
            with requests.get(url, timeout = 5) as response:
                ret_json = response.json()
            return ret_json
        except Exception as e:
            print(e)
            time.sleep(10)
            continue

def get_free_goods(start, append_list = False):
    ''' Extract 99%-discount goods list in a list of 99 products
    start:          start page index
    append_list:    if to append new found free goods to final list

    return:         goods_count
    '''

    global free_list
    retry_time = 3

    while retry_time >= 0:
        response_json = fetch_Steam_json_response(API_URL_TEMPLATE.format(pos = start))
        try:
            goods_count = response_json["total_count"]
            goods_html = response_json["results_html"]
            page_parser = bs4.BeautifulSoup(goods_html, "html.parser")
            full_discounts_div = page_parser.find_all(name = "div", attrs = {"class":"search_discount_block", "data-discount":"99"})
            sub_free_list = [
                [
                    get_img_src(div),
                    get_title(div),
                    get_review_summary(div),
                    get_href(div),
                ] for div in full_discounts_div
            ]

            if append_list:
                for sub_free in sub_free_list:
                    free_list.put(sub_free)

            return goods_count
        except Exception as e:
            print("get_free_goods: error on start = %d, remain retry %d time(s)" % (start, retry_time))
            print(e)
            retry_time -= 1
    print("get_free_goods: error on start = %d, throw" % (start))

    return 0


def get_img_src(div):
    try:
        elem = div.parent.parent.parent.parent.find(name = "img")
        if elem is None:
            return "NONE"
        else:
            return elem.get("src")
    except Exception as e:
        print("get_img_src:")
        print(div.parent.parent.parent.parent)
        print(e)
        return "NONE"

def get_title(div):
    try:
        return div.parent.parent.parent.parent.find(name = "span", attrs = {"class":"title"}).get_text()
    except Exception as e:
        print("get_title:")
        print(div.parent.parent.parent.parent)
        print(e)
        return "NONE"

def get_review_summary(div):
    try:
        elem = div.parent.parent.parent.parent.find(name = "span", attrs = {"class":"search_review_summary"})
        if elem is None:
            return "NONE"
        else:
            return elem.get("data-tooltip-html")
    except Exception as e:
        print("get_review_summary:")
        print(div.parent.parent.parent.parent)
        print(e)
        return "NONE"

def get_href(div):
    try:
        return div.parent.parent.parent.parent.get("href")
    except Exception as e:
        print("get_href:")
        print(div.parent.parent.parent.parent)
        print(e)
        return "NONE"


# Get total count of free goods
tryget_first_page = get_free_goods(0)
total_count = tryget_first_page

# Multi-thread crawling
threads = ThreadPoolExecutor(max_workers = THREAD_CNT)
futures = [threads.submit(get_free_goods, index, True) for index in range(0, total_count, 100)]

wait(futures, return_when=ALL_COMPLETED)

# Process free list
final_free_list = []
free_names = set()
while not free_list.empty():
    free_item = free_list.get()
    game_name = free_item[0]
    if game_name not in free_names:
        free_names.add(game_name)
        final_free_list.append(free_item)

with open("free_goods_detail.json", "w") as fp:
    json.dump({
        "total_count": len(final_free_list),
        "free_list": final_free_list,
        "update_time": datetime.datetime.now(tz=pytz.timezone("Asia/Shanghai")).strftime('%Y-%m-%d %H:%M:%S')
    }, fp)
