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
# Google Cloud Consoleでsheets.googleapis.comの有効化が必要です。
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
TOKEN_PICKLE_FILE = 'token.pickle'
# 🚨 ここをあなたのスプレッドシートIDに置き換えてください
# 1U_6H73SKZ7NXWHB7oXG2mdhh4kHe0zLXg9iSJ3jCjqY は元のコードの例です。
SPREADSHEET_ID = "1waFSSryRnz1H0EzgUoTPjcqjfyssd3PbXclANx0YOZA" 
# 書き込み先のシート名を設定
RELEASE_SHEET = "OpenAI" 
URL = "https://help.openai.com/en/articles/6825453-chatgpt-release-notes"

# ==========================
# Google Sheets 認証 (ご提示のロジックを使用)
# ==========================
def get_credentials():
    """token.pickleから認証情報をロードし、必要ならリフレッシュします。"""
    creds = None
    if not os.path.exists(TOKEN_PICKLE_FILE):
        print("❌ token.pickle が存在しません。OAuth認証を完了させてから実行してください。")
        sys.exit(1)
        
    with open(TOKEN_PICKLE_FILE, 'rb') as f:
        creds = pickle.load(f)
        
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            print("🕒 トークンをリフレッシュしています...")
            creds.refresh(Request())
        else:
            print("❌ OAuth トークンが無効です。token.pickleを再取得してください。")
            sys.exit(1)
            
    return creds

# ==========================
# Sheets 書き込み関数 (ロジックを本件用に修正)
# ==========================
def write_release_notes(data):
    """
    抽出したリリース情報をスプレッドシートのA2以降に書き込みます。
    A列: 日付, B列: リリース内容
    """
    try:
        creds = get_credentials()
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        
        if not data:
            print("⚠️ 転記するデータがありません。")
            return

        # 1. ヘッダー行 (A1:B1) を書き込み
        header = [['日付', 'リリース内容']]
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{RELEASE_SHEET}!A1:B1",
            valueInputOption="RAW",
            body={"values": header}
        ).execute()

        # 2. 既存データ（A2以降）をクリア
        # スプレッドシートのサイズを考慮し、広めにクリア
        sheet.values().clear(
            spreadsheetId=SPREADSHEET_ID, 
            range=f"{RELEASE_SHEET}!A2:C1000"
        ).execute()
        
        # 3. データ書き込み
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            # A2から開始し、データ全体を書き込む
            range=f"{RELEASE_SHEET}!A2:B",
            valueInputOption="USER_ENTERED", # スプレッドシートの書式を維持するため
            body={"values": data}
        ).execute()
        
        print(f"✅ {len(data)} 行を {RELEASE_SHEET} シートに転記しました。")
        
    except Exception as e:
        print(f"⚠️ 書き込み処理中にエラーが発生しました: {e}")
        sys.exit(1)

# ==========================
# スクレイピング関数 (Beautiful Soupを使用)
# ==========================
def extract_release_notes(url):
    """
    OpenAI ChatGPTリリースノートのURLから日付と内容を抽出します。
    """
    print(f"🔍 {url} からリリースノートを抽出中...")
    try:
        # Webページを取得
        response = requests.get(url, timeout=10)
        response.raise_for_status() 
    except RequestException as e:
        print(f"Error fetching URL: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    article_body = soup.find('div', class_='article-body')
    if not article_body:
        print("Error: Could not find the main article body.")
        return []

    data_to_write = [] # 書き込み形式: [['日付', '内容'], ...]
    current_date = None
    
    for element in article_body.children:
        # <h2>タグを検出: これがリリース日
        if element.name == 'h2':
            current_date = element.get_text(strip=True)
        
        # リリース内容を含む要素（<p>タグや<ul>タグ）を検出
        elif current_date and element.name in ['p', 'ul', 'div']: 
            content = element.get_text(separator='\n', strip=True)
            
            if content:
                # 抽出データの最終エントリの日付をチェック
                if data_to_write and data_to_write[-1][0] == current_date:
                    # 同じ日付の場合は内容を追記
                    data_to_write[-1][1] += '\n\n' + content 
                else:
                    # 新しい日付の場合は新しい行として追加
                    data_to_write.append([current_date, content])
    
    print(f"✅ 抽出完了。{len(data_to_write)} 件のリリース情報を検出しました。")
    return data_to_write


# ==========================
# メイン実行
# ==========================
if __name__ == "__main__":
    
    # スプレッドシートIDが変更されているかチェック
    if SPREADSHEET_ID == "1U_6H73SKZ7NXWHB7oXG2mdhh4kHe0zLXg9iSJ3jCjqY":
        print("\n--- 警告 ---")
        print("SPREADSHEET_ID をあなたのスプレッドシートIDに置き換えてください。処理を終了します。")
        sys.exit(1)

    # 1. リリースノートを抽出
    release_data = extract_release_notes(URL)

    # 2. 抽出結果をコンソールに出力
    print("\n--- 抽出結果 (A列:日付 | B列:内容) ---")
    for row in release_data:
        print(f"{row[0]} | {row[1][:60]}...") # 内容は一部表示
    
    # 3. スプレッドシートに書き込み
    write_release_notes(release_data)

    print("\n-------------------------------------------------------")
    print(f"✨ 全ての処理が完了しました。スプレッドシートを確認してください。")
    print("-------------------------------------------------------")
