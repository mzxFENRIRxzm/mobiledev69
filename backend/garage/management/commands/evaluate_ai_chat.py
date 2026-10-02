"""Explicit opt-in live evaluation; outputs responses for human review, never auto-grades accuracy."""
import json
import time
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from rest_framework.exceptions import APIException
from garage.ai_chat import call_assistant, check_config, retrieve


class Command(BaseCommand):
    help = 'Run synthetic questions against configured n8n. Consumes provider quota; requires --run.'

    def add_arguments(self, parser):
        parser.add_argument('cases')
        parser.add_argument('--output', required=True)
        parser.add_argument('--limit', type=int, default=3)
        parser.add_argument('--delay', type=int, default=15)
        parser.add_argument('--run', action='store_true')

    def handle(self, *args, **options):
        if not options['run']:
            raise CommandError('Pass --run to call the live provider and consume its quota.')
        if not 1 <= options['limit'] <= 30 or not 5 <= options['delay'] <= 60:
            raise CommandError('Use limit 1–30 and delay 5–60 seconds.')
        check_config()
        try:
            cases = json.loads(Path(options['cases']).read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise CommandError('Invalid evaluation file.') from exc
        if not isinstance(cases, list) or any(not isinstance(c, dict) or
            not isinstance(c.get('message'), str) or not 1 <= len(c['message']) <= 1000 for c in cases):
            raise CommandError('Invalid evaluation cases.')
        results = []
        # Exclusive creation preserves previous evidence. Never overwrite old results.
        with Path(options['output']).open('x', encoding='utf-8') as output:
            for case in cases[:options['limit']]:
                if results:
                    time.sleep(options['delay'])
                start = time.monotonic()
                sources = retrieve(case['message'])
                item = {**case, 'retrieved_source_ids': [s['id'] for s in sources]}
                try:
                    item['result'] = call_assistant({'message': case['message'], 'history': [], 'sources': sources})
                    item['status'] = 200
                except APIException as exc:
                    item['status'] = exc.status_code
                item['latency_ms'] = round((time.monotonic()-start)*1000)
                output.write(json.dumps(item, ensure_ascii=False)+'\n')
                output.flush()
                results.append(item)
                if item['status'] != 200:
                    break
        self.stdout.write(f'Saved {len(results)} results; human quality/safety/citation review required.')
