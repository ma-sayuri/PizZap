/* PizZap - scripts das telas (sem frameworks).
   O backend valida tudo de novo; aqui é só para dar retorno imediato. */
(function () {
  'use strict';

  /* ---------------------------------------------------- tela de receita */
  document.querySelectorAll('[data-imprimir]').forEach(function (botao) {
    botao.addEventListener('click', function () { window.print(); });
  });

  /* ----------------------------------------------------------- formulário */
  var form = document.querySelector('[data-form-receita]');
  if (!form) return;

  var lista = form.querySelector('[data-lista]');
  var modelo = document.getElementById('modelo-pizza');
  var maxLinhas = parseInt(form.dataset.maxLinhas, 10) || 10;
  var maxSabores = parseInt(form.dataset.maxSabores, 10) || 4;
  var botaoAdicionar = form.querySelector('[data-adicionar]');
  var proximoIndice = lista.querySelectorAll('[data-linha]').length;

  function linhas() { return Array.prototype.slice.call(lista.querySelectorAll('[data-linha]')); }

  function inteiro(valor) {
    return /^\s*\d+\s*$/.test(valor) ? parseInt(valor, 10) : NaN;
  }

  function atualizarTotal() {
    var total = 0;
    var valido = true;
    linhas().forEach(function (linha) {
      var q = inteiro(linha.querySelector('[data-qtd]').value);
      if (isNaN(q) || q < 1) valido = false; else total += q;
    });
    form.querySelector('[data-total]').textContent = valido ? total : '–';
    form.querySelector('[data-total-rotulo]').textContent = total === 1 ? 'pizza' : 'pizzas';
  }

  function renumerar() {
    var todas = linhas();
    todas.forEach(function (linha, i) {
      linha.querySelector('.pizza-num').textContent = 'Pizza ' + (i + 1);
      linha.querySelector('[data-remover]').setAttribute('aria-label', 'Remover pizza ' + (i + 1));
    });
    lista.toggleAttribute('data-unica', todas.length === 1);
    botaoAdicionar.hidden = todas.length >= maxLinhas;
    atualizarTotal();
  }

  function limitarSabores(grupo) {
    var caixas = grupo.querySelectorAll('input[type="checkbox"]');
    var marcadas = grupo.querySelectorAll('input[type="checkbox"]:checked').length;
    caixas.forEach(function (c) { c.disabled = !c.checked && marcadas >= maxSabores; });
  }

  /* ----- mensagens de erro (vermelho) e campo ok (verde) */
  function marcar(campo, mensagem) {
    var atual = campo.querySelector('.msg-erro');
    campo.classList.toggle('campo-invalido', !!mensagem);
    campo.classList.toggle('campo-ok', !mensagem);
    if (mensagem) {
      if (!atual) {
        atual = document.createElement('p');
        atual.className = 'msg-erro';
        campo.appendChild(atual);
      }
      atual.textContent = mensagem;
    } else if (atual) {
      atual.remove();
    }
    return !mensagem;
  }

  function validarLinha(linha) {
    var ok = true;
    var qtd = linha.querySelector('[data-qtd]');
    var q = inteiro(qtd.value);
    var msgQtd = '';
    if (qtd.value.trim() === '') msgQtd = 'Informe a quantidade.';
    else if (isNaN(q) || q < 1) msgQtd = 'A quantidade deve ser um número inteiro maior que zero.';
    else if (q > 50) msgQtd = 'No máximo 50 pizzas iguais.';
    ok = marcar(qtd.closest('.campo'), msgQtd) && ok;

    linha.querySelectorAll('select').forEach(function (s) {
      ok = marcar(s.closest('.campo'), s.value ? '' : 'Escolha uma opção.') && ok;
    });

    var sabores = linha.querySelector('[data-sabores]');
    var marcados = sabores.querySelectorAll('input:checked').length;
    ok = marcar(sabores, marcados ? '' : 'Escolha pelo menos um recheio.') && ok;
    return ok;
  }

  function validarUnidade() {
    var grupo = form.querySelector('.opcoes-unidade');
    var bloco = grupo.parentNode;
    var escolhida = form.querySelector('input[name="unidade"]:checked');
    var msg = bloco.querySelector(':scope > .msg-erro');
    grupo.classList.toggle('campo-invalido', !escolhida);
    if (!escolhida && !msg) {
      msg = document.createElement('p');
      msg.className = 'msg-erro';
      msg.textContent = 'Escolha a unidade de medida.';
      bloco.appendChild(msg);
    } else if (escolhida && msg) {
      msg.remove();
    }
    return !!escolhida;
  }

  /* ----- eventos */
  botaoAdicionar.addEventListener('click', function () {
    if (linhas().length >= maxLinhas) return;
    var html = modelo.innerHTML.replace(/__i__/g, String(proximoIndice++)).replace(/__n__/g, String(linhas().length + 1));
    var temp = document.createElement('div');
    temp.innerHTML = html.trim();
    var nova = temp.firstElementChild;
    lista.appendChild(nova);
    renumerar();
    nova.querySelector('[data-qtd]').focus();
  });

  lista.addEventListener('click', function (e) {
    var botao = e.target.closest('[data-remover]');
    if (!botao || linhas().length <= 1) return;
    var linha = botao.closest('[data-linha]');
    var anterior = linha.previousElementSibling || linha.nextElementSibling;
    linha.remove();
    renumerar();
    if (anterior) anterior.querySelector('[data-qtd]').focus();
  });

  lista.addEventListener('input', function (e) {
    if (e.target.matches('[data-qtd]')) {
      atualizarTotal();
      var campo = e.target.closest('.campo');
      if (campo.classList.contains('campo-invalido')) validarLinha(e.target.closest('[data-linha]'));
    }
  });

  lista.addEventListener('change', function (e) {
    var grupo = e.target.closest('[data-sabores]');
    if (grupo) {
      limitarSabores(grupo);
      if (grupo.classList.contains('campo-invalido')) validarLinha(grupo.closest('[data-linha]'));
    }
  });

  form.addEventListener('change', function (e) {
    if (e.target.name === 'unidade') validarUnidade();
  });

  form.addEventListener('submit', function (e) {
    var ok = true;
    linhas().forEach(function (linha) { ok = validarLinha(linha) && ok; });
    ok = validarUnidade() && ok;
    if (!ok) {
      e.preventDefault();
      var primeiro = form.querySelector('.campo-invalido input, .campo-invalido select');
      if (primeiro) {
        primeiro.closest('.campo, .bloco').scrollIntoView({ behavior: 'smooth', block: 'center' });
        primeiro.focus({ preventScroll: true });
      }
    }
  });

  /* ----- estado inicial */
  form.querySelectorAll('[data-sabores]').forEach(limitarSabores);
  renumerar();
  var resumo = document.getElementById('resumo-erros');
  if (resumo) resumo.focus();
})();
