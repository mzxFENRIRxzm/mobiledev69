"""Import reviewed manual excerpts from local JSON; inactive until admin approval."""
import json
from pathlib import Path
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from garage.models import KnowledgeChunk


class Command(BaseCommand):
    help = 'Import a JSON array of manual excerpts (title, source_url, locator, keywords, content).'

    def add_arguments(self, parser):
        parser.add_argument('file')

    def handle(self, *args, **options):
        path = Path(options['file'])
        try:
            if path.stat().st_size > 2_000_000:
                raise CommandError('File must be at most 2 MB.')
            records = json.loads(path.read_text(encoding='utf-8-sig'))
        except (OSError, ValueError) as exc:
            raise CommandError('Cannot read valid UTF-8 JSON.') from exc
        if not isinstance(records, list) or not 1 <= len(records) <= 500:
            raise CommandError('Expected 1–500 excerpts.')
        created = 0
        with transaction.atomic():
            for index, record in enumerate(records, 1):
                if not isinstance(record, dict) or set(record) - {'title', 'source_url', 'locator', 'keywords', 'content'}:
                    raise CommandError(f'Unexpected fields in item {index}.')
                chunk = KnowledgeChunk(**record)
                try:
                    chunk.full_clean()
                except (ValidationError, TypeError) as exc:
                    raise CommandError(f'Invalid item {index}: {exc}') from exc
                if not KnowledgeChunk.objects.filter(source_url=chunk.source_url, locator=chunk.locator,
                                                      content=chunk.content).exists():
                    chunk.save()
                    created += 1
        self.stdout.write(f'Imported {created} inactive excerpts. Review and activate in Django admin.')
