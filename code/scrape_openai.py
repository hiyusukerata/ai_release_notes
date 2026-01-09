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
URL = "https://help.openai.com/en/articles/6825453-chatgpt-release-notes"
HISTORY_FILE = "history/openai.json"
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
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
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
                {"role": "system", "content": "あなたは優秀な翻訳者です。OpenAIのアップデート情報を、日本のユーザー向けに分かりやすく日本語で要約して翻訳してください。"},
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
    payload = {"text": message}
    requests.post(SLACK_WEBHOOK_URL, json=payload)

# ==========================
# クロール処理
# ==========================
def main():
    driver = init_webdriver()
    history = load_history()
    new_history = []
    post_targets = []

    try:
        driver.get(URL)
        wait = WebDriverWait(driver, 20)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "h1")))
        
        h1_elements = driver.find_elements(By.TAG_NAME, "h1")
        
        # 2番目から6番目のh1を対象にする (インデックス 1〜5)
        # ページ内のh1が少ない場合は、存在する分だけ取得
        end_idx = min(6, len(h1_elements))
        
        for i in range(1, end_idx):
            target_h1 = h1_elements[i]
            date_title = target_h1.text.strip()
            new_history.append(date_title) # 今回見つかったものを保存対象に

            # 履歴になければ新規投稿対象
            if date_title not in history:
                print(f"✨ 新規アップデート発見: {date_title}")
                
                # JavaScriptで次のh1までのコンテンツを取得
                script = """
                var startNode = arguments[0];
                var result = "";
                var curr = startNode.nextElementSibling;
                while (curr) {
                    if (curr.tagName === 'H1') break;
                    result += curr.innerText + "\\n";
                    curr = curr.nextElementSibling;
                }
                return result;
                """
                content_text = driver.execute_script(script, target_h1)
                full_text = f"【{date_title}】\n{content_text}"
                
                # 翻訳
                translated_text = translate_text(full_text)
                post_targets.append(translated_text)

        # 新規があればSlack送信
        if post_targets:
            for post in post_targets:
                send_slack(f"📢 *ChatGPT 新機能アップデート*\n\n{post}")
            print(f"✅ {len(post_targets)} 件の更新をSlackに送信しました。")
        else:
            print("📭 新しいアップデートはありませんでした。")

        # 履歴を更新（今回のクロール結果で上書き）
        save_history(new_history)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
