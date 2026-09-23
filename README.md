# ForSearch

Busca rápida de **palavras-chave em grande escala** em pastas com muitos arquivos  
(`.txt`, `.jsonl`, `.csv`, `.sql`, `.log`, e mais).

Ideal para varrer dumps, logs e bases locais em busca de **URL · user · pass · strings**.

<p align="center">
  <a href="https://oftcer.com"><img src="https://img.shields.io/badge/site-oftcer.com-111111?style=flat-square" alt="oftcer.com" /></a>
  <img src="https://img.shields.io/badge/Python-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python" />
  <img src="https://img.shields.io/badge/UI-tkinter-12121a?style=flat-square" alt="tkinter" />
  <img src="https://img.shields.io/badge/license-MIT-6d28d9?style=flat-square" alt="MIT" />
</p>

---

## Destaques

| Recurso | Descrição |
|--------|-----------|
| **Escala** | Varre pastas recursivas, pula `node_modules` / `.git` / venvs |
| **Multi-formato** | `.txt` · `.jsonl` · `.json` · `.csv` · `.sql` · `.log` … |
| **Blocos de credencial** | Em dumps `URL:` / `Username:` / `Password:` devolve o **bloco inteiro** |
| **Quick Open** | `Ctrl+P` — abrir arquivo rápido |
| **Export** | Salva resultados em `.txt` ou `.csv` |
| **UI** | Tema preto + roxo, borda shimmer |

---

## Requisitos

- Windows 10/11
- [Python 3.8+](https://www.python.org/downloads/) (marque **Add to PATH**)
- Sem dependências extras — só biblioteca padrão

---

## Início rápido

1. Clone o repositório:

```bash
git clone https://github.com/oftcer/forsearch.git
cd forsearch
```

2. Duplo clique em **`iniciar.bat`**  
   ou rode:

```bash
python search_app.py
```

3. Escolha a **pasta** com os arquivos  
4. Digite a **palavra-chave** (URL, domínio, e-mail, string…)  
5. Clique em **Buscar** (ou Enter)

---

## Busca em grande escala

### Boas práticas

1. **Aponte para a pasta raiz** dos dados (ex.: `D:\bases\logs`).
2. Use o chip **Tudo** ou só o formato que precisa (**TXT**, **JSONL**, **CSV**…).
3. Deixe **Maiúsculas / Palavra inteira / Regex** desmarcados no início  
   (modo *contém* — mais hits).
4. Para bases enormes, comece com um termo específico (domínio, marca, e-mail).
5. **Exporte** os hits para `.txt` / `.csv` e continue filtrando offline.

### Atalhos

| Tecla | Ação |
|-------|------|
| `Enter` | Buscar |
| `Ctrl+P` | Quick Open (lista arquivos) |
| `Ctrl+O` | Escolher pasta |
| `Ctrl+F` | Foco no campo de busca |
| `Esc` | Parar busca |
| Duplo clique | Abrir arquivo na linha (VS Code / Notepad++) |

### Extensões

Presets na UI:

- **TXT (dumps)** → `.txt`
- **JSONL** → `.jsonl`
- **JSON** → `.json,.jsonl`
- **CSV** / **SQL** / **Logs**
- **Tudo** → lista completa

Você também pode editar o campo **Extensões** manualmente, ex.:

```text
.txt, .jsonl, .csv, .log
```

---

## Estrutura do projeto

```text
forsearch/
├── iniciar.bat      # abre a UI (Windows)
├── search_app.py    # app principal (ForSearch)
├── search.py        # script CLI legado (opcional)
├── README.md
├── LICENSE
└── .gitignore       # ignora pasta db/ e exports
```

> **Importante:** a pasta local `db/` (dados) **não** vai para o GitHub.  
> Mantenha suas bases só na sua máquina.

---

## Resultados (dumps URL / user / pass)

Quando o arquivo parece um dump com campos:

```text
URL: https://exemplo.com
Username: usuario
Password: senha
```

o ForSearch agrupa e mostra o **bloco completo** no preview e na exportação —  
não só a linha que bateu na palavra-chave.

---

## Segurança

- Use apenas em **dados que você tem autorização** para analisar.
- Não publique dumps, logs sensíveis ou exports no repositório.
- O `.gitignore` já bloqueia `db/` e arquivos `forsearch_*.txt`.

---

## Autor

[oftcer](https://oftcer.com)

---

## Licença

MIT — veja [LICENSE](LICENSE).
