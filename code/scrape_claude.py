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
URL = "https://platform.claude.com/docs/ja/release-notes/overview"
HISTORY_FILE = "history/claude_release_notes.json"
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
                {"role": "system", "content": "あなたは優秀なエンジニア兼翻訳者です。Anthropic Claudeのアップデート情報を、日本のユーザー向けに分かりやすく日本語で要約して翻訳してください。"},
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
    try:
        requests.post(SLACK_WEBHOOK_URL, json=payload)
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

    # 指定されたクラス名（スペース区切りはドットで繋ぐ）
    TARGET_CLASS_SELECTOR = ".group.relative.pt-6.pb-2"

    try:
        print(f"🔍 アクセス中: {URL}")
        driver.get(URL)
        wait = WebDriverWait(driver, 20)
        
        # 要素がロードされるのを待機
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, TARGET_CLASS_SELECTOR)))
        
        # 指定されたクラスを持つ要素（日付見出し部分）を取得
        elements = driver.find_elements(By.CSS_SELECTOR, TARGET_CLASS_SELECTOR)
        
        # 1つ目から6つ目を対象にする (インデックス 0〜5)
        end_idx = min(6, len(elements))

        for i in range(0, end_idx):
            target_el = elements[i]
            date_title = target_el.text.strip()
            
            if not date_title:
                continue

            new_history.append(date_title)

            if date_title not in history:
                print(f"✨ Claude 新規アップデート発見: {date_title}")
                
                # JavaScriptロジックを強化：
                # 見出し要素からスタートし、DOMツリー上で「次のアップデート見出し」に
                # ぶつかるまで、すべてのテキストノードを収集します。
                script = """
                var startNode = arguments[0];
                var selector = arguments[1];
                var result = "";
                
                // 1. 開始要素の次の要素から探索開始
                var curr = startNode.nextElementSibling;
                
                // もし隣に要素がなければ親に上がって隣を探す（入れ子対策）
                if (!curr) {
                    curr = startNode.parentElement.nextElementSibling;
                }

                while (curr) {
                    // 次のアップデートセクション（同じクラスを持つ要素）が見つかったら終了
                    // 自身または子要素にそのクラスがあるかチェック
                    if (curr.matches(selector) || curr.querySelector(selector)) break;
                    
                    result += curr.innerText + "\\n";
                    curr = curr.nextElementSibling;
                    
                    // 親要素の境界を超えて次のセクションを探すための処理
                    if (!curr && startNode.parentElement) {
                        curr = startNode.parentElement.nextElementSibling;
                    }
                }
                return result;
                """
                content_text = driver.execute_script(script, target_el, TARGET_CLASS_SELECTOR)
                
                # デバッグ用：取得結果が空の場合の対策
                if not content_text.strip():
                    content_text = "(コンテンツの取得に失敗しました。サイト構造が変更された可能性があります)"

                full_text = f"【{date_title}】\n{content_text}"
                
                translated_text = translate_text(full_text)
                post_targets.append(translated_text)

        # 新規があればSlack送信
        if post_targets:
            for post in post_targets:
                send_slack(f"📢 *Claude リリースノート更新*\n\n{post}")
            print(f"✅ {len(post_targets)} 件の更新をSlackに送信しました。")
        else:
            print("📭 新しいアップデートはありませんでした。")

        # 今回取得した上位件数分で履歴を更新
        save_history(new_history)

    finally:
        driver.quit()

if __name__ == "__main__":
    main()
