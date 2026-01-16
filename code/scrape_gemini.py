import os
import json
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from openai import OpenAI

# ==========================
# 設定情報
# ==========================
URL = "https://ai.google.dev/gemini-api/docs/changelog?hl=ja"
HISTORY_FILE = "history/gemini_changelog.json"
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

# ==========================
# WebDriver 初期化
# ==========================
def init_webdriver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    return webdriver.Chrome(options=options)

# ==========================
# 履歴の読み書き
# ==========================
def load_history():
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_history(history):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# ==========================
# ChatGPT API による翻訳
# ==========================
def translate_text(text):
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "あなたは優秀なエンジニア兼翻訳者です。Google Gemini APIのアップデート情報を、日本のユーザー向けに分かりやすく日本語で要約して翻訳してください。"},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"⚠️ 翻訳エラー: {e}")
        return text

# ==========================
# Slack通知
# ==========================
def send_slack(message):
    # メッセージ末尾にGeminiのURLを付与
    source_url = "https://ai.google.dev/gemini-api/docs/changelog?hl=ja"
    full_text = f"{message}\n\n🔗 出典: {source_url}"
    
    payload = {"text": full_text}
    try:
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        response.raise_for_status()
    except Exception as e:
        print(f"⚠️ Slack送信エラー: {e}")

# ==========================
# クロール処理
# ==========================
def main():
    driver = init_webdriver()
    history = load_history()
    new_history = []
    post_targets = []

    try:
        print(f"🔍 Gemini 調査開始: {URL}")
        driver.get(URL)
        wait = WebDriverWait(driver, 20)
        
        # h2要素がロードされるのを待機
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "h2")))
        
        h2_elements = driver.find_elements(By.TAG_NAME, "h2")
        
        # 1番目から6番目のh2を対象にする
        end_idx = min(6, len(h2_elements))
        
        for i in range(0, end_idx):
            target_h2 = h2_elements[i]
            date_title = target_h2.text.strip()
            
            if not date_title:
                continue

            new_history.append(date_title)

            # 履歴になければ新規投稿
            if date_title not in history:
                print(f"✨ Gemini 新規アップデート発見: {date_title}")
                
                # JavaScriptで次のh2までのコンテンツを取得
                script = """
                var startNode = arguments[0];
                var result = "";
                var curr = startNode.nextElementSibling;
                while (curr) {
                    if (curr.tagName === 'H2') break;
                    result += curr.innerText + "\\n";
                    curr = curr.nextElementSibling;
                }
                return result;
                """
                content_text = driver.execute_script(script, target_h2)
                
                if not content_text.strip():
                    content_text = "(コンテンツの取得に失敗しました)"

                full_text = f"【{date_title}】\n{content_text}"
                
                # 翻訳
                translated_text = translate_text(full_text)
                post_targets.append(translated_text)

        # Slack送信
        if post_targets:
            for post in post_targets:
                send_slack(f"📢 *Gemini API アップデート情報*\n\n{post}")
            print(f"✅ {len(post_targets)} 件の更新を送信しました。")
        else:
            print("📭 新しい更新はありません。")

        save_history(new_history)

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
