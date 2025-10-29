import requests
from bs4 import BeautifulSoup
import gspread
import os
import sys

# --- 1. スクレッピング関数 ---

def extract_release_notes(url):
    """
    OpenAI ChatGPTリリースノートのURLから日付（<h2>）と内容（<p>、<ul>）を抽出します。
    """
    print(f"🔍 URL: {url} からリリースノートを抽出中...")
    try:
        # Webページを取得
        response = requests.get(url, timeout=10)
        response.raise_for_status() # HTTPエラーが発生した場合に例外を発生させる
    except requests.exceptions.RequestException as e:
        print(f"Error fetching URL: {e}")
        return []

    # BeautifulSoupでHTMLをパース
    soup = BeautifulSoup(response.content, 'html.parser')

    # リリースノートの主要なコンテナ要素（article-bodyクラスを持つdiv）を特定
    article_body = soup.find('div', class_='article-body')
    if not article_body:
        print("Error: Could not find the main article body.")
        return []

    release_notes = []
    current_date = None
    
    # article-body内の全ての子要素を順番に処理
    for element in article_body.children:
        # <h2>タグを検出: これがリリース日
        if element.name == 'h2':
            current_date = element.get_text(strip=True)
        
        # リリース内容を含む要素（<p>タグや<ul>タグ）を検出
        elif current_date and element.name in ['p', 'ul', 'div']: 
            # divタグも念のため含める
            
            # リリース内容を整形（リスト項目や改行を考慮）
            # get_text(separator='\n', ...)でリスト項目が改行されるようにする
            content = element.get_text(separator='\n', strip=True)
            
            # リリース内容が空でない、かつ日付が取得済みの場合に格納
            if content:
                if release_notes and release_notes[-1]['date'] == current_date:
                    # 既にこの日付でリリース内容が格納されている場合は内容を追記
                    release_notes[-1]['content'] += '\n\n' + content # 空行を挟んで連結
                else:
                    # 新しい日付の場合は新しいエントリとして追加
                    release_notes.append({
                        'date': current_date,
                        'content': content
                    })
    
    print(f"✅ 抽出完了。{len(release_notes)} 件のリリース情報を検出しました。")
    return release_notes

# --- 2. Google Sheets 書き込み関数 ---

def write_to_google_sheet(releases, spreadsheet_id, sheet_name):
    """
    抽出したリリース情報をGoogleスプレッドシートのA2以降に書き込みます。
    A列に日付、B列にリリース内容を記述します。
    """
    # 認証情報ファイルはスクリプトと同じディレクトリにあることを想定
    CREDENTIALS_FILE = 'service_account.json'
    
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"\n--- 致命的エラー ---")
        print(f"認証情報ファイル '{CREDENTIALS_FILE}' が見つかりません。")
        print(f"事前にGoogle Cloud Consoleで作成し、スクリプトと同じディレクトリに配置してください。")
        sys.exit(1)

    try:
        # gspreadでサービスアカウント認証
        gc = gspread.service_account(filename=CREDENTIALS_FILE)
        
        # スプレッドシートとワークシートを開く
        spreadsheet = gc.open_by_key(spreadsheet_id)
        worksheet = spreadsheet.worksheet(sheet_name)
        
        # 書き込むデータの整形: A列に日付、B列に内容
        # 形式: [['日付1', '内容1'], ['日付2', '内容2'], ...]
        data_to_write = []
        for release in releases:
            # [A列の値, B列の値] のリストを作成
            data_to_write.append([release['date'], release['content']])

        # A1にヘッダーを書き込む
        worksheet.update('A1:B1', [['日付', 'リリース内容']], value_input_option='USER_ENTERED')
        
        # A2セル以降にデータを書き込む
        if data_to_write:
            num_rows_written = len(data_to_write)
            
            # A2からB列の最終行までをクリア
            clear_range = f'A2:B{worksheet.row_count}'
            worksheet.batch_clear([clear_range])

            # A2から開始し、データ全体を一度に書き込む
            worksheet.update('A2', data_to_write, value_input_option='USER_ENTERED')
            
            print("\n-------------------------------------------------------")
            print(f"✅ Googleスプレッドシートへの書き込みが完了しました。")
            print(f"シート名: {sheet_name}")
            print(f"書き込み行数: {num_rows_written} 件")
            print(f"書き込み範囲: A2:B{num_rows_written + 1}")
            print("-------------------------------------------------------")
        else:
            print("\n💡 抽出されたリリース情報がありませんでした。書き込みをスキップします。")

    except gspread.exceptions.SpreadsheetNotFound:
        print(f"Error: スプレッドシートID '{spreadsheet_id}' が見つかりませんでした。IDを確認してください。")
        sys.exit(1)
    except gspread.exceptions.WorksheetNotFound:
        print(f"Error: シート名 '{sheet_name}' が見つかりませんでした。シート名を確認してください。")
        sys.exit(1)
    except Exception as e:
        print(f"Error writing to Google Sheets: {e}")
        sys.exit(1)


# --- 3. 実行部分 ---

if __name__ == "__main__":
    # --- 🚨 設定値 (実行前に必ず変更してください) 🚨 ---
    URL = "https://help.openai.com/en/articles/6825453-chatgpt-release-notes"
    
    # GoogleスプレッドシートのIDをここに設定してください。
    # URL: https://docs.google.com/spreadsheets/d/ ここがID /edit#gid=0
    SPREADSHEET_ID = "YOUR_SPREADSHEET_ID_HERE" 
    
    # 書き込みたいシートの名前（例: 'シート1' や 'Release Notes' など）
    SHEET_NAME = "Release Notes"
    # ---

    if SPREADSHEET_ID == "YOUR_SPREADSHEET_ID_HERE":
        print("\n--- 警告 ---")
        print("設定値 SPREADSHEET_ID をあなたのスプレッドシートIDに置き換えてください。処理を終了します。")
    else:
        releases = extract_release_notes(URL)
        if releases:
            write_to_google_sheet(releases, SPREADSHEET_ID, SHEET_NAME)
