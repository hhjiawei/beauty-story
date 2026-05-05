import asyncio
import math
import heapq
import random
import re
from dataclasses import dataclass
from typing import List, Dict, Optional, Set, Callable
from urllib.parse import urljoin, urlparse, urldefrag
from collections import Counter

import aiohttp
from aiohttp import ClientTimeout, TCPConnector
from bs4 import BeautifulSoup
from langchain_core.tools import tool
from pydantic import BaseModel, Field

# ==================== 预定义 User-Agent 列表 ====================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36 OPR/109.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (iPad; CPU OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14; SM-S918B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Vivaldi/6.7.3329.35",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Brave/1.65.133",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 AVG/124.0.0.0",
]


def get_random_headers() -> Dict[str, str]:
    """获取随机请求头"""
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Cache-Control": "max-age=0",
    }


# ==================== 重试装饰器 ====================

def async_retry(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0):
    """指数退避重试装饰器"""

    def decorator(func: Callable):
        async def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except (aiohttp.ClientError, asyncio.TimeoutError, ConnectionError) as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        jitter = random.uniform(0, delay * 0.3)
                        await asyncio.sleep(delay + jitter)
            raise last_exception

        return wrapper

    return decorator


# ==================== 配置模型 ====================

class WebSearchInput(BaseModel):
    """网络爬虫搜索工具的输入参数 Schema"""
    start_url: str = Field(description="起始爬取的 URL 地址")
    query: str = Field(description="搜索查询关键词")
    max_pages: int = Field(default=10, ge=1, le=100, description="最大爬取页面数")
    max_depth: int = Field(default=2, ge=1, le=5, description="最大爬取深度")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量")
    delay: float = Field(default=0.5, ge=0.0, description="请求间隔秒数，避免对目标站造成压力")
    use_jieba: bool = Field(default=False, description="是否使用 jieba 进行中文分词")
    max_concurrent: int = Field(default=5, ge=1, le=20, description="最大并发请求数")
    max_retries: int = Field(default=3, ge=1, le=10, description="请求失败最大重试次数")
    retry_base_delay: float = Field(default=1.0, ge=0.1, description="重试基础延迟秒数")
    proxy: Optional[str] = Field(default=None, description="代理地址，如 http://127.0.0.1:7890")
    timeout: float = Field(default=10.0, ge=1.0, le=120.0, description="单次请求超时秒数")


@dataclass
class FetchResult:
    """请求结果封装"""
    success: bool
    html: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    status_code: Optional[int] = None


# ==================== 爬虫引擎 ====================

def _normalize_url(url: str) -> str:
    """规范化 URL：去除 fragment、统一尾部斜杠"""
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


