# PizZap: dicionário de dados (MySQL)

Banco criado por `database/schema.sql`: as 5 tabelas da EAP 1.4.1 e mais 2 para os sabores (EAP 1.6.4).

- **Banco:** `pizzap` · **SGBD:** MySQL 8.0 ou superior · **Motor:** InnoDB · **Codificação:** utf8mb4
- **Normalização:** 3FN nas tabelas principais.

## Quem guarda o quê

| Onde | O que tem |
|---|---|
| **MySQL** | Medidas caseiras, ingredientes com densidade, modo de preparo de cada massa, sabores com os ingredientes e o registro de cada receita gerada |
| **`dados.py`** | Tamanhos, proporções das massas e limites do pedido (os "objetos de proporções" da EAP 1.2.2), ligados ao banco pelos mesmos ids. Também tem uma cópia dos dados iniciais do banco, usada só sem MySQL |

```
Receitas_Geradas (1) ──< ReceitasXIngredientes >── (1) Ingredientes
Recheios         (1) ──< RecheiosXIngredientes >── (1) Ingredientes
MedidasCaseiras e TemplatesReceitas: tabelas de consulta, sem chave estrangeira
```

---

## MedidasCaseiras

Medidas usadas na conversão para xícaras e colheres (EAP 1.2.3).

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `id` | INT UNSIGNED | não | Chave primária (AUTO_INCREMENT) |
| `medida_caseira` | VARCHAR(40) | não | Nome, ex.: `xícara de chá` |
| `volume` | DECIMAL(6,2) | não | Volume em mililitros |

- **Chaves e índices:** PK `id`; único `uq_medida_caseira`
- **Regra:** `ck_volume_positivo` (volume > 0)
- **Dados (Anvisa, IN 75/2020, Anexo VII):** xícara de chá 200 ml · colher de sopa 10 ml · colher de chá 5 ml

## Ingredientes

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `id` | INT UNSIGNED | não | Chave primária |
| `ingrediente` | VARCHAR(80) | não | Nome |
| `densidade` | DECIMAL(5,3) | sim | Gramas por mililitro. `NULL` = sem valor em fonte oficial (o ingrediente aparece só em gramas) |

- **Chaves e índices:** PK `id`; único `uq_ingrediente`
- **Regra:** `ck_densidade_positiva` (nula ou > 0)
- **Dados:** 39 ingredientes. 11 têm densidade da **FAO/INFOODS Density Database v2.0**: farinha de trigo 0,521 · farinha integral 0,55 · água 1,0 · sal 1,217 · fermento seco 0,95 · açúcar 0,88 · azeite 0,918 · ovo cozido 0,6 · ervilha 0,73 · milho 0,73 · canela 0,56 g/ml. Os outros 28 (queijos, frios, molhos, folhas etc.) não têm valor nessa base e ficam com `NULL`, em vez de um valor inventado.

## TemplatesReceitas

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `id` | INT UNSIGNED | não | Chave primária. É o mesmo id do tipo de massa em `dados.py` |
| `modo_de_preparo` | TEXT | não | Passos, um por linha |

- **Dados:** 1 Tradicional · 2 Napolitana tradicional · 3 Fina e crocante · 4 Massa grossa · 5 Integral. A Napolitana segue o Regulamento (UE) nº 97/2010; as outras são receitas de referência da equipe (não existe norma oficial para elas).

## Recheios

Sabores. Novos sabores podem ser cadastrados por `POST /api/banco/recheios`.

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `id` | INT UNSIGNED | não | Chave primária. É o `recheio_ids` do pedido |
| `recheio` | VARCHAR(60) | não | Nome do sabor |
| `descricao` | VARCHAR(255) | não | Texto curto mostrado no formulário |
| `doce` | BOOLEAN | não | Separa salgadas e doces no formulário (padrão FALSE) |

- **Chaves e índices:** PK `id`; único `uq_recheio`
- **Dados:** 11 sabores. Margherita (ETG) e Marinara (ETG) seguem o Regulamento (UE) nº 97/2010; os outros são receitas da equipe.

## RecheiosXIngredientes

