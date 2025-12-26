from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.contrib import messages

from .forms import CrawlForm, DeleteRequestForm
from .models import CrawlResult, CrawlLog
from .crawler import WebCrawler   # dein Crawler


# ✅ Dashboard mit Logs + Ergebnissen
@login_required
def dashboard(request):
    results = CrawlResult.objects.filter(user=request.user).order_by("-crawled_at")
    logs = CrawlLog.objects.filter(user=request.user)[:50]

    return render(request, "crawler_app/dashboard.html", {
        "results": results,
        "logs": logs,
    })


# ✅ Crawl starten
@login_required
def start_crawl(request):
    progress = 0

    if request.method == "POST":
        form = CrawlForm(request.POST)

        if form.is_valid():
            start_url = form.cleaned_data["start_url"]

            # ✅ Popup wenn URL bereits existiert
            if CrawlResult.objects.filter(url=start_url, user=request.user).exists():
                messages.warning(request, "Diese Seite wurde bereits gecrawlt!")
                return redirect("dashboard")

            # ✅ Log: Crawl gestartet
            CrawlLog.objects.create(
                user=request.user,
                message=f"Crawler gestartet für: {start_url}"
            )

            crawler = WebCrawler(
                start_url=start_url,
                max_pages=form.cleaned_data["max_pages"],
                delay=form.cleaned_data["delay"]
            )


            total = form.cleaned_data["max_pages"]

            # ✅ Crawl Schritt für Schritt
            for i, item in enumerate(crawler.crawl()):
                progress = int(((i + 1) / total) * 100)

                # ✅ Ergebnis speichern
                CrawlResult.objects.update_or_create(
                    user=request.user,
                    url=item["url"],
                    defaults={
                    "title": item["title"],
                    "description": item["description"],
                    "headings": item["headings"],
                    "paragraphs": item["paragraphs"],
                    "link_count": item["link_count"],
                    "status_code": item["status_code"],
                    "crawled_at": timezone.now(),
                    }
                )


                # ✅ Log für jede gecrawlte Seite
                CrawlLog.objects.create(
                    user=request.user,
                    message=f"Gecrawlt: {item['url']} (Status {item.get('status_code', 200)})"
                )

            # ✅ Log: Crawl beendet
            CrawlLog.objects.create(
                user=request.user,
                message=f"Crawler beendet für: {start_url}"
            )

            messages.success(request, "Crawl erfolgreich abgeschlossen!")
            return redirect("dashboard")

    else:
        form = CrawlForm()

    return render(request, "crawler_app/start_crawl.html", {
        "form": form,
        "progress": progress
    })


# ✅ Löschanfrage an Admin senden
@login_required
def request_delete_view(request):
    if request.method == "POST":
        form = DeleteRequestForm(request.POST)

        if form.is_valid():
            delete_request = form.save(commit=False)
            delete_request.user = request.user
            delete_request.save()

            # ✅ Log speichern
            CrawlLog.objects.create(
                user=request.user,
                message=f"Löschanfrage gestellt: {delete_request.request_type} ({delete_request.value})"
            )

            messages.success(request, "Deine Anfrage wurde an den Admin gesendet.")
            return redirect("dashboard")

    else:
        form = DeleteRequestForm()

    return render(request, "crawler_app/request_delete.html", {"form": form})

