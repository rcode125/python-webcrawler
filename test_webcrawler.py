import unittest
from unittest.mock import patch, MagicMock
import json

from webcrawler import WebCrawler


class TestWebCrawlerIntegration(unittest.TestCase):
    def setUp(self):
        # Patch os.path.exists to avoid reading real files by default
        p_exists = patch('webcrawler.os.path.exists', return_value=False)
        self.addCleanup(p_exists.stop)
        p_exists.start()

        # Patch requests.get used in WebCrawler (both robots.txt and page fetches)
        self.requests_patcher = patch('webcrawler.requests.get')
        self.mock_get = self.requests_patcher.start()
        self.addCleanup(self.requests_patcher.stop)

        def requests_side_effect(url, headers=None, timeout=None):
            # robots.txt
            if url.rstrip('/').endswith('/robots.txt'):
                m = MagicMock()
                m.status_code = 200
                m.text = "User-agent: *\nDisallow:"
                return m
            # simple HTML for pages
            m = MagicMock()
            m.status_code = 200
            m.text = '<html><head><title>Test Page</title><meta name="description" content="desc"></head>' \
                     '<body><h1>H1</h1><p>para</p><a href="/link1">L</a></body></html>'
            return m

        self.mock_get.side_effect = requests_side_effect

        self.crawler = WebCrawler("https://example.com", max_pages=3, delay=0)

    def test_initialization(self):
        self.assertEqual(self.crawler.start_url, "https://example.com")
        self.assertEqual(self.crawler.domain, "example.com")
        self.assertEqual(self.crawler.max_pages, 3)

    def test_is_valid_url_same_domain(self):
        self.assertTrue(self.crawler.is_valid_url("https://example.com/page"))
        self.assertFalse(self.crawler.is_valid_url("https://other.com/page"))

    def test_extract_links_and_queue(self):
        html = '<html><body><a href="/page1">p1</a><a href="/page2">p2</a></body></html>'
        links = self.crawler.extract_links("https://example.com", html)
        # links should be absolute and deduped by to_visit_set
        self.assertIn("https://example.com/page1", links)
        self.assertIn("https://example.com/page2", links)

    def test_extract_content(self):
        html = '<html><head><title>Title</title></head><body><h1>Heading</h1><p>Paragraph</p></body></html>'
        content = self.crawler.extract_content("https://example.com", html)
        self.assertEqual(content['title'], 'Title')
        self.assertIn('Heading', content['headings'])

    def test_fetch_page_handles_error(self):
        # make requests.get raise for page fetch
        def raise_on_page(url, headers=None, timeout=None):
            if url.rstrip('/').endswith('/robots.txt'):
                m = MagicMock(); m.status_code = 200; m.text = "User-agent: *\nDisallow:"; return m
            raise RuntimeError("network error")

        self.mock_get.side_effect = raise_on_page
        page = self.crawler.fetch_page('https://example.com/some')
        self.assertIsNone(page)

    def test_crawl_respects_max_pages_and_saves_data(self):
        data = self.crawler.crawl()
        # max_pages=3 so visited should be <=3
        self.assertLessEqual(len(self.crawler.visited), 3)
        # data items should have url and title
        if data:
            for item in data:
                self.assertIn('url', item)
                self.assertIn('title', item)

    def test_start_url_already_in_existing_data_aborts(self):
        # simulate existing JSON with start_url present
        existing = [{'url': 'https://example.com', 'title': 'old'}]

        with patch('webcrawler.os.path.exists', return_value=True), \
             patch('webcrawler.open', create=True) as mock_open, \
             patch('webcrawler.json.load', return_value=existing):
            mock_open.return_value.__enter__.return_value = MagicMock()
            crawler2 = WebCrawler('https://example.com', max_pages=2)
            # if start_url already in visited, crawl should return immediately
            data = crawler2.crawl()
            # data should equal the loaded existing data
            self.assertEqual(crawler2.data, existing)


if __name__ == '__main__':
    unittest.main()
