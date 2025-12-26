#!/usr/bin/env python
# coding: utf-8

import os
import pickle
import time
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# ==========================
# Google Sheets 設定
# ==========================
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
TOKEN_PICKLE_FILE = 'token.pickle'
# 転記先スプレッドシートID
SPREADSHEET_ID = "1EVf63WG2LVToyyYCV0_G8Y4AAibfmydAu4xHseisyKA"
RESULT_SHEET = "crawl"
URL = "https://help.openai.com/en/articles/6825453-chatgpt-release-notes"

# ==========================
# Google Sheets 認証
# ==========================
def get_credentials():
    creds = None
    if not os.path.exists(TOKEN_PICKLE_FILE):
        raise Exception(f"❌ {TOKEN_PICKLE_FILE} が存在しません。")
    with open(TOKEN_PICKLE_FILE, 'rb') as f:
        creds = pickle.load(f)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise Exception("❌ OAuth トークンが無効です。")
    return creds

# ==========================
# Sheets 書き込み (B2セルへの転記)
# ==========================
def write_to_b2(text_content):
    try:
        creds = get_credentials()
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        
        # 単一セルへの書き込み
        body = {'values': [[text_content]]}
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{RESULT_SHEET}!B2",
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        print(f"✅ {RESULT_SHEET}!B2 への転記が成功しました。")
    except Exception as e:
        print(f"⚠️ 書き込みエラー: {e}")

# ==========================
# Selenium WebDriver 初期化
# ==========================
def init_webdriver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--incognito")
    # ボット検知回避用 User-Agent
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    service = webdriver.chrome.service.Service()
    return webdriver.Chrome(service=service, options=options)

# ==========================
# クロール & 抽出処理
# ==========================
def scrape_openai_release():
    driver = init_webdriver()
    extracted_text = ""
    
    try:
        print(f"🔍 {URL} へアクセス中...")
        driver.get(URL)
        
        # h1タグが表示されるまで最大20秒待機
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        
        # 全てのh1要素を取得
        h1_elements = driver.find_elements(By.TAG_NAME, "h1")
        
        if len(h1_elements) < 2:
            print(f"⚠️ h1要素が十分に（2つ以上）見つかりませんでした。検出数: {len(h1_elements)}")
            return ""

        # 2番目のh1を取得
        target_h1 = h1_elements[1]
        print(f"📌 ターゲットセクション: {target_h1.text.strip()}")
        
        # --- ここからJavaScriptで要素間のテキストを抽出 ---
        # 2つ目のh1から3つ目のh1が現れるまでの全ての兄弟要素を結合
        script = """
        var startNode = arguments[0];
        var result = startNode.innerText + "\\n\\n";
        var curr = startNode.nextElementSibling;
        
        while (curr) {
            if (curr.tagName === 'H1') {
                break;
            }
            result += curr.innerText + "\\n\\n";
            curr = curr.nextElementSibling;
        }
        return result;
        """
        extracted_text = driver.execute_script(script, target_h1)
        
    except Exception as e:
        print(f"⚠️ スクレイピング中にエラーが発生しました: {e}")
    finally:
        driver.quit()
        
    return extracted_text

# ==========================
# メイン実行
# ==========================
if __name__ == "__main__":
    content = scrape_openai_release()
    
    if content:
        print("\n--- 抽出内容プレビュー ---")
        print(content[:300] + "...")
        print("--------------------------\n")
        
        # スプレッドシートへ書き込み
        write_to_b2(content)
    else:
        print("❌ 抽出に失敗したため、処理を中断しました。")
