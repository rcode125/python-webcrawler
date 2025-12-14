from django.contrib import admin, messages
from .models import CrawlResult, DeleteRequest, CrawlLog
from .crawler_tools import delete_url, delete_domain, delete_all, delete_404


@admin.register(CrawlResult)
class CrawlResultAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "url", "title", "status_code", "link_count", "crawled_at")
    list_filter = ("user", "status_code", "crawled_at")
    search_fields = ("url", "title", "description", "user__username")

    readonly_fields = ("crawled_at", "headings", "paragraphs", "link_count", "status_code")

    actions = ["delete_selected_results", "delete_by_url", "delete_by_user", "delete_404_entries"]

    def delete_selected_results(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(request, f"{count} Einträge gelöscht.", messages.SUCCESS)

    def delete_by_url(self, request, queryset):
        urls = queryset.values_list("url", flat=True).distinct()
        total = 0
        for url in urls:
            deleted, _ = CrawlResult.objects.filter(url=url).delete()
            total += deleted
        self.message_user(request, f"{total} Einträge gelöscht.", messages.SUCCESS)

    def delete_by_user(self, request, queryset):
        users = queryset.values_list("user", flat=True).distinct()
        total = 0
        for uid in users:
            deleted, _ = CrawlResult.objects.filter(user_id=uid).delete()
            total += deleted
        self.message_user(request, f"{total} Einträge gelöscht.", messages.SUCCESS)

    def delete_404_entries(self, request, queryset):
        deleted, _ = CrawlResult.objects.filter(status_code=404).delete()
        self.message_user(request, f"{deleted} 404‑Einträge gelöscht.", messages.SUCCESS)


@admin.register(DeleteRequest)
class DeleteRequestAdmin(admin.ModelAdmin):
    list_display = ("user", "request_type", "value", "created_at", "processed")
    list_filter = ("request_type", "processed")
    actions = ["process_requests"]

    def process_requests(self, request, queryset):
        count = 0
        for req in queryset:
            if req.processed:
                continue

            if req.request_type == "url":
                delete_url(req.value)
            elif req.request_type == "domain":
                delete_domain(req.value)
            elif req.request_type == "all":
                delete_all()
            elif req.request_type == "404":
                delete_404()

            req.processed = True
            req.save()
            count += 1

        self.message_user(request, f"{count} Anfragen verarbeitet.", messages.SUCCESS)


@admin.register(CrawlLog)
class CrawlLogAdmin(admin.ModelAdmin):
    list_display = ("user", "message", "created_at")
    list_filter = ("user",)
    search_fields = ("message", "user__username")
