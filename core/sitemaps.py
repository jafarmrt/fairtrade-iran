from wagtail.contrib.sitemaps import Sitemap


class AllLanguagesSitemap(Sitemap):
    """Wagtail's sitemap only walks the default site's root page (the Persian tree).
    Include every language tree, skipping pages that ask to be left out."""

    def items(self):
        from wagtail.models import Page

        root = self.get_wagtail_site().root_page
        pages = Page.objects.none()
        for home in root.get_translations(inclusive=True):
            pages = pages | Page.objects.descendant_of(home, inclusive=True)
        return pages.live().public().order_by("path").defer_streamfields().specific()

    def _urls(self, page, protocol, domain):
        # Page URLs are built from the Wagtail Site's hostname; use the address the
        # site is actually reached at, as robots.txt and canonical links do.
        urls = super()._urls(page, protocol, domain)
        site_root = self.get_wagtail_site().root_url
        here = self.request.build_absolute_uri("/").rstrip("/")
        for info in urls:
            if info["location"].startswith(site_root):
                info["location"] = here + info["location"][len(site_root):]
        return urls
