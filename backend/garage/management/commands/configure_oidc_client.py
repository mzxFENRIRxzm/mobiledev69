from django.core.management import BaseCommand

from garage.oidc_client import configure_public_client


class Command(BaseCommand):
    help = "Configure the THE_X public OIDC client without creating demo users."

    def handle(self, *args, **options):
        client = configure_public_client()
        self.stdout.write(self.style.SUCCESS(
            f"Configured {client.client_id} for {', '.join(client.redirect_uris)}"
        ))
