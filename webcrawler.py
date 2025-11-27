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
import sqlite3

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class WebCrawler:
    def __init__(self, start_url, max_pages=50, delay=1, json_file="crawled_data.json", save_to_db=False, db_path="crawled_data.db"):
        self.start_url = start_url
        self.max_pages = max_pages
        self.delay = delay
        self.visited = set()
        self.to_visit = deque([start_url])
        self.data = []
        self.json_file = json_file
        self.save_to_db = save_to_db
        self.db_path = db_path
        
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        }

        self.domain = urlparse(start_url).netloc
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

        # Set zur Verhinderung mehrfacher Einträge in der Queue
        # speichere normalisierte URLs in der Queue-Set (frühzeitig initialisieren)
        self.to_visit_set = {self.normalize_url(u) for u in self.to_visit}

        # optional: SQLite DB initialisieren
        if self.save_to_db:
            try:
                self.init_db()
            except Exception:
                logger.exception("Fehler beim Initialisieren der SQLite-DB")

        # Existierende URLs aus JSON laden zur Duplikatvermeidung
        try:
            self.load_existing_data()
        except Exception:
            # load_existing_data intern loggt Fehler; wir stellen sicher, dass __init__ weiterläuft
            logger.exception("Fehler beim Laden vorhandener Daten in __init__")

    def load_existing_data(self):
        if os.path.exists(self.json_file):
            try:
                with open(self.json_file, "r", encoding="utf-8") as f:
                    existing = json.load(f)
                    # normalize and dedupe existing entries, but only for current domain
                    seen = set()
                    deduped = []
                    for item in existing:
                        url = item.get("url")
                        if not url:
                            continue
                        parsed = urlparse(url)
                        if parsed.netloc != self.domain:
                            continue  # skip URLs from other domains
                        norm = self.normalize_url(url)
                        if norm in seen:
                            continue
                        seen.add(norm)
                        deduped.append(item)
                        self.visited.add(norm)
                    self.data = deduped
                logger.info(f"{len(self.visited)} URLs aus {self.json_file} geladen (nur Domain {self.domain}) zum Vermeiden von Duplikaten")
            except Exception as e:
                logger.error(f"Fehler beim Laden vorhandener Daten: {e}")

    def normalize_url(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            no_frag = parsed._replace(fragment="")
            norm = no_frag.geturl()
            # remove trailing slash for non-root paths
            if norm.endswith('/') and no_frag.path not in ('', '/'):
                norm = norm.rstrip('/')
            return norm
        except Exception:
            return url

    def init_db(self):
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS crawled (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE,
                    title TEXT,
                    description TEXT,
                    headings TEXT,
                    paragraphs TEXT,
                    link_count INTEGER,
                    crawled_at TEXT
                )
                """
            )
            conn.commit()
            conn.close()
            logger.info(f"SQLite DB initialisiert: {self.db_path}")
        except Exception as e:
            logger.error(f"Fehler beim Initialisieren der DB {self.db_path}: {e}")

    def save_record_to_db(self, record: dict):
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            headings_json = json.dumps(record.get("headings", []), ensure_ascii=False)
            paragraphs_json = json.dumps(record.get("paragraphs", []), ensure_ascii=False)
            cur.execute(
                """
                INSERT OR IGNORE INTO crawled (url, title, description, headings, paragraphs, link_count, crawled_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("url"),
                    record.get("title"),
                    record.get("description"),
                    headings_json,
                    paragraphs_json,
                    record.get("link_count"),
                    record.get("crawled_at"),
                ),
            )
            conn.commit()
            conn.close()
            logger.debug(f"Datensatz in DB gespeichert: {record.get('url')}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern in DB: {e}")

    def can_fetch(self, url):
        # wenn kein Robotparser verfügbar ist, erlauben wir das Crawlen
        try:
            if not self.robot_parser:
                return True
            return self.robot_parser.can_fetch(self.headers["User-Agent"], self.normalize_url(url))
        except Exception:
            return True

    def is_valid_url(self, url):
        try:
            parsed = urlparse(url)
            if parsed.scheme not in ("http", "https"):
                return False
            if parsed.netloc != self.domain:
                return False
            clean = self.normalize_url(url)
            if clean in self.visited:
                return False
            return self.can_fetch(clean)
        except Exception:
            return False

    def extract_links(self, url, html):
        links = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.find_all("a", href=True):
                absolute_url = urljoin(url, link["href"])
                norm = self.normalize_url(absolute_url)
                # nur hinzufügen, wenn gültig und noch nicht in Queue/visited
                if self.is_valid_url(absolute_url) and norm not in self.to_visit_set:
                    links.append(absolute_url)
                    self.to_visit_set.add(norm)
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
        if self.normalize_url(self.start_url) in self.visited:
            logger.info(f"Start-URL {self.start_url} bereits gecrawlt — Abbruch.")
            return self.data
        try:
            while self.to_visit and len(self.visited) < self.max_pages:
                url = self.to_visit.popleft()
                # aus Queue-Set entfernen (falls vorhanden) - nutze normalisierte Form
                self.to_visit_set.discard(self.normalize_url(url))
                norm_url = self.normalize_url(url)
                if norm_url in self.visited:
                    continue
                self.visited.add(norm_url)
                logger.info(f"Crawle ({len(self.visited)}/{self.max_pages}): {norm_url}")

                html = self.fetch_page(url)
                if not html:
                    continue
                content = self.extract_content(url, html)
                if content:
                    # Prüfen, ob bereits im data, um Duplikate zu vermeiden
                    if not any(d["url"] == content["url"] for d in self.data):
                        self.data.append(content)
                        if self.save_to_db:
                            try:
                                self.save_record_to_db(content)
                            except Exception:
                                logger.exception("Fehler beim Speichern eines Eintrags in die DB")

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
            # normalize urls in existing and current data, avoid duplicates
            urls_in_existing = {self.normalize_url(item.get("url", "")) for item in existing_data}
            new_items = []
            for item in self.data:
                url = item.get("url")
                if not url:
                    continue
                norm = self.normalize_url(url)
                if norm in urls_in_existing:
                    continue
                urls_in_existing.add(norm)
                new_items.append(item)
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



