import re
import math
import heapq
import time
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from collections import Counter


class WebCrawlerSearch:
    """
    简单的网络爬虫 + 智能搜索引擎：
    - 爬取网页（遵守同域名、限制深度和数量）
    - 提取页面文本，基于 TF-IDF + 余弦相似度检索
    """

    def __init__(self, start_url, max_pages=20, max_depth=2, delay=0.5,
                 use_jieba=False):
        self.start_url = start_url
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.delay = delay  # 请求间隔，避免对服务器造成压力
        self.domain = urlparse(start_url).netloc

        # 搜索相关
        self.documents = []  # 页面文本
        self.urls = []  # 对应 URL
        self.doc_vectors = []  # TF-IDF 向量
        self.idf = {}
        self.vocab = set()
        self.use_jieba = use_jieba

        if use_jieba:
            import jieba
            self.jieba = jieba
        else:
            self.jieba = None

    def _fetch(self, url):
        """下载页面 HTML"""
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (compatible; SearchCrawler/1.0)'}
            resp = requests.get(url, headers=headers, timeout=5)
            resp.raise_for_status()
            # 仅处理 HTML 页面
            if 'text/html' not in resp.headers.get('Content-Type', ''):
                return None
            return resp.text
        except Exception:
            return None

    def _extract_text_and_links(self, html, base_url):
        """从 HTML 中提取纯文本和同域名链接"""
        soup = BeautifulSoup(html, 'html.parser')
        # 移除 script 和 style 标签
        for tag in soup(['script', 'style']):
            tag.decompose()
        text = soup.get_text(separator=' ', strip=True)
        # 清理多余空白
        text = re.sub(r'\s+', ' ', text).strip()

        links = []
        for a in soup.find_all('a', href=True):
            href = a['href']
            full_url = urljoin(base_url, href)
            # 只保留同域名链接，且不是哈希或 javascript
            if urlparse(full_url).netloc == self.domain and \
                    not full_url.startswith('javascript:') and \
                    not '#' in full_url:
                links.append(full_url)
        return text, links

    def crawl(self):
        """启动爬虫，构建页面集合"""
        visited = set()
        # 队列元素：(url, depth)
        queue = [(self.start_url, 0)]

        while queue and len(self.documents) < self.max_pages:
            url, depth = queue.pop(0)
            if url in visited:
                continue
            print(f'爬取 ({len(self.documents) + 1}/{self.max_pages}): {url}')

            html = self._fetch(url)
            if not html:
                visited.add(url)
                continue

            text, links = self._extract_text_and_links(html, url)
            visited.add(url)

            if text:
                self.documents.append(text)
                self.urls.append(url)

            # 加入新链接（限制深度）
            if depth < self.max_depth:
                for link in links:
                    if link not in visited:
                        queue.append((link, depth + 1))

            time.sleep(self.delay)  # 礼貌爬取

        # 爬取完成，构建搜索索引
        self._build_index()
        print(f'索引构建完成，共 {len(self.documents)} 个页面。')

    def _tokenize(self, text):
        """分词：中文可用 jieba，否则简单处理"""
        if self.use_jieba and self.jieba:
            tokens = list(self.jieba.cut(text))
        else:
            # 提取英文单词和中文字符（简单按单字分词）
            tokens = re.findall(r'[a-zA-Z]+|[\u4e00-\u9fff]', text.lower())
        return [t for t in tokens if t.strip()]

    def _build_index(self):
        """构建 TF-IDF 索引"""
        N = len(self.documents)
        # 文档词频统计
        doc_token_counts = []
        for doc in self.documents:
            tokens = self._tokenize(doc)
            counter = Counter(tokens)
            doc_token_counts.append(counter)
            self.vocab.update(counter.keys())

        # 计算 IDF
        self.idf = {}
        for word in self.vocab:
            doc_with_word = sum(1 for counter in doc_token_counts if word in counter)
            self.idf[word] = math.log((N + 1) / (doc_with_word + 1)) + 1  # 平滑

        # 构造 TF-IDF 向量
        self.doc_vectors = []
        for counter in doc_token_counts:
            tfidf = {}
            total = sum(counter.values())
            for word, tf in counter.items():
                tfidf[word] = (tf / total) * self.idf[word]
            self.doc_vectors.append(tfidf)

    def _cosine_similarity(self, vec1, vec2):
        """计算两个稀疏向量的余弦相似度"""
        common = set(vec1.keys()) & set(vec2.keys())
        dot_product = sum(vec1[w] * vec2[w] for w in common)
        norm1 = math.sqrt(sum(v ** 2 for v in vec1.values()))
        norm2 = math.sqrt(sum(v ** 2 for v in vec2.values()))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def search(self, query, top_k=5):
        """
        查询接口：返回相关网页集合
        每个结果包含：url, score, snippet(前200字符)
        """
        if not self.doc_vectors:
            return []

        # 查询分词并计算 TF-IDF 向量
        query_tokens = self._tokenize(query)
        query_counter = Counter(query_tokens)
        query_vec = {}
        total = sum(query_counter.values())
        for word, tf in query_counter.items():
            if word in self.idf:
                query_vec[word] = (tf / total) * self.idf[word]

        if not query_vec:
            return []

        # 计算与所有文档的相似度
        scores = []
        for idx, doc_vec in enumerate(self.doc_vectors):
            sim = self._cosine_similarity(query_vec, doc_vec)
            if sim > 0:
                scores.append((-sim, idx))  # 用负值实现最大堆

        heapq.heapify(scores)
        results = []
        for _ in range(min(top_k, len(scores))):
            neg_sim, idx = heapq.heappop(scores)
            snippet = self.documents[idx][:200].replace('\n', ' ')
            results.append({
                'url': self.urls[idx],
                'score': round(-neg_sim, 4),
                'snippet': snippet
            })
        return results


# ---------- 使用示例 ----------
if __name__ == '__main__':
    # 初始化爬虫+搜索引擎（从某个教程站开始，限制 10 页，深度 1）
    engine = WebCrawlerSearch(
        start_url='https://mp.weixin.qq.com/s/I4enrArUavE_zZBJbyxzsg',
        max_pages=10,
        max_depth=1,
        delay=0.5
    )
    engine.crawl()  # 爬取并构建索引

    # 交互式查询
    while True:
        q = input('\n请输入搜索关键词 (q 退出): ').strip()
        if q.lower() == 'q':
            break
        results = engine.search(q, top_k=3)
        if not results:
            print('未找到相关页面。')
        for i, res in enumerate(results, 1):
            print(f"{i}. [{res['score']}] {res['url']}")
            print(f"   摘要: {res['snippet']}...\n")