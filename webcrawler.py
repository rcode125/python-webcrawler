import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from datetime import datetime
import json
import time
from collections import deque
import logging

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class WebCrawler:
    """Ein vollständiger Web Crawler mit Duplikat-Erkennung und Rate Limiting"""
    
    def __init__(self, start_url, max_pages=50, delay=1):
        """
        Initialisiert den Crawler
        
        Args:
            start_url: Die Startadresse zum Crawlen
            max_pages: Maximale Anzahl von Seiten zu crawlen
            delay: Verzögerung zwischen Anfragen in Sekunden
        """
        self.start_url = start_url
        self.max_pages = max_pages
        self.delay = delay
        self.visited = set()
        self.to_visit = deque([start_url])
        self.data = []
        
        # User-Agent setzen
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        
        # Domain extrahieren
        self.domain = urlparse(start_url).netloc
        
    def is_valid_url(self, url):
        """Prüft ob eine URL gültig und in der gleichen Domain ist"""
        try:
            parsed = urlparse(url)
            return (parsed.netloc == self.domain and 
                    parsed.scheme in ['http', 'https'] and
                    url not in self.visited)
        except:
            return False
    
    def extract_links(self, url, html):
        """Extrahiert alle Links aus HTML"""
        links = []
        try:
            soup = BeautifulSoup(html, 'html.parser')
            for link in soup.find_all('a', href=True):
                absolute_url = urljoin(url, link['href'])
                if self.is_valid_url(absolute_url):
                    links.append(absolute_url)
        except Exception as e:
            logger.error(f"Fehler beim Extrahieren von Links: {e}")
        return links
    
    def extract_content(self, url, html):
        """Extrahiert relevante Inhalte aus HTML"""
        try:
            soup = BeautifulSoup(html, 'html.parser')
            
            # Titel
            title = soup.title.string if soup.title else "Kein Titel"
            
            # Beschreibung
            description = ""
            meta_desc = soup.find('meta', attrs={'name': 'description'})
            if meta_desc:
                description = meta_desc.get('content', '')
            
            # Überschriften
            headings = [h.get_text().strip() for h in soup.find_all(['h1', 'h2', 'h3'])]
            
            # Paragraphen (erste 3)
            paragraphs = [p.get_text().strip() for p in soup.find_all('p')[:3]]
            
            # Links (Anzahl)
            link_count = len(soup.find_all('a'))
            
            return {
                'url': url,
                'title': title,
                'description': description,
                'headings': headings[:5],
                'paragraphs': paragraphs,
                'link_count': link_count,
                'crawled_at': datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Fehler beim Extrahieren von Inhalten: {e}")
            return None
    
    def fetch_page(self, url):
        """Lädt eine Seite herunter"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            logger.error(f"Fehler beim Abrufen von {url}: {e}")
            return None
    
    def crawl(self):
        """Startet den Crawl-Prozess"""
        logger.info(f"Starte Crawler mit: {self.start_url}")
        
        while self.to_visit and len(self.visited) < self.max_pages:
            url = self.to_visit.popleft()
            
            if url in self.visited:
                continue
            
            self.visited.add(url)
            logger.info(f"Crawle ({len(self.visited)}/{self.max_pages}): {url}")
            
            # Seite abrufen
            html = self.fetch_page(url)
            if not html:
                continue
            
            # Inhalte extrahieren
            content = self.extract_content(url, html)
            if content:
                self.data.append(content)
            
            # Links extrahieren
            links = self.extract_links(url, html)
            self.to_visit.extend(links)
            
            # Rate Limiting
            time.sleep(self.delay)
        
        logger.info(f"Crawl abgeschlossen! {len(self.visited)} Seiten gecrawlt.")
        return self.data
    
    def save_to_json(self, filename='crawled_data.json'):
        """Speichert die gecrawlten Daten als JSON"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            logger.info(f"Daten gespeichert in: {filename}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern: {e}")
    
    def get_summary(self):
        """Gibt eine Zusammenfassung aus"""
        return {
            'total_pages': len(self.visited),
            'total_items': len(self.data),
            'domain': self.domain,
            'start_url': self.start_url
        }


# Beispielverwendung
if __name__ == "__main__":
    # Crawler initialisieren
    crawler = WebCrawler(
        start_url="https://example.com",
        max_pages=20,
        delay=1
    )
    
    # Crawlen starten
    data = crawler.crawl()
    
    # Ergebnisse speichern
    crawler.save_to_json()
    
    # Zusammenfassung anzeigen
    print("\n=== Crawl-Zusammenfassung ===")
    summary = crawler.get_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")
