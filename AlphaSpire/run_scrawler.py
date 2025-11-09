"""
run_scrawler.py
合併爬蟲和預處理功能，使用本地 Ollama gemma3:1b 模型
"""

import time
import datetime
import json
import unicodedata
import requests
from pathlib import Path
from bs4 import BeautifulSoup
from loguru import logger
from playwright.sync_api import sync_playwright

from utils.config_loader import ConfigLoader

# ============================================================================
# 配置
# ============================================================================
OLLAMA_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma3:1b"

# 目錄設置
BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "wq_posts" / "raw_posts"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR = BASE_DIR / "data" / "wq_posts" / "processed_posts"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
HELPFUL_DIR = BASE_DIR / "data" / "wq_posts" / "helpful_posts"
HELPFUL_DIR.mkdir(parents=True, exist_ok=True)

COOKIES_FILE = RAW_DIR / "cookies.json"


# ============================================================================
# 文本清理和提取
# ============================================================================

def clean_text(text: str) -> str:
    """清洗文本中非utf-8字符，統一為 NFC 格式"""
    if not text:
        return ""
    cleaned = text.encode("utf-8", errors="ignore").decode("utf-8", errors="ignore")
    cleaned = unicodedata.normalize("NFC", cleaned)
    return cleaned.strip()


def extract_post_info(html_content: str) -> dict:
    """從單個HTML中抽取 description, title, post-body, post-comments"""
    soup = BeautifulSoup(html_content, "html.parser")

    # description
    description = ""
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        description = meta_desc.get("content").strip()
    if not description:
        og_desc = soup.find("meta", property="og:description")
        if og_desc and og_desc.get("content"):
            description = og_desc.get("content").strip()

    # title
    title = ""
    og_title = soup.find("meta", property="og:title")
    if og_title and og_title.get("content"):
        title = og_title.get("content").strip()
    if not title and soup.title:
        title = soup.title.string.strip()

    # post-body
    post_body = ""
    body_div = soup.find("div", class_="post-body")
    if body_div:
        post_body = body_div.get_text("\n", strip=True)

    # comments
    comments = []
    for section in soup.select("section.comment-body"):
        text = section.get_text("\n", strip=True)
        if text:
            comments.append(text)

    return {
        "title": title,
        "description": description,
        "post_body": post_body,
        "post_comments": comments,
    }



def build_check_if_blog_helpful(post_file):
    """
    構建用於判斷帖子是否有幫助的 prompt（字符串格式，類似 adaptive_alpha_miner）
    
    Args:
        post_file: 處理後的 JSON 文件路徑
    
    Returns:
        str: 格式化的 prompt 字符串
    """
    # 讀取帖子內容
    with open(post_file, 'r', encoding='utf-8') as f:
        post_data = json.load(f)
    
    title = post_data.get('title', '')
    description = post_data.get('description', '')
    post_body = post_data.get('post_body', '')
    
    # 構建單個字符串 prompt（參考 adaptive_alpha_miner 的風格）
    prompt = f"""You are an expert in quantitative finance and alpha factor research.
Analyze the following WorldQuant community post and determine if it contains useful information for alpha factor mining.

A helpful post should contain:
- Specific alpha factor ideas or expressions
- Technical discussions about factor construction
- Mathematical formulas or data operations
- Trading strategies or signal generation methods
- Performance analysis or backtesting insights
- Code examples or implementation details

A post is NOT helpful if it only contains:
- General questions without technical content
- Administrative/account issues
- Simple greetings or thank you messages
- Off-topic discussions

POST TITLE:
{title}

POST DESCRIPTION:
{description}

POST BODY:
{post_body[:2000]}

TASK:
Based on the above content, is this post helpful for alpha factor research?
Answer with ONLY ONE WORD: "YES" or "NO"

ANSWER:"""

    return prompt



# ============================================================================
# Ollama LLM 調用
# ============================================================================

def call_ollama_llm(prompt: str, model: str = OLLAMA_MODEL, timeout: int = 60) -> str:
    """
    調用本地 Ollama 模型
    
    Args:
        prompt: 提示詞
        model: 模型名稱
        timeout: 超時時間（秒）
    
    Returns:
        模型的響應文本
    """
    url = f"{OLLAMA_URL}/api/generate"
    
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 100  # 限制輸出長度
        }
    }
    
    try:
        logger.info(f"🤖 調用 Ollama 模型: {model}")
        start_time = time.time()
        
        response = requests.post(url, json=payload, timeout=timeout)
        
        elapsed_time = time.time() - start_time
        logger.info(f"⏱️  Ollama 響應時間: {elapsed_time:.2f}s")
        
        if response.status_code == 200:
            result = response.json()
            response_text = result.get('response', '').strip()
            logger.info(f"💬 Ollama 回應: {response_text[:100]}...")
            return response_text
        else:
            logger.error(f"❌ Ollama API 錯誤: {response.status_code}")
            logger.error(f"   {response.text[:200]}")
            return ""
            
    except requests.exceptions.Timeout:
        logger.error(f"⏱️  Ollama 請求超時（{timeout}s）")
        return ""
    except Exception as e:
        logger.error(f"❌ 調用 Ollama 失敗: {e}")
        return ""


