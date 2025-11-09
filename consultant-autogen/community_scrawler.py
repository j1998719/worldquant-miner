"""
community_scrawler.py - Pure API version (no manual login)
尝试使用纯 API/requests 方式访问 WorldQuant 社区论坛
"""

import json
import time
import re
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from loguru import logger

# --- 配置 ---
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data" / "wq_community"
RAW_DIR = DATA_DIR / "raw_posts"
PROCESSED_DIR = DATA_DIR / "processed_posts"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# 中文论坛 topic URL
TOPIC_URL = "https://support.worldquantbrain.com/hc/en-us/community/topics/12913416465431-%E4%B8%AD%E6%96%87%E8%AE%BA%E5%9D%9B"
# Zendesk API endpoint (可能需要认证)
API_BASE = "https://support.worldquantbrain.com/api/v2"


class CommunityScrawler:
    """使用纯 API 方式爬取 WorldQuant 社区帖子"""
    
    def __init__(self):
        self.session = requests.Session()
        # 使用更真实的浏览器 headers
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
        })
        self.topic_id = "12913416465431"
        self.cookies_file = RAW_DIR / "session_cookies.json"
        self._load_cookies()
    
    def _load_cookies(self):
        """从文件加载 cookies"""
        if self.cookies_file.exists():
            try:
                with open(self.cookies_file, 'r') as f:
                    cookies_dict = json.load(f)
                    for name, value in cookies_dict.items():
                        self.session.cookies.set(name, value)
                logger.info(f"Loaded {len(cookies_dict)} cookies from {self.cookies_file}")
            except Exception as e:
                logger.warning(f"Failed to load cookies: {e}")
    
    def _save_cookies(self):
        """保存 cookies 到文件"""
        try:
            cookies_dict = {cookie.name: cookie.value for cookie in self.session.cookies}
            with open(self.cookies_file, 'w') as f:
                json.dump(cookies_dict, f, indent=2)
            logger.info(f"Saved {len(cookies_dict)} cookies to {self.cookies_file}")
        except Exception as e:
            logger.warning(f"Failed to save cookies: {e}")
    
    def test_access(self):
        """测试是否可以访问论坛页面（无需登录）"""
        logger.info(f"Testing access to {TOPIC_URL}")
        try:
            response = self.session.get(TOPIC_URL, timeout=30, allow_redirects=True)
            logger.info(f"Status Code: {response.status_code}")
            logger.info(f"Final URL: {response.url}")
            
            # 保存当前的 cookies
            self._save_cookies()
            
            if response.status_code == 200:
                logger.success("✓ Successfully accessed the topic page!")
                return True
            elif response.status_code == 403:
                logger.warning("✗ Access denied (403). The site may require login or have anti-bot protection.")
                logger.info("Try option 3 in the menu to manually login and save cookies.")
                return False
            else:
                logger.error(f"✗ Failed with status code: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"✗ Error accessing page: {e}")
            return False
    
    def manual_login_with_browser(self):
        """使用 Playwright 打开浏览器进行手动登录，获取 cookies"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            return False
        
        logger.info("Opening browser for manual login...")
        logger.info("Please login in the browser, then press Enter in the terminal")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=False)
            context = browser.new_context()
            page = context.new_page()
            
            page.goto(TOPIC_URL)
            input("\n👉 Please login in the browser, then press Enter here to continue...")
            
            # 保存 cookies
            cookies = context.cookies()
            cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            
            with open(self.cookies_file, 'w') as f:
                json.dump(cookies_dict, f, indent=2)
            
            logger.success(f"✓ Saved {len(cookies_dict)} cookies to {self.cookies_file}")
            
            browser.close()
            
            # 重新加载 cookies 到 session
            self._load_cookies()
            return True
    
    def get_topic_posts_html(self, page=1):
        """
        获取 topic 页面的 HTML（分页）
        Zendesk 社区通常使用 ?page=N 参数
        """
        url = f"{TOPIC_URL}?page={page}"
        logger.info(f"Fetching page {page}: {url}")
        
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch page {page}: {e}")
            return None
    
    def parse_posts_from_html(self, html_content):
        """
        从 topic 页面 HTML 中解析帖子列表
        返回: list of {post_id, title, url, author, created_at}
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        posts = []
        
        # Zendesk 社区的帖子通常在这样的链接中
        # <a href="/hc/en-us/community/posts/...">
        post_links = soup.select('a[href*="/community/posts/"]')
        
        logger.info(f"Found {len(post_links)} post links")
        
        for link in post_links:
            href = link.get('href', '')
            if not href:
                continue
            
            # 提取 post_id
            match = re.search(r'/posts/(\d+)', href)
            if not match:
                continue
            
            post_id = match.group(1)
            title = link.get_text(strip=True)
            
            # 构建完整 URL
            full_url = href if href.startswith('http') else f"https://support.worldquantbrain.com{href}"
            
            # 尝试获取更多信息（作者、时间等）
            post_info = {
                'post_id': post_id,
                'title': title,
                'url': full_url,
                'scraped_at': datetime.now().isoformat()
            }
            
            # 避免重复
            if not any(p['post_id'] == post_id for p in posts):
                posts.append(post_info)
        
        return posts
    
    def fetch_post_detail(self, post_url):
        """
        获取单个帖子的详细内容
        """
        logger.info(f"Fetching post: {post_url}")
        
        try:
            response = self.session.get(post_url, timeout=30)
            response.raise_for_status()
            return response.text
        except Exception as e:
            logger.error(f"Failed to fetch post {post_url}: {e}")
            return None
    
    def parse_post_content(self, html_content):
        """
        解析帖子详情页的内容
        返回: {title, author, created_at, body, comments}
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # 提取标题
        title = ""
        title_tag = soup.find('h1')
        if title_tag:
            title = title_tag.get_text(strip=True)
        
        # 提取作者和时间（Zendesk 结构可能不同，需要调整）
        author = ""
        created_at = ""
        
        # 提取帖子正文
        body = ""
        # Zendesk 通常使用 class="post-body" 或类似的
        body_div = soup.find('div', class_='post-body')
        if not body_div:
            # 尝试其他可能的选择器
            body_div = soup.find('div', class_='article-body')
        if body_div:
            body = body_div.get_text('\n', strip=True)
        
        # 提取评论
        comments = []
        comment_sections = soup.select('div.comment-body, section.comment-body')
        for comment in comment_sections:
            comment_text = comment.get_text('\n', strip=True)
            if comment_text:
                comments.append(comment_text)
        
        return {
            'title': title,
            'author': author,
            'created_at': created_at,
            'body': body,
            'comments': comments,
            'comment_count': len(comments)
        }
    
    def save_raw_html(self, post_id, html_content):
        """保存原始 HTML"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = RAW_DIR / f"{timestamp}_{post_id}.html"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Saved raw HTML: {file_path}")
        return file_path
    
    def save_processed_json(self, post_id, post_data):
        """保存处理后的 JSON"""
        file_path = PROCESSED_DIR / f"{post_id}.json"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(post_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved processed JSON: {file_path}")
        return file_path
    
    def scrape_topic(self, max_pages=3, max_posts=20):
        """
        爬取整个 topic 的帖子
        
        Args:
            max_pages: 最多爬取多少页
            max_posts: 最多爬取多少个帖子
        """
        all_posts = []
        posts_scraped = 0
        
        for page in range(1, max_pages + 1):
            if posts_scraped >= max_posts:
                break
            
            logger.info(f"\n{'='*60}")
            logger.info(f"Page {page}")
            logger.info(f"{'='*60}")
            
            # 获取列表页 HTML
            html = self.get_topic_posts_html(page)
            if not html:
                logger.warning(f"Failed to get page {page}, stopping")
                break
            
            # 解析帖子列表
            posts = self.parse_posts_from_html(html)
            logger.info(f"Found {len(posts)} posts on page {page}")
            
            if not posts:
                logger.info("No more posts found, stopping")
                break
            
            # 爬取每个帖子的详细内容
            for post_info in posts:
                if posts_scraped >= max_posts:
                    break
                
                post_id = post_info['post_id']
                post_url = post_info['url']
                
                logger.info(f"\n[{posts_scraped + 1}/{max_posts}] Scraping post {post_id}: {post_info['title'][:50]}...")
                
                # 获取详情页
                detail_html = self.fetch_post_detail(post_url)
                if not detail_html:
                    continue
                
                # 保存原始 HTML
                self.save_raw_html(post_id, detail_html)
                
                # 解析内容
                content = self.parse_post_content(detail_html)
                
                # 合并信息
                full_post_data = {
                    **post_info,
                    **content
                }
                
                # 保存处理后的数据
                self.save_processed_json(post_id, full_post_data)
                
                all_posts.append(full_post_data)
                posts_scraped += 1
                
                logger.success(f"✓ Scraped post {post_id} ({posts_scraped}/{max_posts})")
                
                # 礼貌延迟
                time.sleep(2)
            
            # 页面间延迟
            if page < max_pages:
                time.sleep(3)
        
        logger.info(f"\n{'='*60}")
        logger.success(f"✓ Total posts scraped: {posts_scraped}")
        logger.info(f"{'='*60}")
        
        return all_posts
    
    def scrape_single_post(self, post_url):
        """
        爬取单个帖子（用于测试）
        
        Args:
            post_url: 帖子 URL
        """
        logger.info(f"Scraping single post: {post_url}")
        
        # 提取 post_id
        match = re.search(r'/posts/(\d+)', post_url)
        if not match:
            logger.error("Invalid post URL")
            return None
        
        post_id = match.group(1)
        
        # 获取详情页
        detail_html = self.fetch_post_detail(post_url)
        if not detail_html:
            return None
        
        # 保存原始 HTML
        self.save_raw_html(post_id, detail_html)
        
        # 解析内容
        content = self.parse_post_content(detail_html)
        
        # 构建完整数据
        post_data = {
            'post_id': post_id,
            'url': post_url,
            'scraped_at': datetime.now().isoformat(),
            **content
        }
        
        # 保存处理后的数据
        self.save_processed_json(post_id, post_data)
        
        logger.success(f"✓ Successfully scraped post {post_id}")
        logger.info(f"Title: {content['title']}")
        logger.info(f"Body length: {len(content['body'])} chars")
        logger.info(f"Comments: {len(content['comments'])}")
        
        return post_data


def main():
    """主函数"""
    logger.add("logs/community_scraper.log", rotation="10 MB")
    
    scraper = CommunityScrawler()
    
    # 1. 测试访问
    logger.info("Step 1: Testing access to WorldQuant Community")
    access_ok = scraper.test_access()
    
    if not access_ok:
        logger.warning("Cannot access the community page directly.")
        logger.info("\n" + "="*60)
        logger.info("The site requires login. Please choose:")
        logger.info("1. Try manual login with browser (will save cookies)")
        logger.info("2. Exit and check your network/credentials")
        logger.info("="*60)
        
        login_choice = input("Enter your choice (1 or 2): ").strip()
        
        if login_choice == "1":
            if scraper.manual_login_with_browser():
                logger.info("Login successful! Testing access again...")
                if not scraper.test_access():
                    logger.error("Still cannot access after login. Please check.")
                    return
            else:
                logger.error("Login failed.")
                return
        else:
            return
    
    logger.info("\n" + "="*60)
    logger.info("Choose an option:")
    logger.info("1. Scrape a single post (for testing)")
    logger.info("2. Scrape multiple posts from topic")
    logger.info("3. Manual login with browser (save cookies)")
    logger.info("="*60)
    
    choice = input("Enter your choice (1, 2, or 3): ").strip()
    
    if choice == "1":
        # 测试单个帖子
        test_url = "https://support.worldquantbrain.com/hc/en-us/community/posts/35951496406551--Alpha-Mining-%E5%9F%BA%E4%BA%8E-AI-Agent-%E7%9A%84%E5%85%A8%E8%87%AA%E5%8A%A8-Alpha-%E6%8C%96%E6%8E%98"
        logger.info(f"\nScraping test post: {test_url}")
        post_data = scraper.scrape_single_post(test_url)
        
        if post_data:
            logger.success("\n✓ Single post scraping successful!")
            print(f"\nPost Title: {post_data['title']}")
            print(f"Body Preview: {post_data['body'][:200]}...")
    
    elif choice == "2":
        # 爬取多个帖子
        max_posts = int(input("How many posts to scrape? (default 20): ").strip() or "20")
        max_pages = int(input("How many pages to scrape? (default 3): ").strip() or "3")
        
        logger.info(f"\nScraping up to {max_posts} posts from {max_pages} pages")
        posts = scraper.scrape_topic(max_pages=max_pages, max_posts=max_posts)
        
        logger.success(f"\n✓ Scraped {len(posts)} posts in total")
        
        # 保存汇总
        summary_file = DATA_DIR / "scraping_summary.json"
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump({
                'scraped_at': datetime.now().isoformat(),
                'total_posts': len(posts),
                'posts': posts
            }, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Summary saved to: {summary_file}")
    
    elif choice == "3":
        # 手动登录
        if scraper.manual_login_with_browser():
            logger.success("✓ Login successful! Cookies saved. You can now run the scraper again.")
        else:
            logger.error("✗ Login failed.")
    
    else:
        logger.error("Invalid choice")


if __name__ == "__main__":
    main()

