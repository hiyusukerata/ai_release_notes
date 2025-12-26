#!/usr/bin/env python
# coding: utf-8

import os
import pickle
import sys
import time
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from requests.exceptions import RequestException
import requests
from bs4 import BeautifulSoup

# ==========================
# Google Sheets & 認証設定
# ==========================
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
TOKEN_PICKLE_FILE = 'token.pickle'
SPREADSHEET_ID = "1EVf63WG2LVToyyYCV0_G8Y4AAibfmydAu4xHseisyKA" 
RELEASE_SHEET = "OpenAI" 
URL = "https://help.openai.com/en/articles/6825453-chatgpt-release-notes"

def get_credentials():
    creds = None
    if os.path.exists(TOKEN_PICKLE_FILE):
        with open(TOKEN_PICKLE_FILE, 'rb') as f:
            creds = pickle.load(f)
            
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("❌ OAuth トークンが無効です。token.pickleを再取得してください。")
            sys.exit(1)
    return creds

def write_to_b2(text_content):
    try:
        creds = get_credentials()
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        
        body = {'values': [[text_content]]}
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{RELEASE_SHEET}!B2",
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        print(f"✅ スプレッドシートの {RELEASE_SHEET}!B2 に転記完了。")
    except Exception as e:
        print(f"⚠️ 書き込みエラー: {e}")

# ==========================
# スクレイピング関数 (403対策版)
# ==========================
def extract_second_h1_content(url):
    print(f"🔍 {url} から抽出中...")
    
    # ブラウザになりすますためのヘッダーを強化
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'ja,en-US;q=0.9,en;q=0.8',
        'Cache-Control': 'max-age=0',
        'Connection': 'keep-alive',
    }
    
    try:
        session = requests.Session()
        response = session.get(url, headers=headers, timeout=15)
        response.raise_for_status() 
    except RequestException as e:
        print(f"❌ アクセス失敗: {e}")
        # もし403が出る場合、サイト側がボット対策をさらに強化した可能性があります
        return ""

    soup = BeautifulSoup(response.content, 'html.parser')
    
    # 実際のページ構造に合わせて h1 または記事内の日付クラスを探す
    # OpenAIのヘルプ記事は構造が変わることがあるため、h1を再取得
    h1_elements = soup.find_all('h1')
    
    if len(h1_elements) < 2:
        print(f"⚠️ h1が不足しています（検出数: {len(h1_elements)}）。構造が変わった可能性があります。")
        return ""
    
    target_h1 = h1_elements[1] 
    content_parts = []
    content_parts.append(f"【{target_h1.get_text(strip=True)}】")
    
    sibling = target_h1.next_sibling
    while sibling:
        if sibling.name == 'h1':
            break
        if sibling.name:
            text = sibling.get_text(separator='\n', strip=True)
            if text:
                content_parts.append(text)
        sibling = sibling.next_sibling
    
    return '\n\n'.join(content_parts)

if __name__ == "__main__":
    extracted_text = extract_second_h1_content(URL)
    if extracted_text:
        write_to_b2(extracted_text)
    else:
        print("抽出に失敗しました。")