class AsyncWebCrawlerSearch:
    """异步网络爬虫 + TF-IDF 搜索引擎（增强版）"""

    def __init__(
            self,
            start_url: str,
            max_pages: int = 20,
            max_depth: int = 2,
            delay: float = 0.5,
            use_jieba: bool = False,
            max_concurrent: int = 5,
            max_retries: int = 3,
            retry_base_delay: float = 1.0,
            proxy: Optional[str] = None,
            timeout: float = 10.0,
            custom_session: Optional[aiohttp.ClientSession] = None,
    ):
        self.start_url = _normalize_url(start_url)
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.delay = delay
        self.domain = urlparse(self.start_url).netloc
        self.max_concurrent = max_concurrent
        self.max_retries = max_retries
        self.retry_base_delay = retry_base_delay
        self.proxy = proxy
        self.timeout = timeout

        # 索引数据
        self.documents: List[str] = []
        self.urls: List[str] = []
        self.doc_vectors: List[Dict[str, float]] = []
        self.idf: Dict[str, float] = {}
        self.vocab: Set[str] = set()

        # 分词器
        self._jieba = None
        if use_jieba:
            import jieba
            self._jieba = jieba

        # 异步控制
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._session: Optional[aiohttp.ClientSession] = None
        self._custom_session = custom_session  # 外部传入的 session，不自动关闭
        self._owns_session = False

    async def __aenter__(self):
        if self._custom_session:
            self._session = self._custom_session
        else:
            connector = TCPConnector(
                limit=self.max_concurrent * 3,
                limit_per_host=self.max_concurrent,
                ttl_dns_cache=300,
                use_dns_cache=True,
                enable_cleanup_closed=True,
                force_close=True,
            )
            timeout = ClientTimeout(total=self.timeout, connect=min(5, self.timeout / 2))
            self._session = aiohttp.ClientSession(
                connector=connector,
                timeout=timeout,
                headers=get_random_headers(),
                trust_env=True,  # 读取系统代理环境变量
            )
            self._owns_session = True
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._owns_session and self._session:
            await self._session.close()

    @async_retry(max_retries=3, base_delay=1.0)
    async def _fetch(self, url: str) -> FetchResult:
        """异步下载页面 HTML（带重试和 UA 轮换）"""
        async with self._semaphore:
            try:
                # 每次请求随机更换 UA
                headers = get_random_headers()

                async with self._session.get(
                        url,
                        headers=headers,
                        allow_redirects=True,
                        proxy=self.proxy,
                        ssl=False,  # 某些站点证书问题，生产环境可改为 ssl=aiohttp.TCP_SSL()
                ) as resp:
                    if resp.status in (403, 429, 503):
                        # 可能被反爬，记录但继续
                        return FetchResult(
                            success=False,
                            url=url,
                            status_code=resp.status,
                            error=f"服务器返回 {resp.status}，可能被反爬"
                        )

                    if resp.status != 200:
                        return FetchResult(
                            success=False,
                            url=url,
                            status_code=resp.status,
                            error=f"HTTP {resp.status}"
                        )

                    content_type = resp.headers.get("Content-Type", "")
                    if "text/html" not in content_type and "application/xhtml" not in content_type:
                        return FetchResult(
                            success=False,
                            url=url,
                            status_code=resp.status,
                            error=f"非 HTML 内容: {content_type}"
                        )

                    html = await resp.text()
                    return FetchResult(success=True, html=html, url=str(resp.url))

            except asyncio.TimeoutError:
                return FetchResult(success=False, url=url, error="请求超时")
            except aiohttp.ClientConnectorError as e:
                return FetchResult(success=False, url=url, error=f"连接错误: {str(e)}")
            except aiohttp.ClientError as e:
                return FetchResult(success=False, url=url, error=f"客户端错误: {str(e)}")
            except Exception as e:
                return FetchResult(success=False, url=url, error=f"未知错误: {str(e)}")
            finally:
                if self.delay > 0:
                    await asyncio.sleep(self.delay + random.uniform(0, self.delay * 0.5))

    def _extract_text_and_links(self, html: str, base_url: str) -> tuple:
        """提取正文与同域名链接"""
        soup = BeautifulSoup(html, "html.parser")

        # 移除噪音标签
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe", "svg"]):
            tag.decompose()

        # 优先提取常见内容容器：微信文章、main、article、body
        main_content = (
            soup.find("div", id="js_content") or  # 微信文章正文
            soup.find("div", class_="rich_media_content") or  # 微信文章备用
            soup.find("main") or
            soup.find("article") or
            soup.find("div", role="main") or
            soup.find("body")
        )
        text = main_content.get_text(separator=" ", strip=True) if main_content else ""
        text = re.sub(r"\s+", " ", text).strip()

        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
                continue

            full_url = _normalize_url(urljoin(base_url, href))
            parsed = urlparse(full_url)

            if parsed.netloc == self.domain and parsed.scheme in ("http", "https"):
                links.append(full_url)

        return text, links

    async def crawl(self) -> None:
        """启动异步 BFS 爬虫"""
        visited: Set[str] = set()
        queue: asyncio.Queue = asyncio.Queue()
        failed_urls: List[str] = []

        await queue.put((self.start_url, 0))
        visited.add(self.start_url)

        while len(self.documents) < self.max_pages and not queue.empty():
            url, depth = await queue.get()

            result = await self._fetch(url)
            if not result.success:
                failed_urls.append(f"{url}: {result.error}")
                continue

            text, links = self._extract_text_and_links(result.html, result.url or url)

            # 过滤无意义短内容（微信文章通常很长，但保留 30 字符下限以防空页面）
            if text and len(text) > 30:
                self.documents.append(text)
                self.urls.append(result.url or url)

            if depth < self.max_depth:
                for link in links:
                    if link not in visited and len(visited) < self.max_pages * 5:
                        visited.add(link)
                        await queue.put((link, depth + 1))

        self._build_index()
        self.failed_urls = failed_urls

    def _tokenize(self, text: str) -> List[str]:
        """分词：jieba 分词或按单字/单词提取"""
        if self._jieba:
            tokens = list(self._jieba.cut(text))
            # jieba 分词结果保留长度 >= 1 的（中文词组通常 >= 2，但单字也可能是有效词）
            return [t.strip() for t in tokens if t.strip()]
        else:
            # 英文取单词，中文取单字
            tokens = re.findall(r"[a-zA-Z]+|[\u4e00-\u9fff]", text.lower())
            # 英文过滤单字符（如 "a", "I"），但中文字符（长度1）必须保留！
            return [t for t in tokens if t.strip() and (len(t) > 1 or not t.isascii())]

    def _build_index(self) -> None:
        """构建 TF-IDF 索引"""
        N = len(self.documents)
        if N == 0:
            return

        doc_token_counts = []
        for doc in self.documents:
            tokens = self._tokenize(doc)
            counter = Counter(tokens)
            doc_token_counts.append(counter)
            self.vocab.update(counter.keys())

        # IDF
        for word in self.vocab:
            doc_with_word = sum(1 for c in doc_token_counts if word in c)
            self.idf[word] = math.log((N + 1) / (doc_with_word + 1)) + 1

        # TF-IDF 向量
        self.doc_vectors = []
        for counter in doc_token_counts:
            tfidf = {}
            total = sum(counter.values())
            if total == 0:
                self.doc_vectors.append(tfidf)
                continue
            for word, tf in counter.items():
                tfidf[word] = (tf / total) * self.idf[word]
            self.doc_vectors.append(tfidf)

    @staticmethod
    def _cosine_similarity(vec1: Dict[str, float], vec2: Dict[str, float]) -> float:
        """稀疏向量余弦相似度"""
        common = set(vec1.keys()) & set(vec2.keys())
        if not common:
            return 0.0

        dot = sum(vec1[w] * vec2[w] for w in common)
        norm1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
        norm2 = math.sqrt(sum(v ** 2 for v in vec2.values()))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def search(self, query: str, top_k: int = 5) -> List[Dict]:
        """基于 TF-IDF 的检索"""
        if not self.doc_vectors:
            return []

        query_tokens = self._tokenize(query)
        query_counter = Counter(query_tokens)
        total = sum(query_counter.values())
        if total == 0:
            return []

        query_vec = {}
        for word, tf in query_counter.items():
            if word in self.idf:
                query_vec[word] = (tf / total) * self.idf[word]

        if not query_vec:
            return []

        scores = []
        for idx, doc_vec in enumerate(self.doc_vectors):
            sim = self._cosine_similarity(query_vec, doc_vec)
            if sim > 0:
                scores.append((-sim, idx))

        if not scores:
            return []

        heapq.heapify(scores)
        results = []
        for _ in range(min(top_k, len(scores))):
            neg_sim, idx = heapq.heappop(scores)
            snippet = self.documents[idx][:200].replace("\n", " ")
            results.append({
                "url": self.urls[idx],
                "score": round(-neg_sim, 4),
                "snippet": snippet,
            })
        return results


