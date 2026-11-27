# PizZap: manual básico de operação

Instalar, ligar, monitorar e testar o sistema (EAP 1.5.1, 1.5.3 e 1.6.4). Tudo roda numa única máquina (localhost), a apresentação é local, sem implantação em URL pública.

## 1. Instalação (primeira vez)

Precisa de **Python 3.9 ou mais novo** e do **MySQL 8.0** instalado e ligado.

1. Abra a pasta `pizzap` no VS Code e abra o terminal.
2. Crie o ambiente virtual:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   # source .venv/bin/activate     # Linux / macOS
   ```
3. Copie `.env.exemplo` para `.env` e preencha os valores reais. O `.env` não vai para o GitHub (`.gitignore`); o `config.py` lê os valores dele. No `config.py` fica só `USAR_MYSQL = True`. No `.env`:
   - `MYSQL_HOST`, `MYSQL_PORT`, `MYSQL_USER` e `MYSQL_PASSWORD` do seu MySQL.
   - `SECRET_KEY`: texto longo e aleatório. Ela assina o cookie de acesso à API e é misturada ao IP antes do hash. Gere uma com `python -c "import secrets; print(secrets.token_hex(32))"`.
   - `CHAVE_API`: a senha da equipe para abrir `/api?chave=...`. O monitor e o teste de carga a leem do `config.py` e a enviam sozinhos.
4. Ligue o sistema (próxima seção). Na primeira vez, o `iniciar.py` instala as dependências e cria o banco sozinho.

**Banco criado com uma versão anterior?** O `iniciar.py` percebe e pergunta se pode recriar (digite `SIM`). Isso apaga só as receitas de teste já registradas. Também dá para rodar o `database/schema.sql` inteiro no Workbench.

## 2. Ligar e desligar

| Comando | Para quê |
|---|---|
| `python iniciar.py` | **Uso normal.** Instala o que faltar, cria o banco se ele não existir e liga o servidor (Waitress) em http://127.0.0.1:5000 |
| `python iniciar.py --rede` | O mesmo, aceitando acesso de outras máquinas da rede |
| `python iniciar.py --porta 8000` | Usa outra porta |
| `python iniciar.py --recriar-banco` | Roda o `schema.sql` de novo. **Apaga todas as receitas registradas** e pede confirmação |
| `python iniciar.py --sem-limite` | Desliga o rate limit. **Só para o teste de carga** |
| `python app.py` | Modo de desenvolvimento: recarrega ao salvar o código e mostra os erros detalhados |

**Para desligar:** Ctrl+C no terminal. As receitas que ainda estiverem na fila de gravação são salvas antes de o servidor fechar.

Ao ligar, o terminal mostra os 3 passos (dependências, banco, servidor) e o tempo total. Na medição feita, com as dependências já instaladas, isso levou menos de 1 segundo. A EAP 1.5.1 aceita até 5 minutos.

**Antes de apresentar:** abra o site e gere uma receita uma vez. As primeiras requisições são as mais lentas (no ensaio, a primeira geração levou 444 ms; a mediana ficou em 24 ms).

## 3. Monitoramento (EAP 1.5.3)

| O quê | Onde |
|---|---|
| Saúde do sistema (uptime, requisições, tempo médio, erros, banco, fila de gravação, CPU e memória) | http://127.0.0.1:5000/api/status |
| Últimas receitas gravadas no banco | http://127.0.0.1:5000/api/banco/receitas |
| Log de cada requisição (método, caminho, status e tempo) e dos erros | `logs/pizzap.log` |
| Verificação a cada minuto, gravada em planilha | `python ferramentas/monitorar.py` → `ferramentas/monitoramento.csv` |

Os endereços `/api/...` exigem a `CHAVE_API`: abra uma vez `http://127.0.0.1:5000/api?chave=SUA_CHAVE` (a chave fica guardada até fechar o navegador).

- **Logs rotativos:** quando `pizzap.log` passa de 1 MB, ele vira `pizzap.log.1`, e assim até `pizzap.log.5`; o mais antigo é apagado. Requisições acima de 250 ms e erros 5xx entram como `WARNING`.

### Verificação de estabilidade

Com o servidor ligado, rode em outro terminal:

```bash
python ferramentas/monitorar.py --horas 0.34                  # 20 minutos (sem --horas, o padrão é 48 horas)
python ferramentas/monitorar.py --horas 0.1 --intervalo 5     # demonstração rápida: 6 minutos, uma verificação a cada 5 s
```

