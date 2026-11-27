-- =====================================================================
-- PizZap - Banco de dados MySQL (EAP 1.4.1 - Schema Principal)
--
-- Como usar: abra este arquivo no MySQL Workbench e execute tudo
-- (raio, Ctrl+Shift+Enter), ou rode  python iniciar.py --recriar-banco
-- ATENÇÃO: apaga e recria o banco "pizzap".
--
-- Tabelas (as 5 da EAP 1.4.1 + 2 dos sabores):
--   MedidasCaseiras        medidas usadas na conversão (xícara, colheres)
--   Ingredientes           ingredientes e densidade (g/ml)
--   TemplatesReceitas      modo de preparo de cada tipo de massa
--   Recheios               sabores
--   RecheiosXIngredientes  gramas por cm² de cada ingrediente de cada sabor
--   Receitas_Geradas       cada receita gerada (EAP 1.2.4): data/hora e os
--                          parâmetros do pedido (quantidade, diâmetro, massa
--                          e sabores de cada pizza)
--   ReceitasXIngredientes  quanto de cada ingrediente cada receita usou
--
--   Receitas_Geradas 1 ──── N ReceitasXIngredientes N ──── 1 Ingredientes
--   Recheios         1 ──── N RecheiosXIngredientes N ──── 1 Ingredientes
--
-- Tamanhos e proporções das massas ficam em dados.py (mesmos ids).
--
-- Fontes dos dados:
--   Medidas caseiras: Anvisa, Instrução Normativa nº 75/2020, Anexo VII.
--   Densidades: FAO/INFOODS Density Database v2.0 (FAO, 2012). Ingrediente
--     sem valor nessa base fica com densidade NULL (aparece só em gramas).
--   Massa Napolitana tradicional e sabores Margherita (ETG) e Marinara (ETG):
--     Regulamento (UE) nº 97/2010, Anexo II (Pizza Napoletana ETG).
--   Demais massas e sabores: receitas de referência da equipe (sem norma oficial).
-- =====================================================================

SET NAMES utf8mb4;

DROP DATABASE IF EXISTS pizzap;
CREATE DATABASE pizzap CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE pizzap;

-- ---------------------------------------------------------------------
-- Tabelas de referência
-- ---------------------------------------------------------------------
CREATE TABLE MedidasCaseiras (
  id             INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  medida_caseira VARCHAR(40)   NOT NULL,             -- ex.: 'xícara de chá'
  volume         DECIMAL(6,2)  NOT NULL,             -- em mililitros
  PRIMARY KEY (id),
  UNIQUE KEY uq_medida_caseira (medida_caseira),
  CONSTRAINT ck_volume_positivo CHECK (volume > 0)
) ENGINE=InnoDB;

CREATE TABLE Ingredientes (
  id          INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  ingrediente VARCHAR(80)   NOT NULL,
  densidade   DECIMAL(5,3)  NULL,                    -- g/ml; NULL = sem medida caseira
  PRIMARY KEY (id),
  UNIQUE KEY uq_ingrediente (ingrediente),           -- também acelera a busca por nome
  CONSTRAINT ck_densidade_positiva CHECK (densidade IS NULL OR densidade > 0)
) ENGINE=InnoDB;

CREATE TABLE TemplatesReceitas (
  id              INT UNSIGNED NOT NULL AUTO_INCREMENT,  -- mesmo id do tipo de massa (dados.py)
  modo_de_preparo TEXT         NOT NULL,                 -- um passo por linha
  PRIMARY KEY (id)
) ENGINE=InnoDB;

-- Sabores: um sabor tem vários ingredientes, cada um em gramas por cm² de pizza
CREATE TABLE Recheios (
  id        INT UNSIGNED NOT NULL AUTO_INCREMENT,    -- é o recheio_ids do pedido
  recheio   VARCHAR(60)  NOT NULL,
  descricao VARCHAR(255) NOT NULL,                   -- texto curto do formulário
  doce      BOOLEAN      NOT NULL DEFAULT FALSE,     -- separa salgadas e doces
  PRIMARY KEY (id),
  UNIQUE KEY uq_recheio (recheio)
) ENGINE=InnoDB;

