# PizZap: documentação da API

API da EAP 1.2.1 e consultas ao banco (EAP 1.6.4). Formato JSON em UTF-8. Cada resposta traz o cabeçalho `X-Tempo-Resposta-ms`. Limite de 100 requisições por minuto por IP (a 101ª recebe `429`).

## Acesso: só a equipe

A API não aparece no site e exige a `CHAVE_API` do `.env`. Sem a chave, todo endereço que começa com `/api` responde `404`, como se não existisse. O site (home, formulário e receita) continua aberto para todos, porque não depende da API.

- **Pelo navegador:** ligue o sistema e abra uma vez **http://127.0.0.1:5000/api?chave=SUA_CHAVE**. A chave fica guardada na sessão até fechar o navegador (ou até clicar em **Sair** na página). Depois disso, os endereços `GET` abrem direto.
- **Por programa:** mande o cabeçalho `X-Chave-API: SUA_CHAVE`.

A página `/api` tem um botão **Enviar** para cada endereço e mostra a resposta embaixo, com o código HTTP.

| Método | Endereço | O que faz |
|---|---|---|
| `POST` | `/api/banco/ingredientes` | Cadastra um ingrediente na tabela `Ingredientes` |
| `POST` | `/api/banco/medidas` | Cadastra uma medida na tabela `MedidasCaseiras` |
| `POST` | `/api/banco/recheios` | Cadastra um sabor com os ingredientes (`Recheios` e `RecheiosXIngredientes`) |
| `POST` | `/api/receitas` | Gera e registra uma receita (EAP 1.2.1) |
| `GET` | `/api/receitas/{id}` | Mostra uma receita gerada |
| `GET` | `/api/opcoes` | Tamanhos, massas, sabores, unidades e limites do formulário |
| `GET` | `/api/status` | Saúde do sistema (EAP 1.5.3) |
| `GET` | `/api/banco/medidas` | Tabela `MedidasCaseiras` |
| `GET` | `/api/banco/ingredientes` | Tabela `Ingredientes` (e `/api/banco/ingredientes/{id}`) |
| `GET` | `/api/banco/templates` | Tabela `TemplatesReceitas` |
| `GET` | `/api/banco/recheios` | Sabores com os ingredientes (e `/api/banco/recheios/{id}`) |
| `GET` | `/api/banco/receitas` | Últimas receitas de `Receitas_Geradas` (`?limite=20`) |
| `GET` | `/api/banco/receitas/{id}` | Parâmetros e ingredientes usados numa receita |

As rotas `/api/banco` precisam de `USAR_MYSQL = True`; sem banco, respondem `503`. Para corrigir ou apagar um cadastro, use o MySQL Workbench e reinicie o servidor.

---

## POST /api/banco/ingredientes

```json
{"ingrediente": "Atum em lata", "densidade": null}
```

- `ingrediente`: obrigatório, até 80 caracteres, sem repetir.
- `densidade`: em g/ml, opcional. Com `null`, o ingrediente aparece só em gramas.
- **201:** `{"id": 40, "ingrediente": "Atum em lata", "densidade_g_ml": null}`
- **400:** `{"erro": "Dados inválidos.", "campos": {"densidade": "Informe um número maior que 0 (g/ml) ou null."}}`
- **409:** nome já cadastrado.

O ingrediente novo fica no banco e aparece em `/api/banco/ingredientes`. Para usá-lo numa pizza, cadastre um sabor com ele (abaixo).

## POST /api/banco/recheios

```json
{
  "recheio": "Atum",
  "descricao": "Molho de tomate, atum, cebola e mussarela.",
  "doce": false,
  "ingredientes": [
    {"id_ingrediente": 9,  "gramas_por_cm2": 0.08},
    {"id_ingrediente": 40, "gramas_por_cm2": 0.10},
    {"id_ingrediente": 17, "gramas_por_cm2": 0.04}
  ]
}
```

- `recheio` (até 60 caracteres, sem repetir) e `descricao` (até 255): obrigatórios. `doce`: opcional (padrão `false`).
- `ingredientes`: pelo menos um. `id_ingrediente` vem de `/api/banco/ingredientes` (vale o que foi cadastrado pela API). `gramas_por_cm2` é quanto vai por cm² de pizza; referência: molho 0,08, mussarela 0,1 a 0,2, orégano 0,002.
- **201:** o sabor criado, com a lista de ingredientes. Ele já aparece no formulário, sem reiniciar.
- **400:** campo errado, ou `id_ingrediente` que não existe. **409:** nome já cadastrado.
- Sabor e ingredientes são gravados juntos: se algo falhar, nada fica pela metade.

## POST /api/banco/medidas

```json
{"medida_caseira": "colher de sobremesa", "volume": 7.5}
```

- `medida_caseira`: obrigatório, até 40 caracteres, sem repetir.
- `volume`: em ml, maior que 0.
- **201:** `{"id": 4, "medida_caseira": "colher de sobremesa", "volume_ml": 7.5}`
- **400** com o campo errado, ou **409** se o nome já existe.

A medida nova já entra na conversão das receitas, sem reiniciar. O plural é feito sozinho ("colheres de sobremesa").

---

## POST /api/receitas

Recebe o pedido, valida, calcula e registra a receita. A gravação no MySQL acontece em segundo plano, então a resposta não espera o banco.

```json
{
  "unidade": "ambas",
  "pizzas": [
    {"quantidade": 2, "diametro_cm": 35, "tipo_massa_id": 1, "recheio_ids": [1, 2]}
  ]
}
```

