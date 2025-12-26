#!/usr/bin/env python
# coding: utf-8

import os
import pickle
import sys
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
# ご提示いただいたスプレッドシートID
SPREADSHEET_ID = "1EVf63WG2LVToyyYCV0_G8Y4AAibfmydAu4xHseisyKA" 
RELEASE_SHEET = "OpenAI" 
URL = "https://help.openai.com/en/articles/6825453-chatgpt-release-notes"

def get_credentials():
    creds = None
    if not os.path.exists(TOKEN_PICKLE_FILE):
        print("❌ token.pickle が存在しません。")
        sys.exit(1)
    with open(TOKEN_PICKLE_FILE, 'rb') as f:
        creds = pickle.load(f)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            print("❌ OAuth トークンが無効です。")
            sys.exit(1)
    return creds

# ==========================
# Sheets 書き込み関数 (B2セルへの転記に特化)
# ==========================
def write_to_b2(text_content):
    """
    指定されたテキストをB2セルに書き込みます。
    """
    try:
        creds = get_credentials()
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        
        # B2セルに書き込み（valuesは2次元配列にする必要があります）
        body = {
            'values': [[text_content]]
        }
        
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{RELEASE_SHEET}!B2",
            valueInputOption="USER_ENTERED",
            body=body
        ).execute()
        
        print(f"✅ スプレッドシートの {RELEASE_SHEET}!B2 に転記が完了しました。")
        
    except Exception as e:
        print(f"⚠️ 書き込み処理中にエラーが発生しました: {e}")

# ==========================
# スクレイピング関数 (2つ目のh1セクションを抽出)
# ==========================
def extract_second_h1_content(url):
    """
    2つ目のh1から、3つ目のh1が始まるまでの内容をすべて取得します。
    """
    print(f"🔍 {url} から2つ目のh1セクションを抽出中...")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/109.0.0.0 Safari/537.36'
    }
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status() 
    except RequestException as e:
        print(f"Error fetching URL: {e}")
        return ""

    soup = BeautifulSoup(response.content, 'html.parser')
    h1_elements = soup.find_all('h1')
    
    # 2つ目のh1が存在するか確認 (インデックス1)
    if len(h1_elements) < 2:
        print("❌ ページ内にh1タグが2つ以上見つかりませんでした。")
        return ""
    
    target_h1 = h1_elements[1] # 2つ目のh1
    content_parts = []
    
    # h1自体のテキストを追加（必要なければコメントアウトしてください）
    content_parts.append(target_h1.get_text(strip=True))
    
    # 次の要素から順番に取得し、次のh1が現れたら停止
    sibling = target_h1.next_sibling
    while sibling:
        # 次のh1が見つかったら終了
        if sibling.name == 'h1':
            break
        
        # タグ（p, ul, h3など）であればテキストを抽出
        if sibling.name:
            text = sibling.get_text(separator='\n', strip=True)
            if text:
                content_parts.append(text)
        
        sibling = sibling.next_sibling
    
    # 改行で結合して返す
    return '\n\n'.join(content_parts)

# ==========================
# メイン実行
# ==========================
if __name__ == "__main__":
    # 1. 2番目のリリース内容を抽出
    extracted_text = extract_second_h1_content(URL)

    if extracted_text:
        # 2. スプレッドシートのB2に書き込み
        write_to_b2(extracted_text)
        print("\n--- 抽出された内容のプレビュー ---")
        print(extracted_text[:200] + "...") 
    else:
        print("抽出に失敗したため、書き込みは行われませんでした。")
