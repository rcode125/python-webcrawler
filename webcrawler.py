import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser
from datetime import datetime
import json
import time
from collections import deque
import os
import logging
import argparse

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class WebCrawler:
    def __init__(self, start_url, max_pages=50, delay=1, json_file="crawled_data.json"):
        self.start_url = start_url
        self.max_pages = max_pages
        self.delay = delay
        self.visited = set()
        self.to_visit = deque([start_url])
        self.data = []
        self.json_file = json_file
        
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        }

        self.domain = urlparse(start_url).netloc

        # robots.txt einlesen (sicher mit timeout, damit es nicht hängt)
        self.robot_parser = None
        robots_url = urljoin(f"https://{self.domain}", "/robots.txt")
        try:
            resp = requests.get(robots_url, headers=self.headers, timeout=5)
            if resp.status_code == 200:
                from urllib.robotparser import RobotFileParser

                self.robot_parser = RobotFileParser()
                # parse erwartet eine Liste von Zeilen
                self.robot_parser.parse(resp.text.splitlines())
                logger.info(f"robots.txt geladen von {robots_url}")
            else:
                logger.info(f"robots.txt nicht gefunden (Status {resp.status_code}), erlauben standardmäßig alles")
                self.robot_parser = None
        except Exception as e:
            logger.warning(f"robots.txt konnte nicht geladen werden: {e}. Erlaube standardmäßig alles.")
            self.robot_parser = None

        # Existierende URLs aus JSON laden zur Duplikatvermeidung
        self.load_existing_data()

        # Set zur Verhinderung mehrfacher Einträge in der Queue
        self.to_visit_set = set(self.to_visit)

    def load_existing_data(self):
        if os.path.exists(self.json_file):
            try:
                with open(self.json_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    self.data = existing
                    for item in existing:
                        self.visited.add(item.get("url"))
                logger.info(f"{len(self.visited)} URLs aus {self.json_file} geladen zum Vermeiden von Duplikaten")
            except Exception as e:
                logger.error(f"Fehler beim Laden vorhandener Daten: {e}")

    def can_fetch(self, url):
        # wenn kein Robotparser verfügbar ist, erlauben wir das Crawlen
        try:
            if not self.robot_parser:
                return True
            return self.robot_parser.can_fetch(self.headers["User-Agent"], url)
        except Exception:
            return True

    def is_valid_url(self, url):
        try:
            parsed = urlparse(url)
            clean_url = parsed._replace(fragment="").geturl()
            return (
                parsed.scheme in ("http", "https")
                and parsed.netloc == self.domain
                and clean_url not in self.visited
                and self.can_fetch(clean_url)
            )
        except Exception:
            return False

    def extract_links(self, url, html):
        links = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.find_all("a", href=True):
                absolute_url = urljoin(url, link["href"])
                # nur hinzufügen, wenn gültig und noch nicht in Queue/visited
                if self.is_valid_url(absolute_url) and absolute_url not in self.to_visit_set:
                    links.append(absolute_url)
                    self.to_visit_set.add(absolute_url)
        except Exception as e:
            logger.error(f"Fehler beim Extrahieren von Links: {e}")
        return links

    def extract_content(self, url, html):
        try:
            soup = BeautifulSoup(html, "html.parser")
            title_tag = soup.title
            title = title_tag.string.strip() if title_tag and title_tag.string else "Kein Titel"
            description = ""
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                description = meta_desc.get("content", "").strip()
            headings = [h.get_text(strip=True) for h in soup.find_all(["h1", "h2", "h3"])]
            paragraphs = [p.get_text(strip=True) for p in soup.find_all("p")[:3]]
            link_count = len(soup.find_all("a"))
            return {
                "url": url,
                "title": title,
                "description": description,
                "headings": headings[:5],
                "paragraphs": paragraphs,
                "link_count": link_count,
                "crawled_at": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Fehler beim Extrahieren von Inhalten: {e}")
            return None

    def fetch_page(self, url):
        if not self.can_fetch(url):
            logger.info(f"Crawling von {url} durch robots.txt verboten.")
            return None
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()
            return response.text
        except Exception as e:
            # Catch all exceptions (network errors, mocked exceptions, etc.)
            logger.error(f"Fehler beim Abrufen von {url}: {e}")
            return None

    def crawl(self):
        logger.info(f"Starte Crawler mit: {self.start_url}")
        # Wenn Start-URL bereits gecrawlt wurde, nichts tun
        if self.start_url in self.visited:
            logger.info(f"Start-URL {self.start_url} bereits gecrawlt — Abbruch.")
            return self.data
        try:
            while self.to_visit and len(self.visited) < self.max_pages:
                url = self.to_visit.popleft()
                # aus Queue-Set entfernen (falls vorhanden)
                self.to_visit_set.discard(url)
                if url in self.visited:
                    continue
                self.visited.add(url)
                logger.info(f"Crawle ({len(self.visited)}/{self.max_pages}): {url}")

                html = self.fetch_page(url)
                if not html:
                    continue
                content = self.extract_content(url, html)
                if content:
                    # Prüfen, ob bereits im data, um Duplikate zu vermeiden
                    if not any(d["url"] == content["url"] for d in self.data):
                        self.data.append(content)

                links = self.extract_links(url, html)
                self.to_visit.extend(links)

                time.sleep(self.delay)
        except KeyboardInterrupt:
            logger.info("Crawl durch Benutzer abgebrochen (KeyboardInterrupt). Speichere Fortschritt...")
        except Exception as e:
            logger.error(f"Unerwarteter Fehler während des Crawls: {e}")

        logger.info(f"Crawl abgeschlossen! {len(self.visited)} Seiten gecrawlt.")
        return self.data

    def save_to_json(self):
        try:
            # Bestehende Datei laden (falls vorhanden)
            existing_data = []
            if os.path.exists(self.json_file):
                with open(self.json_file, "r", encoding="utf-8") as f:
                    try:
                        existing_data = json.load(f)
                    except json.JSONDecodeError:
                        existing_data = []
            # neue, nicht vorhandene Daten anhängen
            urls_in_existing = {item["url"] for item in existing_data}
            new_items = [item for item in self.data if item["url"] not in urls_in_existing]
            all_data = existing_data + new_items

            with open(self.json_file, "w", encoding="utf-8") as f:
                json.dump(all_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Daten gespeichert in {self.json_file} (gesamt {len(all_data)} Einträge)")
        except Exception as e:
            logger.error(f"Fehler beim Speichern: {e}")

    def get_summary(self):
        return {
            "total_pages": len(self.visited),
            "total_items": len(self.data),
            "domain": self.domain,
            "start_url": self.start_url,
        }


def main():
    parser = argparse.ArgumentParser(description="Einfacher Webcrawler")
    parser.add_argument("--start-url", default="https://minecraft.com", help="Start-URL zum Crawlen")
    parser.add_argument("--max-pages", type=int, default=20, help="Maximale Anzahl Seiten zum Crawlen")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay zwischen Anfragen in Sekunden")
    parser.add_argument("--json-file", default="crawled_data.json", help="JSON-Datei zum Speichern der Ergebnisse")
    parser.add_argument("--no-save", action="store_true", help="Speichert die Ergebnisse nicht in der JSON-Datei")
    args = parser.parse_args()

    crawler = WebCrawler(
        start_url=args.start_url,
        max_pages=args.max_pages,
        delay=args.delay,
        json_file=args.json_file,
    )
    data = crawler.crawl()
    if not args.no_save:
        crawler.save_to_json()

    print("\n=== Crawl-Zusammenfassung ===")
    summary = crawler.get_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