# ==================== LangChain Tool ====================

@tool(args_schema=WebSearchInput)
async def web_crawler_search(
        start_url: str,
        query: str,
        max_pages: int = 10,
        max_depth: int = 2,
        top_k: int = 5,
        delay: float = 0.5,
        use_jieba: bool = False,
        max_concurrent: int = 5,
        max_retries: int = 3,
        retry_base_delay: float = 1.0,
        proxy: Optional[str] = None,
        timeout: float = 10.0,
) -> str:
    """
    网络爬虫搜索引擎工具。

    从指定的 start_url 开始，异步爬取同域名下的网页，构建 TF-IDF 索引，
    并根据 query 返回最相关的页面结果。

    特性：
    - 多 User-Agent 轮换，降低被屏蔽风险
    - 指数退避重试机制
    - 支持代理配置
    - 精细化异常处理
    - 适配微信文章等特定页面结构

    适用场景：
    - 需要搜索某个特定网站内的信息
    - 该网站没有提供搜索 API
    - 需要基于页面内容进行语义检索

    返回格式化的搜索结果字符串。
    """
    try:
        async with AsyncWebCrawlerSearch(
                start_url=start_url,
                max_pages=max_pages,
                max_depth=max_depth,
                delay=delay,
                use_jieba=use_jieba,
                max_concurrent=max_concurrent,
                max_retries=max_retries,
                retry_base_delay=retry_base_delay,
                proxy=proxy,
                timeout=timeout,
        ) as engine:
            await engine.crawl()
            results = engine.search(query, top_k=top_k)

        domain = urlparse(start_url).netloc

        lines = [f"🔍 查询: '{query}' | 域名: {domain}\n"]

        # 显示爬取统计
        lines.append(
            f"📊 爬取统计: {len(engine.documents)} 个页面 | 失败: {len(getattr(engine, 'failed_urls', []))} 个\n")

        if not results:
            lines.append(f"⚠️ 未找到与 '{query}' 相关的页面。")
            return "\n".join(lines)

        for i, res in enumerate(results, 1):
            lines.append(
                f"{i}. [相似度: {res['score']}] {res['url']}\n"
                f"   📄 摘要: {res['snippet']}...\n"
            )
        return "\n".join(lines)

    except Exception as e:
        return f"❌ 搜索过程中发生错误: {type(e).__name__}: {str(e)}"


# ==================== 高级使用：自定义 Session ====================

async def demo_with_custom_session():
    """演示使用自定义 aiohttp ClientSession"""
    # 创建自定义 session（例如带 Cookie、特定 SSL 配置等）
    connector = TCPConnector(limit=10, ssl=False)
    timeout = ClientTimeout(total=15)

    async with aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={"Authorization": "Bearer your-token"}  # 如果需要认证
    ) as custom_session:
        engine = AsyncWebCrawlerSearch(
            start_url="https://example.com",
            max_pages=5,
            custom_session=custom_session,  # 传入自定义 session
        )

        async with engine:
            await engine.crawl()
            results = engine.search("test", top_k=3)
            print(results)


# ==================== 基础使用示例 ====================

if __name__ == "__main__":
    async def demo():
        result = await web_crawler_search.ainvoke({
            "start_url": "https://mp.weixin.qq.com/s/I4enrArUavE_zZBJbyxzsg",
            "query": "2024年",
            "max_pages": 5,
            "max_depth": 2,
            "top_k": 3,
            "delay": 0.3,
            "max_retries": 3,
            "proxy": None,  # 如需代理: "http://127.0.0.1:7890"
        })
        print(result)


    asyncio.run(demo())