| Campo | Regra |
|---|---|
| `unidade` | `gramas`, `quilogramas`, `caseira` (xícaras e colheres) ou `ambas` |
| `pizzas` | De 1 a 10 linhas; no máximo 100 pizzas no total |
| `pizzas[].quantidade` | Inteiro de 1 a 50 (pode vir como texto só com dígitos, ex.: `"2"`) |
| `pizzas[].diametro_cm` | 25 (Broto), 30 (Média), 35 (Grande) ou 40 (Gigante) |
| `pizzas[].tipo_massa_id` | 1 Tradicional, 2 Napolitana tradicional, 3 Fina e crocante, 4 Massa grossa, 5 Integral |
| `pizzas[].recheio_ids` | De 1 a 4 sabores diferentes (ids em `/api/opcoes` ou `/api/banco/recheios`) |

Também aceita o formulário da tela (`pizzas[0][quantidade]=2` etc.), porque os nomes dos campos são os mesmos (EAP 1.1.2).

**Resposta 200** (resumida):

```json
{
  "unidade": "ambas",
  "parametros": {"unidade": "ambas", "pizzas": [{"quantidade": 2, "diametro_cm": 35, "tipo_massa_id": 1, "recheio_ids": [1, 2]}]},
  "resumo": {"total_pizzas": 2, "massa_total_g": 692},
  "pizzas": [{
    "quantidade": 2, "diametro_cm": 35, "tamanho": "Grande", "tipo_massa": "Tradicional",
    "recheios": ["Mussarela", "Calabresa"], "peso_massa_g": 346,
    "massa": [{"ingrediente_id": 1, "ingrediente": "Farinha de trigo tipo 1",
               "por_pizza": {"gramas": 206.17, "texto": "206 g", "caseira": "2 xícaras de chá", "aproximado": false},
               "total":     {"gramas": 412.33, "texto": "412 g", "caseira": "4 xícaras de chá", "aproximado": false}}],
    "cobertura": ["..."]
  }],
  "lista_de_compras": ["..."],
  "modo_de_preparo": ["..."],
  "montagem": ["..."],
  "id": 1,
  "criado_em": "2026-11-17T09:50:17"
}
```

- `caseira` é `null` para ingrediente sem densidade oficial (ex.: calabresa).
- `aproximado: true` indica medida caseira com diferença de 5% ou mais; na tela aparece com `≈`.

**Resposta 400** (indica cada campo errado):

```json
{"erro": "Dados inválidos.",
 "campos": {"pizzas[0].quantidade": "A quantidade deve ser um número inteiro maior que zero.",
            "pizzas[0].diametro_cm": "Escolha um tamanho válido.",
            "pizzas[0].recheio_ids": "Escolha pelo menos um recheio."}}
```

Valor que não é número (ex.: `"abc"`, `"²"`) também responde `400`, com o campo indicado.

## GET /api/receitas/{id}

Devolve a receita no mesmo formato do `POST`. Se o servidor foi reiniciado, a receita é remontada com os parâmetros gravados no banco e vem com `"reconstruida": true`. Receita inexistente: `404`.

## GET /api/banco/...

- `/api/banco/medidas`
  ```json
  {"total": 3, "itens": [{"id": 1, "medida_caseira": "xícara de chá", "volume_ml": 200.0},
                         {"id": 2, "medida_caseira": "colher de sopa", "volume_ml": 10.0},
                         {"id": 3, "medida_caseira": "colher de chá", "volume_ml": 5.0}]}
  ```
- `/api/banco/ingredientes/1`: `{"id": 1, "ingrediente": "Farinha de trigo tipo 1", "densidade_g_ml": 0.521}`
- `/api/banco/templates`: `{"total": 5, "itens": [{"id": 2, "tipo_massa": "Napolitana tradicional", "modo_de_preparo": ["Coloque a água na masseira...", "..."]}]}`
- `/api/banco/receitas?limite=20`: `{"total": 1, "itens": [{"id": 1, "timestamp": "2026-11-17T09:50:17", "unidade": "ambas", "total_pizzas": 3}]}`
- `/api/banco/receitas/1`
  ```json
  {"id": 1, "timestamp": "2026-11-17T09:50:17",
   "parametros": {"unidade": "ambas", "pizzas": [{"quantidade": 2, "diametro_cm": 35, "tipo_massa_id": 2, "recheio_ids": [3, 11]}]},
   "ingredientes_usados": [{"id_ingrediente": 1, "ingrediente": "Farinha de trigo tipo 1", "gramas": 420.54}, "..."]}
  ```

## GET /api/status

```json
{"status": "ok", "uptime_segundos": 97, "requisicoes": 35, "tempo_medio_ms": 1.3, "erros_5xx": 0,
 "bloqueadas_429": 0, "banco": "conectado",
 "gravacao_receitas": {"pendentes": 0, "gravadas": 12, "falhas": 0, "ultimo_lote_ms": 8.0, "media_por_lote_ms": 8.0}}
```

Se o MySQL estiver fora, responde `503` com `"status": "degradado"`. `requisicoes` e `tempo_medio_ms` contam todas as requisições do servidor, inclusive as do próprio `/api/status`.

---

## Códigos de resposta

| Código | Quando |
|---|---|
| `200` | Deu certo |
| `201` | Cadastro feito |
| `400` | Dados inválidos (a resposta diz qual campo) |
| `404` | Receita, ingrediente ou endereço inexistente, ou acesso sem a chave da API (inclusive chave errada) |
| `405` | Método não aceito no endereço (ex.: `POST` numa rota de consulta) |
| `409` | Nome já cadastrado |
| `429` | Mais de 100 requisições no minuto (mesmo IP) |
| `500` | Erro inesperado (registrado em `logs/pizzap.log`) |
| `503` | MySQL fora do ar, senha errada ou `USAR_MYSQL = False` nas rotas `/api/banco` |
