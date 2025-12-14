from django.conf import settings
import sqlite3

# Django-Datenbankpfad automatisch laden
DB_PATH = settings.DATABASES["default"]["NAME"]


def delete_url(url):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM crawled WHERE url = ?", (url,))
    conn.commit()
    conn.close()


def delete_domain(domain):
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM crawled WHERE url LIKE ?", (f"%{domain}%",))
    conn.commit()
    conn.close()


def delete_all():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM crawled")
    conn.commit()
    conn.close()


def delete_404():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DELETE FROM crawled WHERE status_code = 404")
    conn.commit()
    conn.close()