def clean_json_file(json_file, normalizer):
    if not os.path.exists(json_file):
        print(f"Datei {json_file} nicht gefunden.")
        return
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        seen = set()
        deduped = []
        for item in data:
            url = item.get("url")
            if not url:
                continue
            norm = normalizer(url)
            if norm in seen:
                continue
            seen.add(norm)
            deduped.append(item)
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(deduped, f, indent=2, ensure_ascii=False)
        print(f"{len(deduped)} eindeutige Einträge in {json_file} gespeichert.")
    except Exception as e:
        print(f"Fehler beim Bereinigen: {e}")

def main():
    parser = argparse.ArgumentParser(description="Einfacher Webcrawler")
    parser.add_argument("--start-url", default="https://github.com", help="Start-URL zum Crawlen")
    parser.add_argument("--max-pages", type=int, default=20, help="Maximale Anzahl Seiten zum Crawlen")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay zwischen Anfragen in Sekunden")
    parser.add_argument("--json-file", default="crawled_data.json", help="JSON-Datei zum Speichern der Ergebnisse")
    parser.add_argument("--save-to-db", action="store_true", help="Speichert Ergebnisse zusätzlich in einer SQLite .db Datei")
    parser.add_argument("--db-file", default="crawled_data.db", help="Pfad zur SQLite DB-Datei")
    parser.add_argument("--no-save", action="store_true", help="Speichert die Ergebnisse nicht in der JSON-Datei")
    parser.add_argument("--clean-json", action="store_true", help="Bereinigt die JSON-Datei und beendet das Programm")
    args = parser.parse_args()

    if args.clean_json:
        # Nur die Datei bereinigen und beenden
        # Wir nutzen die Normalisierungsmethode der Klasse
        clean_json_file(args.json_file, WebCrawler.normalize_url)
        return

    crawler = WebCrawler(
        start_url=args.start_url,
        max_pages=args.max_pages,
        delay=args.delay,
        json_file=args.json_file,
        save_to_db=args.save_to_db,
        db_path=args.db_file,
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
