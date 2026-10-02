"""Install the optional native Agent flow without overwriting existing credentials."""
import json
from setup_n8n import ENV, LOCAL, run


def main():
    if not (LOCAL / 'initialized').exists():
        raise SystemExit('Run python scripts/setup_n8n.py first.')
    marker = LOCAL / 'agent-initialized'
    if not marker.exists():
        credentials_file = LOCAL / 'agent-credentials.json'
        try:
            credentials_file.write_text(json.dumps([{
                'id': 'theXGeminiNative', 'name': 'THE_X Gemini native - enter key',
                'type': 'googlePalmApi',
                'data': {'host': 'https://generativelanguage.googleapis.com', 'apiKey': ''},
            }]), encoding='utf-8')
            run('run', '--rm', '--no-deps', 'n8n', 'import:credentials',
                '--input=/bootstrap/agent-credentials.json')
            run('run', '--rm', '--no-deps', 'n8n', 'import:workflow',
                '--input=/workflows/the-x-gemini-agent.json')
            marker.write_text('Native agent imported; preserve user edits and credentials.\n', encoding='utf-8')
        finally:
            credentials_file.unlink(missing_ok=True)
    rag_marker = LOCAL / 'rag-draft-initialized'
    if not rag_marker.exists():
        run('run', '--rm', '--no-deps', 'n8n', 'import:workflow',
            '--input=/workflows/the-x-rag-draft.json')
        rag_marker.write_text('RAG draft imported; preserve user edits. Not an active app endpoint.\n', encoding='utf-8')
    # Select the RAG draft; preserve all existing secrets and workflow definitions.
    lines = ENV.read_text(encoding='utf-8-sig').splitlines()
    lines = [line for line in lines if not line.startswith('AI_CHAT_N8N_PATH=')]
    ENV.write_text('\n'.join(lines)+'\nAI_CHAT_N8N_PATH=the-x-rag-draft\n', encoding='utf-8')
    run('up', '-d', '--wait', 'n8n', 'backend')
    print('Open http://localhost:15678/workflow/theXGeminiAgent')
    print('App target: http://localhost:15678/workflow/theXOneRagDraft (setup required; still unpublished).')
    print('Configure Gemini, PostgreSQL memory, PGVector and reviewed manuals before publishing the RAG workflow.')
    print('No provider calls made. Re-running preserves the workflow and API key.')


if __name__ == '__main__':
    main()