- O monitor lê a `CHAVE_API` do `config.py` e a envia sozinho. Se a chave não bater (resposta 404), ele para na hora com uma mensagem, em vez de gravar dados vazios.
- Conta como **queda** qualquer verificação sem resposta ou um reinício do servidor (o tempo ligado diminui). No fim, mostra o resumo: verificações, quedas e disponibilidade.
- O CSV abre no Excel (separador `;`). O computador não pode hibernar e o terminal precisa ficar aberto.
- `requisicoes` e `tempo_medio_ms` do `/api/status` contam todas as requisições do servidor, inclusive as do próprio monitor (cada uma leva cerca de 50 ms, porque abre uma conexão com o banco). Para medir desempenho, use o teste de carga (seção 4).

### Resultado do monitoramento (21/11/2026)

| Item | Resultado |
|---|---|
| Duração | 20 minutos (18:11 às 18:31), uma verificação por minuto |
| Verificações / quedas | 21 / **0** (disponibilidade **100%**) |
| Erros 5xx | 0 |
| Banco | conectado em todas as verificações |
| Tempo ligado | contínuo, sem reinício (1.279 s na última verificação) |
| Memória do processo | 47,8 a 49,7 MB (estável) |
| CPU da máquina | 0% a 19,6% (os picos coincidem com o uso do site) |

A meta da Sprint 3 (RN14) era de 2 dias sem queda. Para a apresentação local, a equipe adotou 20 minutos. Os 2 dias seguidos ficam como critério para uma aplicação real futura (basta rodar com `--horas 48`).

## 4. Teste de carga (EAP 1.5.3 e RNF07)

O roteiro está no topo de `ferramentas/locustfile.py`. Cada usuário virtual abre a home e o formulário e gera receitas com pedidos sorteados (1 a 3 tipos de pizza e 1 a 4 sabores); depois de gerar, abre a tela da receita. Ele espera de 1 a 3 segundos entre uma ação e outra e envia a `CHAVE_API` lida do `config.py`. O rate limit é desligado no teste porque todas as requisições saem do mesmo IP; ele é testado à parte, nos testes automáticos.

```bash
pip install locust                       # só na primeira vez
python iniciar.py --sem-limite           # terminal 1: servidor sem rate limit

# terminal 2 (-u usuários, -r quantos entram por segundo, -t duração)
python -m locust -f ferramentas/locustfile.py --host http://127.0.0.1:5000 --headless -u 1   -r 1  -t 2m --csv ferramentas/carga_base
python -m locust -f ferramentas/locustfile.py --host http://127.0.0.1:5000 --headless -u 50  -r 10 -t 2m --csv ferramentas/carga_50
python -m locust -f ferramentas/locustfile.py --host http://127.0.0.1:5000 --headless -u 100 -r 20 -t 2m --csv ferramentas/carga_100
```

Depois do teste, desligue o servidor, rode `python iniciar.py --recriar-banco` (apaga as receitas de teste) e ligue de novo **sem** `--sem-limite`. Dos arquivos gerados, os `*_stats.csv` são a evidência (já estão no `.gitignore`).

### Resultado (21/11/2026)

Servidor (Waitress, sem modo debug, com MySQL) e Locust na **mesma máquina** (Windows, Python 3.12), então o Locust disputa CPU com o PizZap. Cada cenário durou 2 minutos.

Todas as requisições (home, formulário, gerar receita e ver a receita):

| Cenário | Requisições | Falhas | Média | Mediana | 95% abaixo de | Requisições/s |
|---|---|---|---|---|---|---|
| Base (1 usuário) | 65 | 0 | 37 ms | 25 ms | 78 ms | 0,8 |
| 50 usuários | 4.320 | 0 | 99 ms | 52 ms | 400 ms | 36,6 |
| 100 usuários | 7.523 | 0 | 300 ms | 130 ms | 1.200 ms | 63,4 |

Só `POST /api/receitas` (gerar a receita):

| Cenário | Requisições | Falhas | Média | Mediana | 95% abaixo de | Máximo |
|---|---|---|---|---|---|---|
| Base (1 usuário) | 24 | 0 | 45 ms | 24 ms | 68 ms | 444 ms |
| 50 usuários | 1.615 | 0 | 109 ms | 58 ms | 430 ms | 1.117 ms |
| 100 usuários | 2.829 | 0 | 309 ms | 140 ms | 1.200 ms | 2.977 ms |

**Como ler:**