def check_if_post_helpful(post_file: Path) -> bool:
    """
    使用 Ollama 檢查帖子是否有幫助
    
    Args:
        post_file: 處理後的 JSON 文件路徑
    
    Returns:
        True 如果有幫助，False 否則
    """
    try:
        # 構建 prompt（直接返回字符串）
        prompt = build_check_if_blog_helpful(post_file)
        
        # 調用 Ollama
        answer = call_ollama_llm(prompt, model=OLLAMA_MODEL)
        
        if not answer:
            logger.warning(f"⚠️  Ollama 返回空響應")
            return False
        
        logger.info(f"🔎 判斷 {post_file.name} 是否有幫助: {answer}")
        
        # 判斷回答
        if answer.upper().startswith("Y"):
            logger.info(f"✅ 帖子被判定為有幫助")
            return True
        else:
            logger.info(f"❌ 帖子被判定為無幫助")
            return False
            
    except Exception as e:
        logger.error(f"⚠️  check_if_post_helpful 錯誤: {e}")
        return False


# ============================================================================
# 爬蟲相關函數
# ============================================================================


def _save_raw_html(post_id: str, html_content: str):
    """保存原始HTML文件"""
    now_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = RAW_DIR / f"{now_str}_{post_id}.html"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    logger.info(f"💾 保存原始 HTML 到 {file_path}")
    return file_path


def process_html_to_json(html_file: Path, post_id: str) -> Path:
    """
    處理單個 HTML 文件為 JSON
    
    Args:
        html_file: HTML 文件路徑
        post_id: 帖子 ID
    
    Returns:
        處理後的 JSON 文件路徑
    """
    out_file = PROCESSED_DIR / f"{html_file.stem}.json"
    
    logger.info(f"📝 處理 {html_file.name}...")
    html_content = html_file.read_text(encoding="utf-8", errors="ignore")
    html_content = clean_text(html_content)
    
    post_info = extract_post_info(html_content)
    
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(post_info, f, ensure_ascii=False, indent=2)
    
    logger.info(f"✅ 保存處理後的 JSON 到 {out_file}")
    return out_file


def scrape_new_posts(limit: int = 50, auto_process: bool = True):
    """
    Playwright 抓取 WorldQuant Consultant 新帖子
    
    Args:
        limit: 抓取帖子數量上限（默認 50）
        auto_process: 是否自動處理並判斷是否有幫助
    
    Returns:
        新帖子元數據列表
    """
    topic_url = ConfigLoader.get("worldquant_consultant_posts_url")
    new_posts_meta = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        logger.info(f"🌐 導航到主題頁面: {topic_url}")
        page.goto(topic_url)

        logger.info("⏸️  請在瀏覽器中完成登錄...")
        input("✅ 已登錄並看到帖子列表後按回車繼續...")

        fetched_count = 0
        has_next = True
        
        while has_next and fetched_count < limit:
            # 等待頁面加載
            try:
                page.wait_for_load_state("load", timeout=60000)
            except:
                logger.warning("⚠️  load_state timeout, continue anyway")
            time.sleep(5)

            html = page.content()
            soup = BeautifulSoup(html, "html.parser")

            # 抽取帖子鏈接
            post_links = soup.select("a[href*='/community/posts/']")
            logger.info(f"📋 找到 {len(post_links)} 個帖子鏈接")

            for link in post_links:
                if fetched_count >= limit:
                    break
                    
                post_url = link.get("href")
                if not post_url:
                    continue
                    
                full_url = (
                    post_url
                    if post_url.startswith("http")
                    else "https://support.worldquantbrain.com" + post_url
                )

                import re
                m = re.search(r"/posts/(\d+)", full_url)
                if not m:
                    continue
                post_id = m.group(1)

                # 抓取帖子詳情頁
                logger.info(f"\n{'='*60}")
                logger.info(f"📄 抓取帖子 {fetched_count + 1}/{limit}: ID={post_id}")
                logger.info(f"{'='*60}")
                
                page.goto(full_url)
                try:
                    page.wait_for_load_state("load", timeout=60000)
                except:
                    logger.warning("⚠️  Timeout loading post page")
                time.sleep(3)
                
                html_content = page.content()
                html_file = _save_raw_html(post_id, html_content)

                title = link.get_text(strip=True)
                post_meta = {
                    "id": post_id,
                    "title": title,
                    "url": full_url,
                    "time": "",
                }
                new_posts_meta.append(post_meta)
                fetched_count += 1

                # 自動處理
                if auto_process:
                    logger.info(f"\n🔄 開始處理帖子 {post_id}...")
                    json_file = process_html_to_json(html_file, post_id)
                    
                    # 判斷是否有幫助
                    logger.info(f"\n🤖 使用 Ollama 判斷帖子是否有幫助...")
                    if check_if_post_helpful(json_file):
                        helpful_file = HELPFUL_DIR / f"{json_file.name}"
                        
                        with open(json_file, 'r', encoding='utf-8') as f:
                            post_info = json.load(f)
                        
                        with open(helpful_file, "w", encoding="utf-8") as f:
                            json.dump(post_info, f, ensure_ascii=False, indent=2)
                        
                        logger.info(f"⭐ 有幫助的帖子已保存到 {helpful_file}")
                    else:
                        logger.info(f"📝 帖子處理完成但未標記為有幫助")

                # 回到列表頁
                page.goto(topic_url)
                try:
                    page.wait_for_load_state("load", timeout=60000)
                except:
                    logger.warning("⚠️  Timeout loading topic page")
                time.sleep(5)

            # 翻頁
            next_button = page.locator("a:has-text('Next')")
            if next_button.count() > 0 and fetched_count < limit:
                logger.info("➡️  點擊 Next 按鈕...")
                next_button.first.click()
                try:
                    page.wait_for_load_state("load", timeout=60000)
                except:
                    logger.warning("⚠️  Timeout after clicking Next")
                time.sleep(5)
            else:
                has_next = False

        # 保存 cookies
        context.storage_state(path=str(COOKIES_FILE))
        logger.info(f"🍪 保存 cookies 到 {COOKIES_FILE}")
        browser.close()

    logger.info(f"\n{'='*60}")
    logger.info(f"✅ 爬取完成！總共抓取 {len(new_posts_meta)} 個新帖子")
    logger.info(f"{'='*60}")
    return new_posts_meta


