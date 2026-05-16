import click

from house_cli.client.auth import refresh_cookies_from_cdp


@click.command("refresh-cookies")
@click.option("--domain", default="ke.com", help="Cookie domain to refresh, e.g. ke.com")
@click.option("--port", type=int, default=9222, help="Chrome/Edge remote debugging port")
def refresh_cookies(domain: str, port: int):
    """Refresh site cookies from a verified browser DevTools session."""
    cookies = refresh_cookies_from_cdp(domain, port=port)
    click.echo(f"Saved {len(cookies)} cookies for {domain}.")
