import asyncio
import math
import heapq
import random
import re
from dataclasses import dataclass
from typing import List, Dict, Optional, Set, Callable, Tuple
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
    query: Optional[str] = Field(default="", description="搜索查询关键词。为空时返回全部内容")
    max_pages: int = Field(default=10, ge=1, le=100, description="最大爬取页面数")
    max_depth: int = Field(default=2, ge=1, le=5, description="最大爬取深度")
    top_k: int = Field(default=5, ge=1, le=20, description="返回结果数量（query为空时无效，返回全部）")
    delay: float = Field(default=0.5, ge=0.0, description="请求间隔秒数，避免对目标站造成压力")
    use_jieba: bool = Field(default=False, description="是否使用 jieba 进行中文分词")
    max_concurrent: int = Field(default=5, ge=1, le=20, description="最大并发请求数")
    max_retries: int = Field(default=3, ge=1, le=10, description="请求失败最大重试次数")
    retry_base_delay: float = Field(default=1.0, ge=0.1, description="重试基础延迟秒数")
    proxy: Optional[str] = Field(default=None, description="代理地址，如 http://127.0.0.1:7890")
    timeout: float = Field(default=10.0, ge=1.0, le=120.0, description="单次请求超时秒数")
    snippet_mode: str = Field(default="paragraph", description="片段拆分模式: paragraph(段落) / sentence(句子)")
    min_snippet_length: int = Field(default=20, ge=5, description="片段最小长度，低于此值的片段会被过滤")


@dataclass
class FetchResult:
    """请求结果封装"""
    success: bool
    html: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    status_code: Optional[int] = None


# ==================== 文本拆分工具 ====================

class TextSplitter:
    """将长文本拆分为段落或句子片段"""

    @staticmethod
    def split_paragraphs(text: str, min_length: int = 20) -> List[str]:
        """按段落拆分（双换行或连续空白）"""
        raw_paragraphs = re.split(r'\n\s*\n|\r\n\s*\r\n', text.strip())
        paragraphs = []
        for p in raw_paragraphs:
            p = p.strip().replace('\n', ' ')
            p = re.sub(r'\s+', ' ', p)
            if len(p) >= min_length:
                paragraphs.append(p)
        return paragraphs

    @staticmethod
    def split_sentences(text: str, min_length: int = 20) -> List[str]:
        """按句子拆分（支持中英文句号、问号、感叹号）"""
        parts = re.split(r'([。！？.?!])', text.strip())
        sentences = []
        current = ""
        for part in parts:
            current += part
            if re.match(r'[。！？.?!]$', part):
                current = current.strip()
                current = re.sub(r'\s+', ' ', current)
                if len(current) >= min_length:
                    sentences.append(current)
                current = ""
        if current.strip() and len(current.strip()) >= min_length:
            sentences.append(current.strip())
        return sentences

    @classmethod
    def split(cls, text: str, mode: str = "paragraph", min_length: int = 20) -> List[str]:
        if mode == "sentence":
            return cls.split_sentences(text, min_length)
        return cls.split_paragraphs(text, min_length)


# ==================== 爬虫引擎 ====================

def _normalize_url(url: str) -> str:
    """规范化 URL：去除 fragment、统一尾部斜杠"""
    url, _ = urldefrag(url)
    parsed = urlparse(url)
    path = parsed.path.rstrip("/") or "/"
    return f"{parsed.scheme}://{parsed.netloc}{path}"


