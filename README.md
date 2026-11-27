# PizZap

Sistema web que transforma os parâmetros de uma fornada (quantidade, tamanho, tipo de massa e sabores) em uma receita pronta, com a quantidade certa de cada ingrediente em gramas, quilos ou medidas caseiras.

Projeto acadêmico de Gestão de Projetos de Software (2026). Equipe: João Pedro Vicente, Maria Fernanda Sayuri e Victor Augusto.

**Stack:** Python 3.9+ · Flask · Flask-Limiter · Waitress · HTML/CSS com Jinja2 · MySQL 8 (PyMySQL) · pytest · Locust.

| Documento | Conteúdo |
|---|---|
| [docs/API.md](docs/API.md) | Todos os endpoints, com exemplos de requisição e resposta |
| [docs/DICIONARIO_DE_DADOS.md](docs/DICIONARIO_DE_DADOS.md) | As 7 tabelas do MySQL: colunas, tipos, chaves, índices, regras e fontes dos dados |
| [docs/OPERACAO.md](docs/OPERACAO.md) | Instalação, como ligar, monitoramento, teste de carga, backup e problemas comuns |

---

## Como rodar

1. Abra a pasta `pizzap` no VS Code e abra o terminal.
2. Crie o ambiente virtual: `python -m venv .venv` e ative (`.venv\Scripts\activate` no Windows).
3. Copie `.env.exemplo` para `.env` e coloque nele a senha do seu MySQL, a `CHAVE_API` da equipe e uma `SECRET_KEY`. O `.env` fica só no seu computador (está no `.gitignore`).
4. Rode **um único comando**:

   ```bash
   python iniciar.py
   ```

   Ele instala as dependências, cria o banco (se ainda não existir) e liga o servidor em http://127.0.0.1:5000.

Para programar, use `python app.py`, que recarrega ao salvar. Sem MySQL (`USAR_MYSQL = False`), o sistema roda só com `dados.py` e guarda as receitas na memória.

**API (só a equipe):** não aparece no site. Com o sistema ligado, abra uma vez http://127.0.0.1:5000/api?chave=SUA_CHAVE (a `CHAVE_API` do `.env`). A página permite cadastrar ingredientes e medidas caseiras no banco e fazer as consultas. Sem a chave, `/api` responde 404.

**Testes:** `python -m pytest`. Também dá para usar a aba **Testes** do VS Code. Os testes do banco aparecem como *skipped* quando o MySQL não está acessível.

---

## Arquivos

| Arquivo | O que tem | EAP |
|---|---|---|
| `app.py` | Telas, API de receitas, rate limit, logs, `/api/status` e páginas de erro | 1.1, 1.2.1, 1.3.1, 1.5.3 |
| `receita.py` | Validação, cálculo das proporções, conversão de medidas e montagem da receita | 1.2.1, 1.2.2, 1.2.3 |
| `models.py` | Leitura do banco (em lote, com cache) e gravação das receitas em segundo plano | 1.2.4, 1.4.1 |
| `api_banco.py` | API do banco (`/api/banco`): cadastro de ingredientes e medidas, e consultas | 1.4.1 |
| `dados.py` | Tamanhos, proporções das massas e limites; cópia dos dados do banco para rodar sem MySQL | 1.2.2 |
| `config.py` | Configurações; lê a senha do MySQL e as chaves do `.env` | 1.5.1 |
| `.env.exemplo` | Modelo do `.env` | 1.5.1 |
| `iniciar.py` | Sobe o sistema com um comando (dependências, banco e servidor Waitress) | 1.5.1 |
| `database/schema.sql` | As 7 tabelas, chaves, índices e dados iniciais (com as fontes) | 1.4.1 |
| `templates/`, `static/` | Telas (home, formulário, receita, teste da API, erro), CSS e JS | 1.1.1 a 1.1.3 |
| `ferramentas/monitorar.py` | Verificação a cada minuto, gravada em CSV | 1.5.3 |
| `ferramentas/locustfile.py` | Teste de carga com o Locust (usuários simulados) | 1.5.3 |
| `tests/` | Testes automáticos: regras sem banco, banco, API do banco e entradas inválidas | QA |

---

## Regras de cálculo

- **Peso da massa:** área da pizza (π × raio²) × fator do tipo de massa. Fina 0,24 · Napolitana tradicional 0,26 · Tradicional e Integral 0,36 · Massa grossa 0,55 g/cm². Exemplo: Grande (35 cm), Tradicional → 962 cm² × 0,36 = 346 g.
- **Ingredientes da massa (porcentagem do padeiro):** a farinha vale 100% e o resto é proporcional a ela. Assim, a proporção é a mesma em qualquer tamanho.
- **Cobertura:** cada sabor tem gramas por cm². Com mais de um sabor, cada um cobre uma parte igual da pizza.
- **Medidas caseiras:** volume = gramas ÷ densidade (Anvisa: xícara 200 ml, colher de sopa 10 ml, colher de chá 5 ml). O sistema escolhe a forma mais simples com erro abaixo de 5%; se não houver, marca com ≈. Ingrediente sem densidade oficial fica em gramas.
- **Limites do pedido:** de 1 a 50 pizzas iguais por linha, até 10 linhas, 100 pizzas e 4 sabores por pizza.
- **Registro:** cada receita grava a data/hora, os parâmetros do pedido (quantidade, diâmetro, massa e sabores) e as gramas de cada ingrediente. Assim, `/receita/{id}` remonta qualquer receita antiga.

## Fontes dos dados

| Dado | Onde fica | Fonte |
|---|---|---|
| Xícara, colher de sopa e colher de chá | Banco (`MedidasCaseiras`) | Anvisa, Instrução Normativa nº 75/2020, Anexo VII |
| Densidades (11 ingredientes) | Banco (`Ingredientes`) | FAO/INFOODS Density Database v2.0 (FAO, 2012) |
| Massa Napolitana tradicional | `dados.py` e modo de preparo no banco | Regulamento (UE) nº 97/2010, Anexo II (Pizza Napoletana ETG*) |
| Sabores Margherita (ETG) e Marinara (ETG) | Banco (`Recheios`) | Regulamento (UE) nº 97/2010, Anexo II |
| Demais massas e sabores | `dados.py` (massas) e banco (sabores) | Receitas de referência da equipe |

*ETG = Especialidade Tradicional Garantida: selo da União Europeia que fixa a receita tradicional de um prato.

Os 28 ingredientes sem densidade na base da FAO ficam com `NULL` e aparecem só em gramas.
