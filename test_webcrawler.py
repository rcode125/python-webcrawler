import unittest
from unittest.mock import patch, MagicMock
from webcrawler import WebCrawler


class TestWebCrawler(unittest.TestCase):
    
    def setUp(self):
        self.crawler = WebCrawler("https://example.com", max_pages=5)
    
    def test_initialization(self):
        self.assertEqual(self.crawler.start_url, "https://example.com")
        self.assertEqual(self.crawler.domain, "example.com")
        self.assertEqual(self.crawler.max_pages, 5)
    
    def test_is_valid_url(self):
        valid_url = "https://example.com/page"
        invalid_url = "https://other.com/page"
        
        self.assertTrue(self.crawler.is_valid_url(valid_url))
        self.assertFalse(self.crawler.is_valid_url(invalid_url))
    
    def test_extract_links(self):
        html = '<html><body><a href="/page1">Link</a><a href="/page2">Link</a></body></html>'
        links = self.crawler.extract_links("https://example.com", html)
        
        self.assertEqual(len(links), 2)
    
    def test_extract_content(self):
        html = '<html><head><title>Test</title></head><body><h1>Heading</h1><p>Paragraph</p></body></html>'
        content = self.crawler.extract_content("https://example.com", html)
        
        self.assertEqual(content['title'], 'Test')
        self.assertIn('Heading', content['headings'])


if __name__ == '__main__':
    unittest.main()