class AsyncWebCrawlerSearch:
    """异步网络爬虫 + 段落级 TF-IDF 搜索引擎"""

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
            snippet_mode: str = "paragraph",
            min_snippet_length: int = 20,
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
        self.snippet_mode = snippet_mode
        self.min_snippet_length = min_snippet_length

        # ===== 索引数据（以片段为单位） =====
        self.snippets: List[str] = []
        self.snippet_urls: List[str] = []
        self.snippet_indices: List[int] = []
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
        self._custom_session = custom_session
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
                trust_env=True,
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
                headers = get_random_headers()
                async with self._session.get(
                        url,
                        headers=headers,
                        allow_redirects=True,
                        proxy=self.proxy,
                        ssl=False,
                ) as resp:
                    if resp.status in (403, 429, 503):
                        return FetchResult(
                            success=False, url=url, status_code=resp.status,
                            error=f"服务器返回 {resp.status}，可能被反爬"
                        )
                    if resp.status != 200:
                        return FetchResult(
                            success=False, url=url, status_code=resp.status,
                            error=f"HTTP {resp.status}"
                        )
                    content_type = resp.headers.get("Content-Type", "")
                    if "text/html" not in content_type and "application/xhtml" not in content_type:
                        return FetchResult(
                            success=False, url=url, status_code=resp.status,
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

    def _extract_text_and_links(self, html: str, base_url: str) -> Tuple[List[str], List[str]]:
        """提取正文段落与同域名链接"""
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "noscript", "iframe", "svg"]):
            tag.decompose()

        main_content = (
            soup.find("div", id="js_content") or
            soup.find("div", class_="rich_media_content") or
            soup.find("main") or
            soup.find("article") or
            soup.find("div", role="main") or
            soup.find("body")
        )
        text = main_content.get_text(separator="\n", strip=True) if main_content else ""
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n\s*\n+", "\n\n", text)

        snippets = TextSplitter.split(text, mode=self.snippet_mode, min_length=self.min_snippet_length)

        links = []
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
                continue
            full_url = _normalize_url(urljoin(base_url, href))
            parsed = urlparse(full_url)
            if parsed.netloc == self.domain and parsed.scheme in ("http", "https"):
                links.append(full_url)

        return snippets, links

    async def crawl(self) -> None:
        """启动异步 BFS 爬虫，按片段存储"""
        visited: Set[str] = set()
        queue: asyncio.Queue = asyncio.Queue()
        failed_urls: List[str] = []

        await queue.put((self.start_url, 0))
        visited.add(self.start_url)

        while len(visited) < self.max_pages * 5 and not queue.empty():
            url, depth = await queue.get()

            result = await self._fetch(url)
            if not result.success:
                failed_urls.append(f"{url}: {result.error}")
                continue

            snippets, links = self._extract_text_and_links(result.html, result.url or url)

            for idx, snippet in enumerate(snippets):
                self.snippets.append(snippet)
                self.snippet_urls.append(result.url or url)
                self.snippet_indices.append(idx)

            if depth < self.max_depth:
                for link in links:
                    if link not in visited and len(visited) < self.max_pages * 5:
                        visited.add(link)
                        await queue.put((link, depth + 1))

        self._build_index()
        self.failed_urls = failed_urls

    def _tokenize(self, text: str) -> List[str]:
        """分词"""
        if self._jieba:
            tokens = list(self._jieba.cut(text))
            return [t.strip() for t in tokens if t.strip()]
        else:
            tokens = re.findall(r"[a-zA-Z]+|[\u4e00-\u9fff]", text.lower())
            return [t for t in tokens if t.strip() and (len(t) > 1 or not t.isascii())]

    def _build_index(self) -> None:
        """以片段为单位构建 TF-IDF 索引"""
        N = len(self.snippets)
        if N == 0:
            return

        snippet_token_counts = []
        for snippet in self.snippets:
            tokens = self._tokenize(snippet)
            counter = Counter(tokens)
            snippet_token_counts.append(counter)
            self.vocab.update(counter.keys())

        for word in self.vocab:
            doc_with_word = sum(1 for c in snippet_token_counts if word in c)
            self.idf[word] = math.log((N + 1) / (doc_with_word + 1)) + 1

        self.doc_vectors = []
        for counter in snippet_token_counts:
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
        """
        基于 TF-IDF 的片段级检索。
        query 为空时返回全部片段（按页面分组）。
        """
        # ===== query 为空：返回全部内容 =====
        if not query or not query.strip():
            return self._get_all_snippets()

        # ===== 正常 TF-IDF 检索 =====
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
        seen_urls = set()

        while len(results) < min(top_k, len(scores)):
            neg_sim, idx = heapq.heappop(scores)
            url = self.snippet_urls[idx]
            url_count = sum(1 for r in results if r["url"] == url)
            if url_count >= 2:
                continue

            snippet = self.snippets[idx]
            context_start = max(0, idx - 1)
            context_end = min(len(self.snippets), idx + 2)
            context_parts = []
            for cidx in range(context_start, context_end):
                if self.snippet_urls[cidx] == url:
                    prefix = ">> " if cidx == idx else "   "
                    context_parts.append(f"{prefix}{self.snippets[cidx][:150]}")

            results.append({
                "url": url,
                "score": round(-neg_sim, 4),
                "snippet": snippet[:300],
                "context": "\n".join(context_parts),
                "index": self.snippet_indices[idx],
            })

        return results

    def _get_all_snippets(self) -> List[Dict]:
        """query 为空时，按页面分组返回全部片段"""
        # 按 URL 分组
        url_to_snippets: Dict[str, List[Tuple[int, str]]] = {}
        for idx, (snippet, url) in enumerate(zip(self.snippets, self.snippet_urls)):
            if url not in url_to_snippets:
                url_to_snippets[url] = []
            url_to_snippets[url].append((idx, snippet))

        results = []
        for url, items in url_to_snippets.items():
            # 合并同一页面的片段为一段完整文本
            items.sort(key=lambda x: x[0])
            full_text = "\n\n".join(s for _, s in items)
            results.append({
                "url": url,
                "score": 1.0,  # 无搜索分数，标记为全部内容
                "snippet": full_text[:500],  # 截断显示
                "context": full_text[:2000],  # 更多上下文
                "index": 0,
                "is_full_content": True,
            })

        return results


