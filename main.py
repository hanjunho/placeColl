import tkinter as tk
from tkinter import messagebox
import threading
import logging
import os
import pandas as pd
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException
import re


def start_crawling():
    search_keyword = entry.get()
    if not search_keyword:
        messagebox.showerror("Error", "검색어를 입력하세요.")
        return
    threading.Thread(target=crawl, args=(search_keyword,)).start()


def on_enter_key(event):
    start_crawling()


def crawl(search_keyword):
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("크롤링 시작")

    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)  # 대기 시간을 20초로 연장

    logging.info(f"URL 접속: https://map.naver.com/p/search/{search_keyword}")
    driver.get(f"https://map.naver.com/p/search/{search_keyword}")
    time.sleep(4)

    data = []

    def collect_data():
        nonlocal data
        try:
            search_iframe = driver.find_element(By.ID, "searchIframe")
            driver.switch_to.frame(search_iframe)
        except NoSuchElementException as e:
            logging.error(f"searchIframe 로드 오류: {e}")
            return

        scroll_container = driver.find_element(By.CSS_SELECTOR, "#_pcmap_list_scroll_container")
        index = 0

        while True:
            place_elements = driver.find_elements(By.CSS_SELECTOR, "#_pcmap_list_scroll_container > ul > li.VLTHu.OW9LQ")
            if not place_elements:
                break

            if index >= len(place_elements):
                driver.execute_script("arguments[0].scrollTop += arguments[1].clientHeight;", scroll_container, place_elements[-1])
                time.sleep(1)
                place_elements = driver.find_elements(By.CSS_SELECTOR, "#_pcmap_list_scroll_container > ul > li.VLTHu.OW9LQ")
                if index >= len(place_elements):
                    break

            place = place_elements[index]

            # 스크롤 및 클릭
            if index != 0:
                driver.execute_script("arguments[0].scrollTop += arguments[1].clientHeight;", scroll_container, place)
                time.sleep(1)

            try:
                driver.execute_script("arguments[0].click();", place.find_element(By.CSS_SELECTOR, "div.qbGlu > div.ouxiq > a:nth-child(1)"))
            except ElementClickInterceptedException as e:
                logging.error(f"요소 클릭 오류: {e}")
                index += 1
                continue
            time.sleep(2)

            # 최상위 루트 HTML로 전환
            driver.switch_to.default_content()

            try:
                # entryIframe이 존재하는지 확인
                entry_iframe_present = wait.until(EC.presence_of_element_located((By.ID, "entryIframe")))
                if entry_iframe_present:
                    driver.switch_to.frame("entryIframe")
                    logging.info("entryIframe 전환 성공")
                    time.sleep(1)

                    try:
                        name = driver.find_element(By.CSS_SELECTOR, "#_title > div > span.GHAhO").text

                        try:
                            svg_element = driver.find_element(By.CSS_SELECTOR, "#app-root > div > div > div > div:nth-child(5) > div > div:nth-child(2) > div.place_section_content > div > div.O8qbU.pSavy > div > a > div.w9QyJ.vI8SM > div > span > svg")
                            svg_element.click()
                            time.sleep(1)
                            logging.info("SVG 클릭 성공")
                        except NoSuchElementException:
                            logging.info("SVG 요소가 없음")

                        place_section_content = driver.find_element(By.CSS_SELECTOR, "#app-root > div > div > div > div:nth-child(5) > div > div:nth-child(2) > div.place_section_content > div").text

                        current_url = driver.current_url
                        image_link = re.sub(r'placePath=%3Fentry%253Dpll', 'placePath=/photo', current_url)

                        try:
                            info_tab = driver.find_element(By.XPATH, "//div[@id='app-root']/div/div/div/div[contains(@class, 'place_fixed_maintab')]/div/div/div/div/a[span[contains(text(), '정보')]]")
                            try:
                                wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@id='app-root']/div/div/div/div[contains(@class, 'place_fixed_maintab')]/div/div/div/div/a[span[contains(text(), '정보')]]")))
                                driver.execute_script("arguments[0].click();", info_tab)
                                logging.info("정보 탭 클릭 성공")
                            except ElementClickInterceptedException as e:
                                logging.error(f"정보 탭 클릭 오류: {e}")
                        except NoSuchElementException:
                            logging.info("정보 탭이 존재하지 않음")

                        info = ""
                        time.sleep(1)
                        try:
                            if driver.find_element(By.CSS_SELECTOR, "#app-root > div > div > div > div:nth-child(6) > div > div.place_section.no_margin.Od79H > h2.place_section_header").text == "소개":
                                info = driver.find_element(By.CSS_SELECTOR, "#app-root > div > div > div > div:nth-child(6) > div > div.place_section.no_margin.Od79H > div > div > div.Ve1Rp > div").text
                        except NoSuchElementException:
                            info = "No information available"

                        data.append({
                            "업체명": name,
                            "영업시간 및 기타 정보": place_section_content,
                            "사진링크": image_link,
                            "정보": info
                        })
                        logging.info(f"데이터 수집 완료: {name}")

                    except NoSuchElementException as e:
                        logging.error(f"데이터 수집 오류: {e}")

                    # 다시 searchIframe으로 돌아가기
                    driver.switch_to.default_content()
                    search_iframe = driver.find_element(By.ID, "searchIframe")
                    driver.switch_to.frame(search_iframe)

            except TimeoutException as e:
                logging.error(f"entryIframe 로드 오류: {e}")
                index += 1
                continue

            index += 1

    def save_to_excel():
        df = pd.DataFrame(data)
        file_exists = os.path.isfile(f"{search_keyword}.xlsx")
        if file_exists:
            existing_df = pd.read_excel(f"{search_keyword}.xlsx")
            df = pd.concat([existing_df, df], ignore_index=True)
        df.to_excel(f"{search_keyword}.xlsx", index=False)
        logging.info(f"데이터 저장 완료: {search_keyword}.xlsx")

    current_page = 1
    while True:
        collect_data()
        save_to_excel()
        data.clear()

        try:
            time.sleep(2)
            # 페이지네이션에서 '다음 페이지' 버튼을 찾는 로직
            next_button = driver.find_element(By.CSS_SELECTOR, "#app-root > div > div.XUrfU > div.zRM9F > a.eUTV2:not([aria-disabled='true']) > span.place_blind")
            # app-root > div > div.XUrfU > div.zRM9F > a:nth-child(6) > span
            print('next_button: ', next_button)
            if next_button.text == "다음페이지":
                next_button_n = next_button.find_element(By.XPATH, "..")
                print('next_button_n: ', next_button.text)
                next_button_n.click()
                logging.info("다음 페이지로 이동")
                time.sleep(5)
                driver.switch_to.default_content()

            else:
                logging.info("다음 페이지가 존재하지 않음")
                break

        except NoSuchElementException:
            # '다음 페이지' 버튼이 없으면 루프 종료
            logging.info("다음 페이지가 존재하지 않음")
            break

    driver.quit()
    messagebox.showinfo("완료", "크롤링이 완료되었습니다.")
    logging.info("크롤링 완료")


root = tk.Tk()
root.title("Naver Map Crawler")

frame = tk.Frame(root)
frame.pack(pady=20)

label = tk.Label(frame, text="검색어:")
label.pack(side=tk.LEFT)

entry = tk.Entry(frame)
entry.pack(side=tk.LEFT, padx=10)

entry.bind('<Return>', on_enter_key)  # 엔터 키 이벤트 바인딩

button = tk.Button(frame, text="수집하기", command=start_crawling)
button.pack(side=tk.LEFT)

root.mainloop()