Ingredientes de cada sabor, em gramas por cm² de pizza. Com mais de um sabor, cada um cobre uma parte igual da pizza.

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `id` | INT UNSIGNED | não | Chave primária (também define a ordem dos ingredientes) |
| `id_recheio` | INT UNSIGNED | não | FK para `Recheios.id` (`ON DELETE CASCADE`) |
| `id_ingrediente` | INT UNSIGNED | não | FK para `Ingredientes.id` (`ON DELETE RESTRICT`) |
| `gramas_por_cm2` | DECIMAL(7,4) | não | Gramas por cm² de pizza |

- **Chaves e índices:** PK `id`; único `uq_recheio_ingrediente` (`id_recheio`, `id_ingrediente`); `idx_rxing_ingrediente`
- **Regra:** `ck_gramas_positivo` (> 0)
- Um ingrediente usado em algum sabor não pode ser apagado (RESTRICT). Apagar um sabor apaga, em cascata, a lista de ingredientes dele.

## Receitas_Geradas (EAP 1.2.4)

Uma linha para cada receita gerada.

| Coluna | Tipo | Nulo | Padrão | Descrição |
|---|---|---|---|---|
| `id` | INT UNSIGNED | não | AUTO_INCREMENT | Chave primária. É o número que aparece na tela (`/receita/{id}`) |
| `timestamp` | DATETIME | não | CURRENT_TIMESTAMP | Data e hora |
| `parametros` | JSON | não | | Parâmetros do pedido, no mesmo formato do JSON da API |

Exemplo de `parametros` (2 pizzas Grandes, massa Tradicional, meio Mussarela e meio Calabresa):

```json
{"unidade": "ambas", "pizzas": [{"quantidade": 2, "diametro_cm": 35, "tipo_massa_id": 1, "recheio_ids": [1, 2]}]}
```

- **Chaves e índices:** PK `id`; `idx_receitas_timestamp` (consultas por período)
- **Por que a coluna `parametros`:** a EAP 1.2.4 pede registrar "timestamp, parâmetros de entrada e receita resultante". Os parâmetros ficam nesta coluna e a receita resultante em `ReceitasXIngredientes`. Com isso, qualquer receita antiga pode ser remontada em `/receita/{id}`, mesmo depois de reiniciar o servidor.
- **Decisão de simplicidade:** um pedido pode ter várias pizzas, cada uma com vários sabores. Guardar isso em JSON evita mais 2 tabelas só para o registro.

## ReceitasXIngredientes

Quanto de cada ingrediente cada receita usou (total de todas as pizzas do pedido).

| Coluna | Tipo | Nulo | Descrição |
|---|---|---|---|
| `id` | INT UNSIGNED | não | Chave primária |
| `id_receita_gerada` | INT UNSIGNED | não | FK para `Receitas_Geradas.id` (`ON DELETE CASCADE`) |
| `id_ingrediente` | INT UNSIGNED | não | FK para `Ingredientes.id` (`ON DELETE RESTRICT`) |
| `quantidade_usada_gramas` | DECIMAL(10,2) | não | Quantidade total em gramas |

- **Chaves e índices:** PK `id`; único `uq_receita_ingrediente` (`id_receita_gerada`, `id_ingrediente`); `idx_rxi_ingrediente`
- **Regra:** `ck_quantidade_positiva`
- Apagar uma receita gerada apaga, em cascata, as linhas dela. Um ingrediente usado em alguma receita não pode ser apagado (RESTRICT).

---

## Fontes dos dados

| Dado | Fonte |
|---|---|
| Volume das medidas caseiras | Anvisa, Instrução Normativa nº 75/2020, Anexo VII |
| Densidade dos ingredientes | FAO/INFOODS Density Database v2.0 (FAO, 2012) |
| Massa Napolitana tradicional (Pizza Napoletana ETG*): 1 l de água para 1,8 kg de farinha, 50-55 g de sal, 3 g de fermento; bolinha de até 250 g para pizza de até 35 cm | Regulamento (UE) nº 97/2010, Anexo II (Pizza Napoletana ETG) |
| Margherita (ETG): 60-80 g de tomate, 80-100 g de mussarela e 4-5 g de azeite por pizza. Marinara (ETG): 70-100 g de tomate e 4-5 g de azeite (tabela `Recheios`) | Regulamento (UE) nº 97/2010, Anexo II |
| Demais massas (`dados.py`) e sabores (`Recheios`) | Receitas de referência da equipe |

*ETG = Especialidade Tradicional Garantida: selo da União Europeia que fixa a receita tradicional de um prato.
