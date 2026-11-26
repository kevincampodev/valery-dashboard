/*
 * Menú lateral y buscador del panel.
 * - Secciones plegables (recuerda cuáles cerraste; la de la página actual siempre abre).
 * - Indicador de la sección activa que se desliza desde donde estabas.
 * - Menú contraído a solo íconos (se recuerda).
 * - Buscador con Ctrl + K: secciones del menú + clientes, proveedores, vendedoras y facturas.
 */
(() => {
  const reducir = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const leer = (clave, defecto) => { try { return JSON.parse(localStorage.getItem(clave)) ?? defecto; } catch (e) { return defecto; } };
  const guardar = (clave, valor) => { try { localStorage.setItem(clave, JSON.stringify(valor)); } catch (e) {} };
  const html = document.documentElement;

  // ---------- Indicador deslizante ----------
  const contenedor = document.getElementById('menuSecciones');
  const indicador = contenedor && contenedor.querySelector('.menu-indicador');
  // Distancia del enlace al borde superior del menú (contando el scroll), sin importar en qué sección esté
  const posicion = el => el.getBoundingClientRect().top - contenedor.getBoundingClientRect().top + contenedor.scrollTop;
  const ubicar = (animar = true) => {
    if (!indicador) return;
    const activo = contenedor.querySelector('.menu-enlace.activo');
    const visible = activo && activo.offsetParent !== null && activo.getBoundingClientRect().height > 0;
    if (!visible) { indicador.style.opacity = 0; return; }
    if (!animar) indicador.style.transition = 'none';
    const y = posicion(activo);
    indicador.style.opacity = 1;
    indicador.style.transform = `translateY(${y}px)`;
    indicador.style.height = activo.offsetHeight + 'px';
    try { sessionStorage.setItem('menu-indicador', String(y)); } catch (e) {}
    if (!animar) { indicador.offsetHeight; indicador.style.transition = ''; }
  };

  // ---------- Secciones plegables ----------
  // Al cargar, las secciones quedan como las dejaste sin animarse (si no, el indicador mediría mal)
  html.classList.add('menu-cargando');
  const cerradas = new Set(leer('menu-cerradas', []));
  document.querySelectorAll('.menu-grupo').forEach(grupo => {
    const nombre = grupo.dataset.grupo, boton = grupo.querySelector('.menu-titulo');
    const fijar = cerrada => {
      grupo.classList.toggle('cerrada', cerrada);
      boton.setAttribute('aria-expanded', String(!cerrada));
    };
    fijar(cerradas.has(nombre) && !grupo.classList.contains('contiene-activo'));
    boton.addEventListener('click', () => {
      const cerrar = !grupo.classList.contains('cerrada');
      fijar(cerrar);
      cerrar ? cerradas.add(nombre) : cerradas.delete(nombre);
      guardar('menu-cerradas', [...cerradas]);
      // el indicador sigue al enlace mientras la sección se abre o se cierra
      const inicio = performance.now();
      const seguir = t => { ubicar(false); if (t - inicio < 350) requestAnimationFrame(seguir); };
      requestAnimationFrame(seguir);
    });
  });

  contenedor && contenedor.offsetHeight;          // aplica las secciones cerradas de una vez
  requestAnimationFrame(() => html.classList.remove('menu-cargando'));

  // Primera ubicación: desde donde estaba en la página anterior, deslizándose hasta la actual
  if (indicador) {
    let anterior = null;
    try { anterior = sessionStorage.getItem('menu-indicador'); } catch (e) {}
    if (anterior !== null && !reducir) {
      indicador.style.transition = 'none';
      indicador.style.transform = `translateY(${anterior}px)`;
      indicador.style.opacity = 1;
      indicador.offsetHeight;
      indicador.style.transition = '';
      requestAnimationFrame(() => ubicar(true));
    } else {
      ubicar(false);
    }
    window.addEventListener('resize', () => ubicar(false));
    const activo = contenedor.querySelector('.menu-enlace.activo');
    if (activo && posicion(activo) > contenedor.clientHeight - 60) { contenedor.scrollTop = posicion(activo) - 120; ubicar(false); }
  }

  // ---------- Menú contraído ----------
  const contraer = document.getElementById('contraerMenu');
  if (contraer) {
    const titulo = () => {
      const mini = html.classList.contains('menu-mini');
      contraer.title = mini ? 'Expandir menú' : 'Contraer menú';
      contraer.setAttribute('aria-label', contraer.title);
    };
    titulo();
    contraer.addEventListener('click', () => {
      const mini = html.classList.toggle('menu-mini');
      try { localStorage.setItem('menu-mini', mini ? '1' : '0'); } catch (e) {}
      titulo();
      ubicar(false);
      setTimeout(() => { ubicar(false); window.dispatchEvent(new Event('resize')); }, 260);  // las gráficas se reacomodan
    });
  }

  // ---------- Buscador (Ctrl + K) ----------
  const caja = document.getElementById('buscador');
  if (!caja || !window.PANEL) return;
  const campo = document.getElementById('buscadorTexto'), lista = document.getElementById('buscadorLista');
  let resultados = [], elegido = 0, pedido = 0, temporizador = null, foco = null;

  const sinTildes = t => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const escapar = t => String(t ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const icono = n => `<svg class="ico" aria-hidden="true"><use href="${PANEL.iconos}#${n}"></use></svg>`;

  const pintar = (cargando = false) => {
    if (!resultados.length) {
      lista.innerHTML = `<div class="buscador-vacio">${cargando ? 'Buscando…' : (campo.value.trim() ? 'No encontramos nada con ese nombre.' : '')}</div>`;
      return;
    }
    let grupo = null, html = '';
    resultados.forEach((r, i) => {
      if (r.grupo !== grupo) { grupo = r.grupo; html += `<div class="buscador-grupo">${escapar(grupo)}</div>`; }
      html += `<a href="${escapar(r.url)}" class="buscador-item${i === elegido ? ' elegido' : ''}" role="option" aria-selected="${i === elegido}" data-i="${i}">
        <span class="buscador-icono">${icono(r.icono || 'search')}</span>
        <span class="buscador-textos"><strong>${escapar(r.titulo)}</strong>${r.detalle ? `<small>${escapar(r.detalle)}</small>` : ''}</span>
      </a>`;
    });
    lista.innerHTML = html;
    const actual = lista.querySelector('.elegido');
    if (actual) actual.scrollIntoView({ block: 'nearest' });
  };

  const secciones = texto => {
    const t = sinTildes(texto.trim());
    return PANEL.secciones
      .filter(s => !t || sinTildes(s.titulo + ' ' + s.detalle).includes(t))
      .map(s => ({ ...s, grupo: 'Secciones' }));
  };

  const buscar = () => {
    const texto = campo.value;
    resultados = secciones(texto);
    elegido = 0;
    clearTimeout(temporizador);
    if (texto.trim().length < 2) { pintar(); return; }
    pintar(!resultados.length);
    const numero = ++pedido;
    temporizador = setTimeout(() => {
      fetch(`${PANEL.buscar}?q=${encodeURIComponent(texto)}`, { headers: { Accept: 'application/json' } })
        .then(r => r.ok ? r.json() : { resultados: [] })
        .then(d => {
          if (numero !== pedido) return;          // llegó tarde: ya escribiste otra cosa
          resultados = secciones(texto).concat(d.resultados || []);
          pintar();
        })
        .catch(() => { if (numero === pedido) pintar(); });
    }, 180);
  };

  const abrir = () => {
    foco = document.activeElement;
    caja.hidden = false;
    html.classList.add('buscador-abierto');
    const menu = window.bootstrap && bootstrap.Offcanvas.getInstance(document.getElementById('menuLateral'));
    if (menu) menu.hide();
    campo.value = '';
    buscar();
    setTimeout(() => campo.focus(), 10);
  };
  const cerrar = () => {
    caja.hidden = true;
    html.classList.remove('buscador-abierto');
    if (foco && foco.focus) foco.focus();
  };

  document.querySelectorAll('[data-abrir-buscador]').forEach(b => b.addEventListener('click', abrir));
  caja.querySelectorAll('[data-cerrar-buscador]').forEach(b => b.addEventListener('click', cerrar));
  campo.addEventListener('input', buscar);
  lista.addEventListener('mousemove', e => {
    const item = e.target.closest('.buscador-item');
    if (item && Number(item.dataset.i) !== elegido) { elegido = Number(item.dataset.i); pintar(); }
  });
  document.addEventListener('keydown', e => {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') { e.preventDefault(); caja.hidden ? abrir() : cerrar(); return; }
    if (caja.hidden) return;
    if (e.key === 'Escape') { e.preventDefault(); cerrar(); }
    else if (e.key === 'ArrowDown' && resultados.length) { e.preventDefault(); elegido = (elegido + 1) % resultados.length; pintar(); }
    else if (e.key === 'ArrowUp' && resultados.length) { e.preventDefault(); elegido = (elegido - 1 + resultados.length) % resultados.length; pintar(); }
    else if (e.key === 'Enter' && resultados[elegido]) { e.preventDefault(); location.href = resultados[elegido].url; }
  });
})();
