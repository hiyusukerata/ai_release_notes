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
# Sheets 書き込み関数 (ロジックを3列用に修正)
# ==========================
def write_release_notes(data):
    """
    抽出したリリース情報をスプレッドシートのA2以降に書き込みます。
    A列: 日付, B列: タイトル, C列: 本文
    """
    try:
        creds = get_credentials()
        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()
        
        if not data:
            print("⚠️ 転記するデータがありません。")
            return

        # 1. ヘッダー行 (A1:C1) を書き込み
        header = [['日付 (H1)', 'タイトル (H3)', '本文']]
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{RELEASE_SHEET}!A1:C1",
            valueInputOption="RAW",
            body={"values": header}
        ).execute()

        # 2. 既存データ（A2以降）をクリア
        # スプレッドシートのサイズを考慮し、広めにクリア
        sheet.values().clear(
            spreadsheetId=SPREADSHEET_ID, 
            range=f"{RELEASE_SHEET}!A2:E1000"
        ).execute()
        
        # 3. データ書き込み
        sheet.values().update(
            spreadsheetId=SPREADSHEET_ID,
            # A2から開始し、データ全体を書き込む
            range=f"{RELEASE_SHEET}!A2:C",
            valueInputOption="USER_ENTERED", 
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
    OpenAI ChatGPTリリースノートのURLから日付(H1)、タイトル(H3)、本文(<p>, <ul>)を抽出します。
    """
    print(f"🔍 {url} からリリースノートを抽出中...")
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status() 
    except RequestException as e:
        print(f"Error fetching URL: {e}")
        return []

    soup = BeautifulSoup(response.content, 'html.parser')
    data_to_write = [] # 書き込み形式: [['日付', 'タイトル', '本文'], ...]
    
    # ページ内の全ての日付（<h1>タグ）を取得
    h1_elements = soup.find_all('h1')
    
    if not h1_elements:
        print("❌ <h1>タグ（リリース日）がページ内から一つも見つかりませんでした。")
        return []
    
    for h1_tag in h1_elements:
        current_date = h1_tag.get_text(strip=True)
        
        # H1タグの次の兄弟要素から、H3タイトルと本文を探す
        sibling = h1_tag.next_sibling
        
        # この日付セクションの最初のH3タイトルを探す
        # H3がない場合は、H1の直後のPタグ以降が本文となる（例: October 22, 2025）
        first_h3 = h1_tag.find_next_sibling('h3')

        if first_h3:
            # --- (A) 複数のH3タイトルが存在するセクションの処理 ---
            
            # H1タグの次の要素から、H1が現れるまで処理を続ける
            while sibling and sibling.name != 'h1':
                if sibling.name == 'h3':
                    # 新しいH3タイトルが見つかった場合
                    current_title = sibling.get_text(strip=True)
                    content_parts = []
                    
                    # H3タグの次の兄弟要素を辿り、次のH1またはH3が現れるまでを本文とする
                    sub_sibling = sibling.next_sibling
                    while sub_sibling and sub_sibling.name not in ['h1', 'h3']:
                        if sub_sibling.name in ['p', 'ul']:
                            content = sub_sibling.get_text(separator='\n', strip=True)
                            if content:
                                content_parts.append(content)
                        sub_sibling = sub_sibling.next_sibling
                    
                    full_content = '\n\n'.join(content_parts)
                    
                    # データを追加: [日付, タイトル, 本文]
                    if full_content:
                        data_to_write.append([current_date, current_title, full_content])
                        
                    # 兄弟要素の走査をH3の次の要素から再開
                    sibling = sub_sibling
                else:
                    # H3以外の要素（テキストノードなど）はスキップ
                    sibling = sibling.next_sibling
        
        else:
            # --- (B) H3タイトルがないセクションの処理 (日付と本文のみ) ---
            current_title = "" # B列は空欄
            content_parts = []
            
            # H1タグの次の要素から、次のH1が現れるまでを本文とする
            while sibling and sibling.name != 'h1':
                if sibling.name in ['p', 'ul']:
                    content = sibling.get_text(separator='\n', strip=True)
                    if content:
                        content_parts.append(content)
                sibling = sibling.next_sibling
            
            full_content = '\n\n'.join(content_parts)
            
            # データを追加: [日付, タイトル(空), 本文]
            if full_content:
                data_to_write.append([current_date, current_title, full_content])
    
    print(f"✅ 抽出完了。{len(data_to_write)} 件のリリース情報を検出しました。")
    return data_to_write


# ==========================
# メイン実行
# ==========================
if __name__ == "__main__":
    
    # スプレッドシートIDが変更されているかチェック
    if SPREADSHEET_ID == "1waFSSryRnz1H0EzgUoTPjcqjfyssd3PbXclANx0YOZA":
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
