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
URL = "https://docs.x.ai/docs/release-notes"
HISTORY_FILE = "history/grok_release_notes.json"
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
                {"role": "system", "content": "あなたは優秀なエンジニア兼翻訳者です。x.aiのGrokに関するアップデート情報を、日本のユーザー向けに分かりやすく日本語で要約して翻訳してください。"},
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
    # メッセージの末尾にGrokのリリースノートURLを追加
    footer_url = "https://docs.x.ai/docs/release-notes"
    payload = {"text": f"{message}\n\n{footer_url}"}
    requests.post(SLACK_WEBHOOK_URL, json=payload)

# ==========================
# クロール処理
# ==========================
def main():
    driver = init_webdriver()
    history = load_history()
    new_history = []
    post_targets = []

    # 指定された日付クラスのセレクター
    TARGET_CLASS_SELECTOR = ".relative.-bottom-4"

    try:
        print(f"🔍 Grok 調査開始: {URL}")
        driver.get(URL)
        wait = WebDriverWait(driver, 20)
        
        # 要素が読み込まれるのを待機
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, TARGET_CLASS_SELECTOR)))
        
        # 日付要素を取得
        date_elements = driver.find_elements(By.CSS_SELECTOR, TARGET_CLASS_SELECTOR)
        
        # 上位6件を対象にする
        end_idx = min(6, len(date_elements))
        
        for i in range(0, end_idx):
            target_el = date_elements[i]
            date_title = target_el.text.strip()
            
            if not date_title:
                continue

            new_history.append(date_title)

            # 履歴になければ新規投稿対象
            if date_title not in history:
                print(f"✨ Grok 新規アップデート発見: {date_title}")
                
                # JavaScriptで次の日付要素が現れるまでのコンテンツを取得
                # Grokの構造に合わせて、親要素を辿りながらテキストを収集
                script = """
                var startNode = arguments[0];
                var selector = arguments[1];
                var result = "";
                var curr = startNode.parentElement ? startNode.parentElement.nextElementSibling : startNode.nextElementSibling;

                while (curr) {
                    if (curr.querySelector(selector) || curr.matches(selector)) break;
                    result += curr.innerText + "\\n";
                    curr = curr.nextElementSibling;
                }
                return result;
                """
                content_text = driver.execute_script(script, target_el, TARGET_CLASS_SELECTOR)
                
                full_text = f"【{date_title}】\n{content_text}"
                
                # 翻訳
                translated_text = translate_text(full_text)
                post_targets.append(translated_text)

        # 新規があればSlack送信
        if post_targets:
            for post in post_targets:
                send_slack(f"📢 *Grok リリースノート更新*\n\n{post}")
            print(f"✅ {len(post_targets)} 件の更新をSlackに送信しました。")
        else:
            print("📭 新しいアップデートはありませんでした。")

        # 履歴を更新
        save_history(new_history)

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
