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
    def __init__(
        self,
        start_url,
        max_pages=50,
        delay=1,
        json_file="crawled_data.json",
        save_to_json=False,
        db_path="db.sqlite3",
    ):
        self.start_url = start_url
        self.max_pages = max_pages
        self.delay = delay
        self.visited = set()
        self.to_visit = deque([start_url])
        self.data = []
        self.json_file = json_file
        self.save_to_json_flag = save_to_json
        self.db_path = db_path

        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0 Safari/537.36"
            )
        }

        self.domain = urlparse(start_url).netloc

        # robots.txt laden
        self.robot_parser = None
        robots_url = urljoin(f"https://{self.domain}", "/robots.txt")
        try:
            resp = requests.get(robots_url, headers=self.headers, timeout=5)
            if resp.status_code == 200:
                self.robot_parser = RobotFileParser()
                self.robot_parser.parse(resp.text.splitlines())
                logger.info(f"robots.txt geladen von {robots_url}")
            else:
                logger.info(
                    f"robots.txt nicht gefunden (Status {resp.status_code}), erlaube standardmäßig alles"
                )
                self.robot_parser = None
        except Exception as e:
            logger.warning(
                f"robots.txt konnte nicht geladen werden: {e}. Erlaube standardmäßig alles."
            )
            self.robot_parser = None

        # Set zur Verhinderung mehrfacher Einträge in der Queue
        self.to_visit_set = {self.normalize_url(u) for u in self.to_visit}

    # ----------------- Hilfsfunktionen -----------------

    def normalize_url(self, url: str) -> str:
        try:
            parsed = urlparse(url)
            no_frag = parsed._replace(fragment="")
            norm = no_frag.geturl()
            if norm.endswith("/") and no_frag.path not in ("", "/"):
                norm = norm.rstrip("/")
            return norm
        except Exception:
            return url

    def can_fetch(self, url):
        try:
            if not self.robot_parser:
                return True
            return self.robot_parser.can_fetch(
                self.headers["User-Agent"], self.normalize_url(url)
            )
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

    # ----------------- DB-Funktionen -----------------

    def init_db(self):
        """Initialisiert die SQLite-Datenbank mit passender Tabelle."""
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
                    crawled_at TEXT,
                    status_code INTEGER
                )
                """
            )
            conn.commit()
            conn.close()
            logger.info(f"SQLite DB initialisiert: {self.db_path}")
        except Exception as e:
            logger.error(f"Fehler beim Initialisieren der DB {self.db_path}: {e}")

    def save_record_to_db(self, record: dict):
        """Speichert einen Datensatz in der SQLite-DB."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            headings_json = json.dumps(record.get("headings", []), ensure_ascii=False)
            paragraphs_json = json.dumps(record.get("paragraphs", []), ensure_ascii=False)
            cur.execute(
                """
                INSERT OR REPLACE INTO crawled (
                    url, title, description, headings, paragraphs,
                    link_count, crawled_at, status_code
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.get("url"),
                    record.get("title"),
                    record.get("description"),
                    headings_json,
                    paragraphs_json,
                    record.get("link_count"),
                    record.get("crawled_at"),
                    record.get("status_code"),
                ),
            )
            conn.commit()
            conn.close()
            logger.debug(f"Datensatz in DB gespeichert: {record.get('url')}")
        except Exception as e:
            logger.error(f"Fehler beim Speichern in DB: {e}")

    # --------- Delete-Operationen für die DB ---------

    def delete_url_from_db(self, url):
        """Löscht eine einzelne URL aus der SQLite-Datenbank."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("DELETE FROM crawled WHERE url = ?", (url,))
            deleted = cur.rowcount
            conn.commit()
            conn.close()
            logger.info(f"{deleted} Eintrag(e) für URL gelöscht: {url}")
        except Exception as e:
            logger.error(f"Fehler beim Löschen der URL {url}: {e}")

    def delete_domain_from_db(self, domain):
        """Löscht alle URLs einer Domain aus der SQLite-Datenbank."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            pattern = f"%{domain}%"
            cur.execute("DELETE FROM crawled WHERE url LIKE ?", (pattern,))
            deleted = cur.rowcount
            conn.commit()
            conn.close()
            logger.info(f"{deleted} Einträge für Domain gelöscht: {domain}")
        except Exception as e:
            logger.error(f"Fehler beim Löschen der Domain {domain}: {e}")

    def clear_database(self):
        """Leert die gesamte SQLite-Datenbanktabelle 'crawled'."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("DELETE FROM crawled")
            deleted = cur.rowcount
            conn.commit()
            conn.close()
            logger.info(f"SQLite-Datenbank geleert ({deleted} Einträge entfernt).")
        except Exception as e:
            logger.error(f"Fehler beim Leeren der Datenbank: {e}")

    def delete_404_from_db(self):
        """Löscht alle URLs mit Statuscode 404 aus der SQLite-Datenbank."""
        try:
            conn = sqlite3.connect(self.db_path)
            cur = conn.cursor()
            cur.execute("DELETE FROM crawled WHERE status_code = 404")
            deleted = cur.rowcount
            conn.commit()
            conn.close()
            logger.info(f"{deleted} Einträge mit Status 404 gelöscht.")
        except Exception as e:
            logger.error(f"Fehler beim Löschen der 404-Einträge: {e}")

    # ----------------- Crawl-Logik -----------------

    def extract_links(self, url, html):
        links = []
        try:
            soup = BeautifulSoup(html, "html.parser")
            for link in soup.find_all("a", href=True):
                absolute_url = urljoin(url, link["href"])
                norm = self.normalize_url(absolute_url)
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
        """Holt eine Seite ab und liefert (html, status_code)."""
        if not self.can_fetch(url):
            logger.info(f"Crawling von {url} durch robots.txt verboten.")
            return None, None
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            status = response.status_code
            if status == 404:
                logger.warning(f"404 gefunden: {url}")
            # Wir speichern auch bei 404, werfen aber keine Exception mehr für status_code
            try:
                response.raise_for_status()
            except Exception:
                # Fehler loggen, aber wir geben dennoch HTML + Status zurück
                logger.error(f"HTTP-Fehler beim Abrufen von {url}: {status}")
            return response.text, status
        except Exception as e:
            logger.error(f"Fehler beim Abrufen von {url}: {e}")
            return None, None

    def crawl(self):
        logger.info(f"Starte Crawler mit: {self.start_url}")

        try:
            while self.to_visit and len(self.visited) < self.max_pages:
                url = self.to_visit.popleft()
                self.to_visit_set.discard(self.normalize_url(url))
                norm_url = self.normalize_url(url)
                if norm_url in self.visited:
                    continue
                self.visited.add(norm_url)
                logger.info(f"Crawle ({len(self.visited)}/{self.max_pages}): {norm_url}")

                html, status = self.fetch_page(url)
                if not html:
                    continue

                content = self.extract_content(url, html)
                if content:
                    content["status_code"] = status if status is not None else 0
                    self.data.append(content)

                links = self.extract_links(url, html)
                self.to_visit.extend(links)

                time.sleep(self.delay)
        except KeyboardInterrupt:
            logger.info("Crawl durch Benutzer abgebrochen (KeyboardInterrupt).")
        except Exception as e:
            logger.error(f"Unerwarteter Fehler während des Crawls: {e}")

        logger.info(f"Crawl abgeschlossen! {len(self.visited)} Seiten bearbeitet.")
        return self.data

    # ----------------- JSON (optional) -----------------

    def save_to_json(self):
        if not self.save_to_json_flag:
            logger.info("Speichern in JSON ist deaktiviert.")
            return

        try:
            existing_data = []
            if os.path.exists(self.json_file):
                with open(self.json_file, "r", encoding="utf-8") as f:
                    try:
                        existing_data = json.load(f)
                    except json.JSONDecodeError:
                        existing_data = []

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
            logger.info(f"Daten in JSON gespeichert: {self.json_file} ({len(all_data)} Einträge)")
        except Exception as e:
            logger.error(f"Fehler beim Speichern in JSON: {e}")

    def get_summary(self):
        return {
            "total_pages": len(self.visited),
            "total_items": len(self.data),
            "domain": self.domain,
            "start_url": self.start_url,
        }


# ----------------- CLI-Hilfsfunktion -----------------


def main():
    parser = argparse.ArgumentParser(description="Einfacher Webcrawler (SQLite-only)")
    parser.add_argument("--start-url", default="https://wikipedia.org", help="Start-URL zum Crawlen")
    parser.add_argument("--max-pages", type=int, default=500, help="Maximale Anzahl Seiten zum Crawlen")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay zwischen Anfragen in Sekunden")
    parser.add_argument("--json-file", default="crawled_data.json", help="JSON-Datei (optional)")
    parser.add_argument("--save-to-json", action="store_true", help="Speichert Ergebnisse zusätzlich in einer JSON-Datei")
    parser.add_argument("--db-file", default="db.sqlite3", help="Pfad zur SQLite DB-Datei (z.B. db.sqlite3)")

    # Delete-Optionen
    parser.add_argument("--delete-url", help="Löscht eine einzelne URL aus der DB")
    parser.add_argument("--delete-domain", help="Löscht alle URLs einer Domain aus der DB")
    parser.add_argument("--clear-db", action="store_true", help="Leert die gesamte SQLite-Tabelle")
    parser.add_argument("--delete-404", action="store_true", help="Löscht alle URLs mit HTTP-Status 404 aus der DB")

    args = parser.parse_args()

    # Crawler-Instanz nur für DB-Operationen
    crawler = WebCrawler(
        start_url=args.start_url,
        max_pages=args.max_pages,
        delay=args.delay,
        json_file=args.json_file,
        save_to_json=args.save_to_json,
        db_path=args.db_file,
    )

    # Lösch-Operationen (beenden das Programm nach Ausführung)
    if args.delete_url:
        crawler.delete_url_from_db(args.delete_url)
        return

    if args.delete_domain:
        crawler.delete_domain_from_db(args.delete_domain)
        return

    if args.clear_db:
        crawler.clear_database()
        return

    if args.delete_404:
        crawler.delete_404_from_db()
        return

    # Normaler Crawl
    data = crawler.crawl()
    if args.save_to_json:
        crawler.save_to_json()

    print("\n=== Crawl-Zusammenfassung ===")
    summary = crawler.get_summary()
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