def preprocess_existing_posts():
    """批量處理已有的未處理 HTML 文件"""
    raw_files = list(RAW_DIR.glob("*.html"))
    logger.info(f"\n📂 找到 {len(raw_files)} 個原始 HTML 文件")
    
    processed_count = 0
    helpful_count = 0

    for raw_file in raw_files:
        post_id = raw_file.stem
        out_file = PROCESSED_DIR / f"{post_id}.json"
        
        if out_file.exists():
            logger.info(f"⏭️  跳過已處理: {raw_file.name}")
            continue

        logger.info(f"\n{'='*60}")
        logger.info(f"📝 處理: {raw_file.name}")
        
        out_file = process_html_to_json(raw_file, post_id)
        processed_count += 1
        
        # 判斷是否有幫助
        if check_if_post_helpful(out_file):
            helpful_file = HELPFUL_DIR / f"{post_id}.json"
            
            with open(out_file, 'r', encoding='utf-8') as f:
                post_info = json.load(f)
            
            with open(helpful_file, "w", encoding="utf-8") as f:
                json.dump(post_info, f, ensure_ascii=False, indent=2)
            
            helpful_count += 1
            logger.info(f"⭐ 有幫助的帖子已保存")

    logger.info(f"\n{'='*60}")
    logger.info(f"✅ 處理完成！")
    logger.info(f"   新處理: {processed_count} 個文件")
    logger.info(f"   有幫助: {helpful_count} 個帖子")
    logger.info(f"{'='*60}")


# ============================================================================
# 主程序
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='WorldQuant 帖子爬蟲和處理工具（使用 Ollama）')
    parser.add_argument('--mode', type=str, 
                       choices=['scrape', 'process', 'both'],
                       default='both',
                       help='運行模式: scrape(僅爬取), process(僅處理), both(爬取並處理)')
    parser.add_argument('--limit', type=int, default=50,
                       help='抓取帖子數量上限（默認: 50）')
    parser.add_argument('--model', type=str, default='gemma3:1b',
                       help='Ollama 模型名稱（默認: gemma3:1b）')
    
    args = parser.parse_args()
    
    # 設置全局模型
    global OLLAMA_MODEL
    OLLAMA_MODEL = args.model
    
    logger.info(f"\n{'='*80}")
    logger.info(f"WorldQuant 帖子爬蟲和處理工具")
    logger.info(f"使用 Ollama 模型: {OLLAMA_MODEL}")
    logger.info(f"{'='*80}\n")
    
    if args.mode in ['scrape', 'both']:
        logger.info("🚀 開始爬取新帖子...")
        new_posts = scrape_new_posts(limit=args.limit, auto_process=True)
        logger.info(f"✅ 爬取了 {len(new_posts)} 個新帖子")
    
    if args.mode == 'process':
        logger.info("🔄 處理現有未處理的帖子...")
        preprocess_existing_posts()
    
    logger.info(f"\n{'='*80}")
    logger.info(f"✅ 全部完成！")
    logger.info(f"{'='*80}")


if __name__ == "__main__":
    main()

