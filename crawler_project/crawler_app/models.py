from django.db import models
from django.contrib.auth.models import User


class CrawlResult(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="crawl_results")
    url = models.URLField()
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    headings = models.JSONField(default=list, blank=True)
    paragraphs = models.JSONField(default=list, blank=True)
    link_count = models.IntegerField(default=0)
    crawled_at = models.DateTimeField()
    status_code = models.IntegerField(default=200)

    class Meta:
        db_table = "crawled"  # WICHTIG: gleiche Tabelle wie der Crawler
        unique_together = ('user', 'url')

    def __str__(self):
        return f"{self.url} ({self.user.username})"


class DeleteRequest(models.Model):
    REQUEST_TYPES = [
        ("url", "Einzelne URL löschen"),
        ("domain", "Domain löschen"),
        ("all", "Alle Einträge löschen"),
        ("404", "Alle 404‑Einträge löschen"),
    ]

    # user = models.ForeignKey(User, on_delete=models.CASCADE)
    request_type = models.CharField(max_length=20, choices=REQUEST_TYPES)
    value = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)

    def __str__(self):
        return f"Anfrage: {self.request_type}"


class CrawlLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at}: {self.message}"