- **Disponibilidade:** nenhuma falha em 11.908 requisições, até 100 usuários simultâneos.
- **Tempo de resposta (RNF03, menos de 250 ms em condições normais):** atendido com 1 usuário (média de 45 ms) e com 50 (média de 109 ms). Com 100 usuários, a mediana (140 ms) fica abaixo de 250 ms, mas a média (309 ms) e os 5% mais lentos passam.
- **Degradação sobre a base (RNF07 original, no máximo 50%):** não foi atingida. Com 50 usuários o tempo médio foi 2,7 vezes o da base (99 ms contra 37 ms) e com 100 usuários, 8,1 vezes.
- **Por que o tempo sobe:** de 50 para 100 usuários, a vazão só aumentou 1,7 vez (de 36,6 para 63,4 requisições por segundo), mas o tempo médio triplicou. O servidor chegou perto do limite e as requisições passaram a esperar na fila, provavelmente por CPU, já que ele roda em um único processo Python e divide a máquina com o Locust.
- **Ressalvas:** a base é curta (65 requisições) e a primeira geração, mais lenta, puxa a média para cima. Os usuários simulados trocam de ação a cada 1 a 3 segundos, o que é bem mais intenso do que a apresentação real.

### Critérios adotados

| | Escala local (apresentação) | Aplicação real futura |
|---|---|---|
| Usuários simultâneos | até 100 | 1.000 |
| Falhas | nenhuma | nenhuma (nem erro 5xx) |
| Tempo | mediana de gerar a receita abaixo de 250 ms | tempo médio até 50% acima da base (ex.: de 200 ms para 300 ms) |
| Estabilidade | 20 minutos sem queda | 2 dias sem queda |
| Situação | **Atendido** | Meta futura: exige servidor dedicado e a carga gerada de outra máquina |

## 5. Testes automáticos

```bash
python -m pytest -v
python -m pytest --cov=receita --cov-report=term-missing     # cobertura (precisa de: pip install pytest-cov)
```

| Arquivo | O que testa | Precisa do MySQL |
|---|---|---|
| `tests/test_pizzap.py` | Cálculo, conversão de medidas, validação, respostas da API, rate limit, chave da API e telas | Não |
| `tests/test_entradas_invalidas.py` | Entradas estranhas (números como `"²"`, chave com acento) devem dar 400 ou 404, nunca 500 | Não |
| `tests/test_mysql.py` | Ligação com o banco, gravação das receitas e erro amigável com senha errada | Sim |
| `tests/test_api_banco.py` | Cadastros e consultas da API `/api/banco` | Sim |

**Resultado atual:** 186 passaram e 1 foi pulado, com **100% de cobertura** de `receita.py` (156 linhas). O teste pulado é intencional: o peso de 12 g com densidade 1,217 dá menos de 1 colher de sopa, e o próprio teste ignora esse caso. Nenhum teste de banco foi pulado.

Os testes de banco usam o MySQL real do `config.py`: o `test_api_banco.py` apaga o que cadastra (nomes que começam com "TESTE"), mas o `test_mysql.py` deixa algumas receitas de teste gravadas. Antes da apresentação, rode `python iniciar.py --recriar-banco` para começar com o banco limpo.

## 6. Backup e restauração do banco

```bash
mysqldump -u SEU_USUARIO -p pizzap > backup_pizzap.sql   # backup
mysql -u SEU_USUARIO -p pizzap < backup_pizzap.sql       # restauração
```

No MySQL Workbench, o mesmo é feito em *Server → Data Export* e *Data Import*.

## 7. Problemas comuns

| Sintoma | Causa provável | Solução |
|---|---|---|
| O terminal diz "Rodando sem banco" ou "USAR_MYSQL = False" | O MySQL está desligado no `config.py` | `USAR_MYSQL = True` e reinicie |
| "O banco 'pizzap' foi criado com outra versão do schema.sql" | O banco é de uma versão anterior | `python iniciar.py --recriar-banco` (digite SIM) |
| "ERRO: não conectou ao MySQL" ou página 503 | MySQL parado, senha ou porta errada | Ligue o MySQL e confira os dados com *Test Connection* no Workbench |
| Erro com `caching_sha2_password` | Falta um pacote para o login do MySQL 8 | `pip install cryptography` |
| Mudei dados direto no Workbench e nada mudou | Medidas, ingredientes e modos de preparo são lidos uma vez, ao ligar | Reinicie o servidor |
| Página "Muitas requisições" (429) | Mais de 100 acessos por minuto do mesmo computador | Espere 1 minuto |
| `pip` não instala na máquina da faculdade | Falta de permissão | Use o ambiente virtual (`.venv`) do passo 2 da instalação |
| Porta 5000 ocupada | Outro programa usa a porta | `python iniciar.py --porta 8000` |
| O monitor para com "o servidor respondeu 404" | A `CHAVE_API` do `.env` não é a do servidor que está ligado | Reinicie o servidor depois de mudar o `.env` e rode o monitor de novo |
| O teste de carga mostra muitas falhas 429 | O servidor foi ligado sem `--sem-limite` | Desligue e rode `python iniciar.py --sem-limite` |
| O teste de carga mostra falhas 404 em `/api/receitas` | A `CHAVE_API` do `.env` mudou depois que o servidor ligou | Reinicie o servidor e rode o teste de novo |
