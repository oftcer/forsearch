# Documentação — ForSearch

## Objetivo

Ferramenta desktop para **pesquisar palavras-chave em grande escala** em discos locais:
pastas com milhares de `.txt`, `.jsonl`, `.csv`, `.sql`, logs, etc.

## Fluxo recomendado (bases grandes)

1. Coloque (ou monte) a base em um disco rápido, ex.: `D:\data\logs`.
2. Abra o ForSearch → **Pasta…** → selecione a raiz.
3. Confira o badge (`N arquivos · X .txt`) — confirma que indexou.
4. Chip de tipo: **JSONL** / **TXT** / **Tudo**.
5. Busque termos específicos primeiro (domínio, marca, e-mail).
6. Exporte → refine em planilha ou segunda busca na pasta de exports.

## Performance

- Varredura recursiva com `os.walk`.
- Ignora pastas pesadas: `.git`, `node_modules`, `__pycache__`, `.venv`, `venv`.
- Limite padrão de resultados: 10 000 hits (evita UI travar).
- Encoding: tenta UTF-8, cp1252, latin-1.
- Arquivos binários (muitos `\x00`) são pulados.

## Formatos de dump

### Multi-linha (REDLINE-like)

```text
URL: https://site.com
Username: user
Password: pass
Application: Chrome
===============
```

Match em qualquer linha → retorna o **bloco inteiro**.

### Uma linha

```text
https://site.com:user:pass
```

Retorna a linha completa.

### JSONL

Cada linha do `.jsonl` é tratada como registro de texto; o match devolve a **linha inteira**.

## CLI legado

`search.py` é o script antigo (terminal). O app oficial é `search_app.py` / `iniciar.bat`.

## Não versionar

- Pasta `db/` e qualquer dump real
- Exports `forsearch_*.txt` / `.csv`
- Credenciais e `.env`