# ==================== LangChain Tool ====================

@tool(args_schema=WebSearchInput)
async def web_crawler_search(
        start_url: str,
        query: Optional[str] = "",
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
        snippet_mode: str = "paragraph",
        min_snippet_length: int = 20,
) -> str:
    """
    网络爬虫搜索引擎工具（段落级检索）。

    从指定的 start_url 开始，异步爬取同域名下的网页，
    将页面拆分为段落/句子片段，构建 TF-IDF 索引。

    query 为空时返回全部页面内容，否则按相似度检索最相关的片段。

    特性：
    - query 为空返回全部内容，有 query 时按 TF-IDF 检索
    - 支持段落级(paragraph)或句子级(sentence)检索
    - 多 User-Agent 轮换，降低被屏蔽风险
    - 指数退避重试机制
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
                snippet_mode=snippet_mode,
                min_snippet_length=min_snippet_length,
        ) as engine:
            await engine.crawl()
            results = engine.search(query, top_k=top_k)

        domain = urlparse(start_url).netloc
        is_full_mode = not query or not query.strip()

        if is_full_mode:
            lines = [f"📄 全文模式 | 域名: {domain} | 共 {len(results)} 个页面\n"]
        else:
            lines = [f"🔍 查询: '{query}' | 域名: {domain} | 模式: {snippet_mode}\n"]
            lines.append(f"📊 索引片段数: {len(engine.snippets)} | 失败页面: {len(getattr(engine, 'failed_urls', []))}\n")

        if not results:
            if is_full_mode:
                lines.append("⚠️ 未获取到任何页面内容。")
            else:
                lines.append(f"⚠️ 未找到与 '{query}' 相关的片段。")
            return "\n".join(lines)

        for i, res in enumerate(results, 1):
            if is_full_mode:
                lines.append(
                    f"{'='*60}\n"
                    f"{i}. 📄 {res['url']}\n"
                    f"{'='*60}\n"
                    f"{res['context'][:1500]}\n"
                    f"{'='*60}\n"
                )
            else:
                lines.append(
                    f"{i}. [相似度: {res['score']}] {res['url']}\n"
                    f"   📄 片段:\n{res['context']}\n"
                )

        return "\n".join(lines)

    except Exception as e:
        return f"❌ 搜索过程中发生错误: {type(e).__name__}: {str(e)}"


# ==================== 使用示例 ====================

if __name__ == "__main__":
    async def demo():
        # 1. query 为空：返回全部内容
        print("=" * 60)
        print("【全文模式】query 为空")
        print("=" * 60)
        result_full = await web_crawler_search.ainvoke({
            "start_url": "https://mp.weixin.qq.com/s/I4enrArUavE_zZBJbyxzsg",
            "query": "",  # 空 query
            "max_pages": 3,
            "max_depth": 1,
            "snippet_mode": "paragraph",
        })
        print(result_full[:2000])  # 只打印前 2000 字

    asyncio.run(demo())