CREATE TABLE RecheiosXIngredientes (
  id             INT UNSIGNED NOT NULL AUTO_INCREMENT,
  id_recheio     INT UNSIGNED NOT NULL,
  id_ingrediente INT UNSIGNED NOT NULL,
  gramas_por_cm2 DECIMAL(7,4) NOT NULL,              -- gramas por cm² de pizza
  PRIMARY KEY (id),
  UNIQUE KEY uq_recheio_ingrediente (id_recheio, id_ingrediente),
  KEY idx_rxing_ingrediente (id_ingrediente),
  CONSTRAINT fk_rxing_recheio FOREIGN KEY (id_recheio)
    REFERENCES Recheios (id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_rxing_ingrediente FOREIGN KEY (id_ingrediente)
    REFERENCES Ingredientes (id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT ck_gramas_positivo CHECK (gramas_por_cm2 > 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Registro das receitas geradas (EAP 1.2.4: timestamp, parâmetros de
-- entrada e receita resultante)
-- ---------------------------------------------------------------------
CREATE TABLE Receitas_Geradas (
  id          INT UNSIGNED NOT NULL AUTO_INCREMENT,
  `timestamp` DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
  -- parâmetros do pedido, no mesmo formato do JSON da API, ex.:
  -- {"unidade": "ambas", "pizzas": [{"quantidade": 2, "diametro_cm": 35,
  --   "tipo_massa_id": 1, "recheio_ids": [1, 2]}]}
  parametros  JSON         NOT NULL,
  PRIMARY KEY (id),
  KEY idx_receitas_timestamp (`timestamp`)          -- consultas por período
) ENGINE=InnoDB;

CREATE TABLE ReceitasXIngredientes (
  id                      INT UNSIGNED  NOT NULL AUTO_INCREMENT,
  id_receita_gerada       INT UNSIGNED  NOT NULL,
  id_ingrediente          INT UNSIGNED  NOT NULL,
  quantidade_usada_gramas DECIMAL(10,2) NOT NULL,
  PRIMARY KEY (id),
  -- um ingrediente aparece uma vez por receita; o índice também serve
  -- para buscar todos os ingredientes de uma receita
  UNIQUE KEY uq_receita_ingrediente (id_receita_gerada, id_ingrediente),
  -- consultas por ingrediente (ex.: quanto de mussarela foi usado no mês)
  KEY idx_rxi_ingrediente (id_ingrediente),
  CONSTRAINT fk_rxi_receita_gerada FOREIGN KEY (id_receita_gerada)
    REFERENCES Receitas_Geradas (id) ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_rxi_ingrediente FOREIGN KEY (id_ingrediente)
    REFERENCES Ingredientes (id) ON DELETE RESTRICT ON UPDATE CASCADE,
  CONSTRAINT ck_quantidade_positiva CHECK (quantidade_usada_gramas > 0)
) ENGINE=InnoDB;

-- ---------------------------------------------------------------------
-- Dados iniciais (os mesmos de dados.py, com os mesmos ids)
-- ---------------------------------------------------------------------

-- Anvisa, Instrução Normativa nº 75/2020, Anexo VII
INSERT INTO MedidasCaseiras (id, medida_caseira, volume) VALUES
  (1, 'xícara de chá', 200.00),
  (2, 'colher de sopa', 10.00),
  (3, 'colher de chá', 5.00);

-- Densidade: FAO/INFOODS Density Database v2.0 (nome na base entre parênteses).
-- NULL = a base não tem o ingrediente: ele aparece só em gramas.
INSERT INTO Ingredientes (id, ingrediente, densidade) VALUES
  (1, 'Farinha de trigo tipo 1', 0.521),  -- FAO: Wheat, flour
  (2, 'Farinha de trigo integral', 0.550),  -- FAO: Wheat, flour, wholemeal
  (3, 'Água', 1.000),  -- FAO: Water
  (4, 'Sal refinado', 1.217),  -- FAO: Salt, table
  (5, 'Fermento biológico seco', 0.950),  -- FAO: Yeast
  (6, 'Açúcar', 0.880),  -- FAO: Sugar, white
  (7, 'Azeite de oliva', 0.918),  -- FAO: Oil, vegetable, olive
  (8, 'Mel', NULL),
  (9, 'Molho de tomate', NULL),
  (10, 'Leite condensado', NULL),
  (11, 'Requeijão cremoso', NULL),
  (12, 'Mussarela ralada', NULL),
  (13, 'Provolone ralado', NULL),
  (14, 'Parmesão ralado', NULL),
  (15, 'Gorgonzola', NULL),
  (16, 'Calabresa fatiada', NULL),
  (17, 'Cebola fatiada', NULL),
  (18, 'Tomate em rodelas', NULL),
  (19, 'Manjericão fresco', NULL),
  (20, 'Presunto em cubos', NULL),
  (21, 'Ovo cozido picado', 0.600),  -- FAO: Egg, chicken, boiled/poached
  (22, 'Azeitona preta', NULL),
  (23, 'Ervilha', 0.730),  -- FAO: Fresh green peas
  (24, 'Milho verde', 0.730),  -- FAO: Corn, sweet, boiled
  (25, 'Frango desfiado', NULL),
  (26, 'Bacon em cubos', NULL),
  (27, 'Champignon fatiado', NULL),
  (28, 'Rúcula', NULL),
  (29, 'Tomate seco', NULL),
  (30, 'Orégano seco', NULL),
  (31, 'Chocolate ao leite derretido', NULL),
  (32, 'Morango picado', NULL),
  (33, 'Banana em rodelas', NULL),
  (34, 'Canela em pó', 0.560),  -- FAO: Cinnamon, powder
  (35, 'Granulado de chocolate', NULL),
  (36, 'Fermento biológico fresco', NULL),
  (37, 'Tomate pelado triturado', NULL),
  (38, 'Mussarela fatiada', NULL),
  (39, 'Alho fatiado', NULL);

-- Modo de preparo (um passo por linha). Id 2 (Napolitana tradicional): Regulamento
-- (UE) nº 97/2010, Anexo II. Os demais: receitas de referência da equipe.
INSERT INTO TemplatesReceitas (id, modo_de_preparo) VALUES
  (1, -- Tradicional
  'Dissolva o fermento e o açúcar em parte da água morna (cerca de 35 °C) e deixe descansar 10 minutos.
Misture a farinha e o sal, junte a água com fermento, o restante da água e o azeite.
Sove por 10 minutos, até a massa ficar lisa e elástica.
Divida em bolinhas com o peso indicado para cada pizza.
Deixe as bolinhas crescerem cobertas por 1 hora, até dobrarem de volume.'),
  (2, -- Napolitana tradicional
  'Coloque a água na masseira e dissolva o sal; junte 10% da farinha e o fermento e misture.
Acrescente o resto da farinha aos poucos, até dar o ponto; essa etapa leva cerca de 10 minutos.
Sove por 20 minutos em velocidade baixa, até a massa ficar lisa e não grudar.
Primeira fermentação: deixe a massa 2 horas sobre a bancada, coberta com pano úmido (cerca de 25 °C).
Divida em bolinhas com o peso indicado (a especificação aceita de 180 g a 250 g).
Segunda fermentação: 4 a 6 horas em temperatura ambiente; use as bolinhas nas 6 horas seguintes.
Abra com as pontas dos dedos, do centro para fora, sem rolo: centro com até 0,4 cm e borda de 1 a 2 cm.
Pela especificação, asse em forno a lenha a cerca de 485 °C por 60 a 90 segundos.'),
  (3, -- Fina e crocante
  'Misture a farinha, o sal e o fermento.
Junte a água e o azeite e sove por 8 minutos.
Deixe descansar 40 minutos coberta.
Divida em bolinhas com o peso indicado e abra bem fina com o rolo.
Fure a massa com um garfo antes de montar, para não estufar.'),
  (4, -- Massa grossa
  'Dissolva o fermento e o açúcar na água morna e deixe descansar 10 minutos.
Junte a farinha, o sal e metade do azeite e sove por 10 minutos (a massa fica mais mole).
Deixe crescer coberta por 1 hora.
Unte a forma com o restante do azeite, acomode a massa e deixe crescer mais 30 minutos na forma.
Monte e asse em forno a 230 °C por 15 a 18 minutos.'),
  (5, -- Integral
  'Dissolva o fermento e o mel na água morna e deixe descansar 10 minutos.
Misture as duas farinhas e o sal; junte a água com fermento e o azeite.
Sove por 12 minutos (a massa fica levemente pegajosa).
Divida em bolinhas com o peso indicado.
Deixe crescer coberta por 1 hora e 30 minutos.');

-- Sabores. Margherita (ETG) e Marinara (ETG): Regulamento (UE) nº 97/2010,
-- Anexo II (60-80 g de tomate, 80-100 g de mussarela e 4-5 g de azeite por
-- pizza de 35 cm, divididos pela área); manjericão, alho e orégano sem
-- gramas na norma (valores da equipe). Os demais: receitas da equipe.
INSERT INTO Recheios (id, recheio, descricao, doce) VALUES
  (1, 'Mussarela', 'Molho de tomate, mussarela e orégano.', FALSE),
  (2, 'Calabresa', 'Calabresa fatiada, cebola e mussarela.', FALSE),
  (3, 'Margherita (ETG)', 'Tomate pelado, mussarela fatiada, manjericão e azeite, conforme a especificação da Pizza Napoletana.', FALSE),
  (4, 'Portuguesa', 'Presunto, ovo, cebola, ervilha e azeitona.', FALSE),
  (5, 'Frango com requeijão', 'Frango desfiado, requeijão cremoso e milho.', FALSE),
  (6, 'Quatro queijos', 'Mussarela, provolone, parmesão e gorgonzola.', FALSE),
  (7, 'Bacon com champignon', 'Bacon crocante, champignon e mussarela.', FALSE),
  (8, 'Rúcula com tomate seco', 'Mussarela, tomate seco e rúcula fresca.', FALSE),
  (9, 'Chocolate com morango', 'Chocolate ao leite derretido e morangos.', TRUE),
  (10, 'Banana com canela', 'Leite condensado, banana, mussarela e canela.', TRUE),
  (11, 'Marinara (ETG)', 'Tomate pelado, alho, orégano e azeite, sem queijo, conforme a especificação da Pizza Napoletana.', FALSE);

INSERT INTO RecheiosXIngredientes (id_recheio, id_ingrediente, gramas_por_cm2) VALUES
  (1, 9, 0.0800),  -- Mussarela: Molho de tomate
  (1, 12, 0.2000),  -- Mussarela: Mussarela ralada
  (1, 30, 0.0020),  -- Mussarela: Orégano seco
  (2, 9, 0.0800),  -- Calabresa: Molho de tomate
  (2, 12, 0.1000),  -- Calabresa: Mussarela ralada
  (2, 16, 0.1200),  -- Calabresa: Calabresa fatiada
  (2, 17, 0.0500),  -- Calabresa: Cebola fatiada
  (2, 30, 0.0020),  -- Calabresa: Orégano seco
  (3, 37, 0.0728),  -- Margherita (ETG): Tomate pelado triturado
  (3, 38, 0.0935),  -- Margherita (ETG): Mussarela fatiada
  (3, 19, 0.0050),  -- Margherita (ETG): Manjericão fresco
  (3, 7, 0.0047),  -- Margherita (ETG): Azeite de oliva
  (4, 9, 0.0800),  -- Portuguesa: Molho de tomate
  (4, 12, 0.1400),  -- Portuguesa: Mussarela ralada
  (4, 20, 0.0800),  -- Portuguesa: Presunto em cubos
  (4, 21, 0.0600),  -- Portuguesa: Ovo cozido picado
  (4, 17, 0.0400),  -- Portuguesa: Cebola fatiada
  (4, 23, 0.0300),  -- Portuguesa: Ervilha
  (4, 22, 0.0300),  -- Portuguesa: Azeitona preta
  (4, 30, 0.0020),  -- Portuguesa: Orégano seco
  (5, 9, 0.0800),  -- Frango com requeijão: Molho de tomate
  (5, 12, 0.1000),  -- Frango com requeijão: Mussarela ralada
  (5, 25, 0.1200),  -- Frango com requeijão: Frango desfiado
  (5, 11, 0.0800),  -- Frango com requeijão: Requeijão cremoso
  (5, 24, 0.0400),  -- Frango com requeijão: Milho verde
  (5, 30, 0.0020),  -- Frango com requeijão: Orégano seco
  (6, 9, 0.0800),  -- Quatro queijos: Molho de tomate
  (6, 12, 0.1200),  -- Quatro queijos: Mussarela ralada
  (6, 13, 0.0500),  -- Quatro queijos: Provolone ralado
  (6, 14, 0.0400),  -- Quatro queijos: Parmesão ralado
  (6, 15, 0.0500),  -- Quatro queijos: Gorgonzola
  (7, 9, 0.0800),  -- Bacon com champignon: Molho de tomate
  (7, 12, 0.1400),  -- Bacon com champignon: Mussarela ralada
  (7, 26, 0.0700),  -- Bacon com champignon: Bacon em cubos
  (7, 27, 0.0700),  -- Bacon com champignon: Champignon fatiado
  (7, 30, 0.0020),  -- Bacon com champignon: Orégano seco
  (8, 9, 0.0800),  -- Rúcula com tomate seco: Molho de tomate
  (8, 12, 0.1600),  -- Rúcula com tomate seco: Mussarela ralada
  (8, 29, 0.0500),  -- Rúcula com tomate seco: Tomate seco
  (8, 28, 0.0300),  -- Rúcula com tomate seco: Rúcula
  (8, 14, 0.0200),  -- Rúcula com tomate seco: Parmesão ralado
  (9, 31, 0.1500),  -- Chocolate com morango: Chocolate ao leite derretido
  (9, 32, 0.1000),  -- Chocolate com morango: Morango picado
  (9, 35, 0.0100),  -- Chocolate com morango: Granulado de chocolate
  (10, 10, 0.0800),  -- Banana com canela: Leite condensado
  (10, 12, 0.0800),  -- Banana com canela: Mussarela ralada
  (10, 33, 0.1500),  -- Banana com canela: Banana em rodelas
  (10, 6, 0.0100),  -- Banana com canela: Açúcar
  (10, 34, 0.0020),  -- Banana com canela: Canela em pó
  (11, 37, 0.0883),  -- Marinara (ETG): Tomate pelado triturado
  (11, 39, 0.0040),  -- Marinara (ETG): Alho fatiado
  (11, 30, 0.0010),  -- Marinara (ETG): Orégano seco
  (11, 7, 0.0047);  -- Marinara (ETG): Azeite de oliva

-- ---------------------------------------------------------------------
-- Consultas úteis para a apresentação
-- ---------------------------------------------------------------------
-- Últimas receitas geradas, com os parâmetros do pedido:
--   SELECT id, `timestamp`, parametros FROM Receitas_Geradas ORDER BY id DESC LIMIT 10;
--
-- Ingredientes usados numa receita:
--   SELECT i.ingrediente, x.quantidade_usada_gramas
--   FROM ReceitasXIngredientes x JOIN Ingredientes i ON i.id = x.id_ingrediente
--   WHERE x.id_receita_gerada = 1;
--
-- Ingredientes mais usados (kg):
--   SELECT i.ingrediente, ROUND(SUM(x.quantidade_usada_gramas) / 1000, 2) AS kg
--   FROM ReceitasXIngredientes x JOIN Ingredientes i ON i.id = x.id_ingrediente
--   GROUP BY i.id ORDER BY kg DESC;
--
-- Ingredientes de cada sabor:
--   SELECT r.recheio, i.ingrediente, x.gramas_por_cm2
--   FROM RecheiosXIngredientes x JOIN Recheios r ON r.id = x.id_recheio
--   JOIN Ingredientes i ON i.id = x.id_ingrediente ORDER BY r.id, x.id;
