"""Initialize the optional local AI stack. Never reads or prints a Gemini API key."""
import json
import secrets
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / 'deploy' / '.env'
LOCAL = ROOT / '.local' / 'n8n'
COMPOSE = ['docker', 'compose', '--env-file', str(ENV), '-f', str(ROOT/'compose.deploy.yaml'),
           '-f', str(ROOT/'compose.ai.yaml')]


def run(*args):
    subprocess.run([*COMPOSE, *args], cwd=ROOT, check=True)


def main():
    if not ENV.exists():
        raise SystemExit('Run python scripts/init_docker.py first.')
    LOCAL.mkdir(parents=True, exist_ok=True)
    text = ENV.read_text(encoding='utf-8-sig')
    settings = dict(line.split('=', 1) for line in text.splitlines() if '=' in line and not line.startswith('#'))
    marker = LOCAL / 'initialized'
    if marker.exists() and any(not settings.get(key, '').strip() for key in
                              ['N8N_DB_PASSWORD', 'N8N_ENCRYPTION_KEY', 'AI_CHAT_WEBHOOK_TOKEN']):
        raise SystemExit('Existing n8n secrets are missing. Restore deploy/.env from your backup; do not rotate them automatically.')
    for key in ['N8N_DB_PASSWORD', 'N8N_ENCRYPTION_KEY', 'AI_CHAT_WEBHOOK_TOKEN']:
        if not settings.get(key, '').strip():
            settings[key] = secrets.token_hex(32)
            lines = [line for line in text.splitlines() if not line.startswith(key+'=')]
            text = '\n'.join(lines) + '\n' + key + '=' + settings[key] + '\n'
    ENV.write_text(text, encoding='utf-8')
    credentials_file = LOCAL / 'credentials.json'
    run('up', '-d', '--wait', 'n8n-postgres')
    if not marker.exists():
        # The blank Google credential is deliberately incomplete. Enter the key in n8n UI.
        credentials = [
            {'id': 'theXWebhookAuth', 'name': 'THE_X Django webhook', 'type': 'httpHeaderAuth',
             'data': {'name': 'Authorization', 'value': 'Bearer '+settings['AI_CHAT_WEBHOOK_TOKEN']}},
            {'id': 'theXGeminiApi', 'name': 'THE_X Gemini API key - enter key', 'type': 'httpHeaderAuth',
             'data': {'name': 'x-goog-api-key', 'value': ''}},
        ]
        try:
            credentials_file.write_text(json.dumps(credentials), encoding='utf-8')
            run('run', '--rm', '--no-deps', 'n8n', 'import:credentials', '--input=/bootstrap/credentials.json')
            run('run', '--rm', '--no-deps', 'n8n', 'import:workflow', '--input=/workflows/the-x-gemini.json')
            marker.write_text('Imported initial workflow and credentials; do not overwrite user edits.\n', encoding='utf-8')
        finally:
            credentials_file.unlink(missing_ok=True)
    run('up', '-d', '--wait', 'n8n')
    print('n8n: http://localhost:15678 - complete owner setup, enter Gemini credential, then Publish THE_X Gemini chat.')
    print('Workflow starts unpublished. No paid API calls were made. See docs/ai-chat-n8n.md.')


if __name__ == '__main__':
    main()
