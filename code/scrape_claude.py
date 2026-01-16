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
    # メッセージ末尾にURLを付与
    source_url = "https://platform.claude.com/docs/ja/release-notes/overview"
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

    # 指定されたクラス名
    TARGET_CLASS_SELECTOR = ".group.relative.pt-6.pb-2"

    try:
        print(f"🔍 調査開始: {URL}")
        driver.get(URL)
        wait = WebDriverWait(driver, 20)
        
        # ターゲット要素が読み込まれるまで待機
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, TARGET_CLASS_SELECTOR)))
        
        elements = driver.find_elements(By.CSS_SELECTOR, TARGET_CLASS_SELECTOR)
        
        # 1番目から6番目までを対象にする
        end_idx = min(6, len(elements))
        
        for i in range(0, end_idx):
            target_el = elements[i]
            date_title = target_el.text.strip()
            
            if not date_title:
                continue

            new_history.append(date_title)

            # 履歴になければ新規投稿
            if date_title not in history:
                print(f"✨ 新規アップデート発見: {date_title}")
                
                # JavaScriptで「次のアップデート見出し」が現れるまでコンテンツを収集
                script = """
                var startNode = arguments[0];
                var selector = arguments[1];
                var result = "";
                
                // 次の要素、または親の次の要素から開始（入れ子構造対策）
                var curr = startNode.nextElementSibling;
                if (!curr && startNode.parentElement) {
                    curr = startNode.parentElement.nextElementSibling;
                }

                while (curr) {
                    // 次のセクションの見出しクラスが見つかったら停止
                    if (curr.matches(selector) || curr.querySelector(selector)) break;
                    
                    result += curr.innerText + "\\n";
                    
                    // 次の兄弟要素へ
                    if (curr.nextElementSibling) {
                        curr = curr.nextElementSibling;
                    } else if (curr.parentElement) {
                        // 兄弟がいなければ親の兄弟へ（DOM構造の深さに対応）
                        curr = curr.parentElement.nextElementSibling;
                    } else {
                        curr = null;
                    }
                }
                return result;
                """
                content_text = driver.execute_script(script, target_el, TARGET_CLASS_SELECTOR)
                
                if not content_text.strip():
                    content_text = "(コンテンツのテキスト抽出に失敗しました。構造を確認してください)"

                full_text = f"【{date_title}】\n{content_text}"
                
                # 翻訳・要約
                translated_text = translate_text(full_text)
                post_targets.append(translated_text)

        # Slack送信処理
        if post_targets:
            # 古い順に送りたい場合は reversed(post_targets) にする
            for post in post_targets:
                send_slack(f"📢 *Claude リリースノート更新*\n\n{post}")
            print(f"✅ {len(post_targets)} 件の更新を送信しました。")
        else:
            print("📭 新しい更新はありません。")

        # 履歴の更新（今回チェックした上位6件を保存）
        save_history(new_history)

    except Exception as e:
        print(f"❌ エラーが発生しました: {e}")
    finally:
        driver.quit()

if __name__ == "__main__":
    main()
