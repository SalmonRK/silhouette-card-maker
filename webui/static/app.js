(() => {
  'use strict'
  const $ = (s, el = document) => el.querySelector(s)
  const $$ = (s, el = document) => [...el.querySelectorAll(s)]
  const SVGNS = 'http://www.w3.org/2000/svg'

  const store = {
    get(k, d) { try { const v = localStorage.getItem('scm.' + k); return v == null ? d : JSON.parse(v) } catch { return d } },
    set(k, v) { try { localStorage.setItem('scm.' + k, JSON.stringify(v)) } catch { /* private mode */ } },
  }

  const st = {
    lang: store.get('lang', 'th'),
    ws: 'create',
    step: 'cards',
    opts: null,
    job: null,
    layout: null,
    sheet: 0,
    settings: Object.assign(
      { paper: 'a4', card: 'standard', borderless: false, registration: '3', fit: 'stretch', extendBleed: '', crop: '', specialty: '' },
      store.get('settings', {}),
    ),
  }

  // ------------------------------------------------------------ i18n
  const t = (k, vars) => {
    let s = (I18N[st.lang] || I18N.th)[k] ?? I18N.en[k] ?? k
    if (vars) for (const [a, b] of Object.entries(vars)) s = s.replaceAll(`{${a}}`, b)
    return s
  }
  function applyLang() {
    document.documentElement.lang = st.lang
    $$('[data-i18n]').forEach((el) => (el.textContent = t(el.dataset.i18n)))
    $$('[data-i18n-aria]').forEach((el) => el.setAttribute('aria-label', t(el.dataset.i18nAria)))
    $$('[data-i18n-ph]').forEach((el) => (el.placeholder = t(el.dataset.i18nPh)))
    $$('[data-lang]').forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.lang === st.lang)))
    renderAll()
  }

  // ------------------------------------------------------------ api
  async function api(path, init) {
    let res
    try { res = await fetch(path, init) } catch { toast(t('err.network')); throw new Error('network') }
    const body = res.headers.get('content-type')?.includes('json') ? await res.json() : null
    if (!res.ok) { const e = new Error(body?.error || res.statusText); e.body = body; throw e }
    return body
  }
  const post = (p, data) => api(p, { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(data ?? {}) })

  async function ensureJob() {
    const id = store.get('job', null)
    if (id) { try { st.job = await api(`api/jobs/${id}`); return } catch { /* expired */ } }
    st.job = await post('api/jobs')
    store.set('job', st.job.id)
  }

  // ------------------------------------------------------------ toast
  let toastTimer
  function toast(msg) {
    const el = $('#toast')
    el.textContent = msg
    el.hidden = false
    clearTimeout(toastTimer)
    toastTimer = setTimeout(() => (el.hidden = true), 5000)
  }

  // ------------------------------------------------------------ steps
  function go(step) {
    st.step = step
    $$('[data-pane]').forEach((p) => (p.hidden = p.dataset.pane !== step))
    $$('[data-step]').forEach((b) => b.setAttribute('aria-current', b.dataset.step === step ? 'step' : 'false'))
    if (step === 'make') refreshOffset()
    renderStage()
  }

  // ------------------------------------------------------------ cards
  const img = (kind, name) => `api/jobs/${st.job.id}/img/${kind}/${encodeURIComponent(name)}?v=${st.job.front.length}-${st.job.ds.length}`

  async function upload(kind, files, front) {
    if (!files.length) return
    const fd = new FormData()
    for (const f of files) fd.append('files', f)
    if (front) fd.append('front', front)
    const r = await api(`api/jobs/${st.job.id}/files/${kind}`, { method: 'POST', body: fd })
    if (r.skipped?.length) toast(t('err.skipped', { f: r.skipped.join(', ') }))
    st.job = r
    renderAll()
  }

  async function remove(kind, name) {
    st.job = await api(`api/jobs/${st.job.id}/files/${kind}/${encodeURIComponent(name)}`, { method: 'DELETE' })
    renderAll()
  }

  // upstream lays out single-sided fronts first, then the ones with their own back (utilities.generate_pdf)
  function printOrder() {
    const own = new Set((st.job?.ds || []).map((f) => f.stem))
    const front = st.job?.front || []
    return [...front.filter((f) => !own.has(f.stem)), ...front.filter((f) => own.has(f.stem))]
  }

  function renderCards() {
    const { back, ds } = st.job
    const front = printOrder()
    const dsBy = Object.fromEntries(ds.map((f) => [f.stem, f]))
    $('#frontCount').textContent = front.length ? `(${front.length})` : ''
    $('#clearAll').hidden = !front.length
    const list = $('#cardList')
    list.textContent = ''
    if (!front.length) {
      const li = document.createElement('li')
      li.className = 'none'
      li.textContent = t('cards.none')
      list.append(li)
    }
    front.forEach((f, i) => {
      const li = document.createElement('li')
      const own = dsBy[f.stem]
      li.innerHTML = `
        <span class="idx">${i + 1}</span>
        <img class="thumb-sm" alt="" loading="lazy">
        <span class="name"></span>
        <label class="mini ${own ? 'has' : ''}" title="${t('cards.ownBack')}">
          <input type="file" accept="image/*" hidden>
          ${own ? '<img class="thumb-sm" alt="">' : `<span>${t('cards.ownBack')}</span>`}
        </label>
        <button type="button" class="x" aria-label="${t('cards.remove')} ${f.name}">×</button>`
      li.querySelector('img').src = img('front', f.name)
      li.querySelector('.name').textContent = f.name
      if (own) li.querySelector('label img').src = img('ds', own.name)
      li.querySelector('input').addEventListener('change', (e) => upload('ds', e.target.files, f.name))
      li.querySelector('.x').addEventListener('click', () => remove('front', f.name))
      list.append(li)
    })
    const b = back[0]
    $('#backImg').hidden = !b
    $('#backEmpty').hidden = !!b
    if (b) $('#backImg').src = img('back', b.name) + '&b=' + b.size
  }

  function bindDrop(el, kind) {
    el.addEventListener('dragover', (e) => { e.preventDefault(); el.classList.add('over') })
    el.addEventListener('dragleave', () => el.classList.remove('over'))
    el.addEventListener('drop', (e) => {
      e.preventDefault()
      el.classList.remove('over')
      upload(kind, [...e.dataTransfer.files])
    })
  }

  // ------------------------------------------------------------ layout
  const label = (k) => k.replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase())
  const fmt = (n) => (Math.round(n * 100) / 100).toString()

  function fillSelects() {
    const { cards, papers, combos, specialty } = st.opts
    const variant = st.settings.borderless ? 'borderless' : 'default'
    const paperSel = $('#paper')
    paperSel.innerHTML = Object.entries(papers)
      .map(([k, p]) => `<option value="${k}">${label(k)} · ${fmt(p.w)} × ${fmt(p.h)} mm</option>`).join('')
    paperSel.value = st.settings.paper
    const ok = new Set(combos.filter((c) => c.paper === st.settings.paper && c.variant === variant).map((c) => c.card))
    const cardSel = $('#card')
    cardSel.innerHTML = Object.entries(cards)
      .filter(([k]) => ok.has(k))
      .map(([k, c]) => `<option value="${k}">${label(k)} · ${fmt(c.w)} × ${fmt(c.h)} mm</option>`).join('')
    if (!ok.has(st.settings.card)) st.settings.card = ok.has('standard') ? 'standard' : [...ok][0]
    cardSel.value = st.settings.card
    const sp = $('#specialty')
    sp.innerHTML = `<option value="">${t('layout.none')}</option>` + specialty.map((s) => `<option value="${s}">${label(s)}</option>`).join('')
    sp.value = st.settings.specialty
    $('#borderless').checked = st.settings.borderless
    $('#registration').value = st.settings.registration
    $('#fit').value = st.settings.fit
    $('#extendBleed').value = st.settings.extendBleed
    $('#crop').value = st.settings.crop
  }

  async function loadLayout() {
    const s = st.settings
    const q = new URLSearchParams({ paper: s.paper, card: s.card, borderless: s.borderless ? '1' : '0', specialty: s.specialty })
    try {
      st.layout = await api(`api/layout?${q}`)
      $('#layoutError').hidden = true
    } catch (e) {
      st.layout = null
      $('#layoutError').textContent = t('err.layout')
      $('#layoutError').hidden = false
    }
    st.sheet = 0
    renderAll()
  }

  function onSetting(e) {
    const el = e.target
    const k = el.id
    st.settings[k] = el.type === 'checkbox' ? el.checked : el.value
    store.set('settings', st.settings)
    if (['paper', 'borderless'].includes(k)) fillSelects()
    if (['paper', 'card', 'borderless', 'specialty'].includes(k)) loadLayout()
    else renderAll()
  }

  const perSheet = () => (st.layout ? st.layout.slots.length : 0)
  const sheetCount = () => Math.max(1, Math.ceil((st.job?.front.length || 0) / Math.max(1, perSheet())))

  function renderFacts() {
    const L = st.layout
    const dl = $('#layoutFacts')
    if (!L) { dl.textContent = ''; return }
    const r = L.registration
    const rows = [
      [t('layout.cardSize'), `${fmt(L.cardW)} × ${fmt(L.cardH)} mm`],
      [t('layout.perSheet'), `${L.slots.length} (${L.cols} × ${L.rows})`],
      [t('layout.sheets'), String(sheetCount())],
      [t('layout.marksVal'), `${fmt(r.length)} / ${fmt(r.thickness)} / ${fmt(r.inset)} mm`],
      [t('layout.template'), L.templateAvailable ? `${L.template}.studio3` : t('layout.noTemplate')],
    ]
    dl.innerHTML = rows.map(([a, b]) => `<div><dt>${a}</dt><dd>${b}</dd></div>`).join('')
  }

  // ------------------------------------------------------------ stage (the sheet on the mat)
  function el(name, attrs, parent) {
    const n = document.createElementNS(SVGNS, name)
    for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v)
    parent?.append(n)
    return n
  }

  function marks(g, L, four) {
    const { inset: i, thickness: th, length: len } = L.registration
    const W = L.pageW, H = L.pageH, h = th / 2
    const r = (x, y, w, hh) => el('rect', { x, y, width: w, height: hh, class: 'mark' }, g)
    r(i - h, i - h, 5 + th, 5 + th) // square, top-left
    r(W - i - len, i - h, len + h, th); r(W - i - h, i - h, th, len + h) // top-right L
    r(i - h, H - i - len, th, len + h); r(i - h, H - i - h, len + h, th) // bottom-left L
    if (four) { r(W - i - len, H - i - h, len + h, th); r(W - i - h, H - i - len, th, len + h) }
  }

  function renderStage() {
    const svg = $('#sheet')
    const L = st.layout
    svg.textContent = ''
    el('title', { id: 'sheetTitle' }, svg).textContent = 'Sheet preview'
    const front = printOrder()
    $('#stageEmpty').hidden = !!front.length || st.step !== 'cards'
    if (!L) return
    const showBack = st.step === 'make' && st.showBack
    const pad = 8
    svg.setAttribute('viewBox', `${-pad} ${-pad} ${L.pageW + pad * 2} ${L.pageH + pad * 2}`)
    el('rect', { x: 0, y: 0, width: L.pageW, height: L.pageH, class: 'paper' }, svg)
    const defs = el('defs', {}, svg)
    const g = el('g', {}, svg)
    const dsBy = Object.fromEntries((st.job?.ds || []).map((f) => [f.stem, f]))
    const back = st.job?.back?.[0]
    const start = st.sheet * L.slots.length
    L.slots.forEach((s, k) => {
      const f = front[start + k]
      const id = `c${k}`
      const cp = el('clipPath', { id }, defs)
      el('rect', { x: s.x, y: s.y, width: s.w, height: s.h, rx: L.radius, ry: L.radius }, cp)
      if (f) {
        const src = showBack ? (dsBy[f.stem] ? img('ds', dsBy[f.stem].name) : back && img('back', back.name)) : img('front', f.name)
        if (src) el('image', { href: src, x: s.x, y: s.y, width: s.w, height: s.h, preserveAspectRatio: st.settings.fit === 'crop' ? 'xMidYMid slice' : 'none', 'clip-path': `url(#${id})` }, g)
      } else {
        el('rect', { x: s.x, y: s.y, width: s.w, height: s.h, rx: L.radius, class: 'slot' }, g)
      }
      el('rect', { x: s.x, y: s.y, width: s.w, height: s.h, rx: L.radius, ry: L.radius, class: 'cut', pathLength: 100 }, g)
    })
    marks(el('g', {}, svg), L, st.settings.registration === '4')

    const n = sheetCount()
    $('#pager').hidden = n < 2
    $('#sheetNo').textContent = `${st.sheet + 1} / ${n}`
    $('#stageMeta').textContent = `${label(L.paper)} ${L.orientation} · ${fmt(L.cardW)} × ${fmt(L.cardH)} mm · ${L.slots.length}/sheet`
  }

  function traceCuts() {
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return
    const svg = $('#sheet')
    svg.classList.remove('tracing')
    void svg.getBoundingClientRect()
    svg.classList.add('tracing')
  }

  // ------------------------------------------------------------ workspaces
  function showWs(ws) {
    st.ws = ws
    store.set('ws', ws)
    $$('[data-ws-pane]').forEach((p) => (p.hidden = p.dataset.wsPane !== ws))
    $$('[data-ws]').forEach((b) => b.setAttribute('aria-current', b.dataset.ws === ws ? 'page' : 'false'))
    if (ws === 'import') openImport().catch(() => {})
    if (ws === 'machine') { refreshOffset(); renderMachine() }
    if (ws === 'create') renderStage()
  }

  // ------------------------------------------------------------ A. deck import (upstream plugins/ + deck library)
  // A fetch fills the server's deck library (webui/data/decks/<id>) first; "use" copies it into the job. The
  // library doubles as history: an old deck opens instantly and can be used again without downloading.
  const GAMES = { // initials + colour for each plugin; a tile without art shows these
    mtg: ['MTG', '#b4552d'], pokemon: ['PKM', '#d69a12'], yugioh: ['YGO', '#6b3fa0'], one_piece: ['OP', '#c8302c'],
    lorcana: ['LOR', '#2c4f9e'], digimon: ['DGM', '#1f7fc4'], flesh_and_blood: ['FAB', '#8a1f1f'],
    star_wars_unlimited: ['SWU', '#1d2b3a'], gundam: ['GDM', '#3c6e8f'], final_fantasy: ['FF', '#4a5bb8'],
    riftbound: ['RB', '#c0692a'], sorcery_contested_realm: ['SOR', '#5b6b3a'], grand_archive: ['GA', '#2d8a7a'],
    altered: ['ALT', '#7a5c3a'], netrunner: ['NR', '#2b2f6b'], arkham_horror_lcg: ['AH', '#3d5a40'],
    lotr_lcg: ['LOTR', '#6e5a2a'], keyforge: ['KF', '#8c2f6e'], ashes_reborn: ['ASH', '#9a4a2a'],
    bushiroad: ['BSR', '#d2445f'], elestrals: ['ELE', '#3f8f4f'], echoes_of_astra: ['EOA', '#5a4a8f'],
  }
  const ORDER = Object.keys(GAMES)
  const gameStyle = (id) => GAMES[id] || [id.slice(0, 3).toUpperCase(), '#4b5a55']
  const abbr = (id) => `<span class="abbr" style="background:${gameStyle(id)[1]}">${gameStyle(id)[0]}</span>`
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])

  let plugins = null
  let impPoll
  const imp = { game: store.get('impGame', 'mtg'), view: 'pick', deck: null, history: [] }
  const plugin = () => plugins?.find((p) => p.id === imp.game)

  async function openImport() {
    if (!plugins) {
      plugins = (await api('api/plugins')).filter((p) => !p.error)
        .sort((a, b) => (ORDER.indexOf(a.id) + 1 || 99) - (ORDER.indexOf(b.id) + 1 || 99))
      if (!plugin()) imp.game = plugins[0]?.id
      renderGames()
      renderPlugin()
    }
    await loadHistory()
    renderImport()
  }

  function renderGames() {
    const q = $('#gameSearch').value.trim().toLowerCase()
    const box = $('#view-pick')
    box.textContent = ''
    for (const p of plugins || []) {
      if (q && !(p.name + ' ' + p.id).toLowerCase().includes(q)) continue
      const [ab, col] = gameStyle(p.id)
      const b = document.createElement('button')
      b.type = 'button'
      b.className = 'game'
      b.setAttribute('role', 'radio')
      b.setAttribute('aria-checked', String(p.id === imp.game))
      b.innerHTML = `<span class="art" style="background:${col}">${p.art ? `<img src="static/assets/games/${p.id}.jpg" alt="" loading="lazy">` : ab}</span>
        <span class="meta">${abbr(p.id)}<span class="t"></span></span><span class="s">${t('imp.formats', { n: p.formats.length })}</span>`
      b.querySelector('.t').textContent = p.name
      b.addEventListener('click', () => { imp.game = p.id; renderGames(); renderPlugin() })
      box.append(b)
    }
  }

  function renderPlugin() {
    const p = plugin()
    if (!p) return
    store.set('impGame', p.id)
    $('#gameHead').innerHTML = `${abbr(p.id)}<span><b></b><small>${t('imp.source')}</small></span>`
    $('#gameHead b').textContent = p.name
    const fs = $('#impFormat')
    fs.textContent = ''
    for (const f of p.formats) fs.append(new Option(f, f))
    const saved = store.get('impFormat', {})[p.id]
    if (p.formats.includes(saved)) fs.value = saved
    const box = $('#impOptions')
    box.textContent = ''
    if (!p.options.length) box.innerHTML = `<p class="hint">${t('imp.noOptions')}</p>`
    for (const o of p.options) {
      const id = 'impOpt-' + o.name
      const wrap = document.createElement(o.kind === 'flag' ? 'label' : 'div')
      if (o.kind === 'flag') {
        wrap.className = 'check'
        wrap.innerHTML = `<input type="checkbox" id="${id}"> <span></span>`
        wrap.querySelector('span').textContent = o.flag
      } else {
        wrap.className = 'field'
        wrap.innerHTML = `<label for="${id}"></label>`
        wrap.querySelector('label').textContent = o.flag + (o.multiple ? ' ' + t('import.multi') : '')
        let input
        if (o.kind === 'choice' && !o.multiple) {
          input = document.createElement('select')
          if (o.default == null) input.append(new Option('—', ''))
          for (const c of o.choices) input.append(new Option(c, c))
          if (o.default != null) input.value = o.default
        } else {
          input = document.createElement('input')
          input.placeholder = o.choices.length ? o.choices.join(', ') : ''
        }
        input.id = id
        wrap.append(input)
      }
      wrap.title = o.help
      const help = document.createElement('small')
      help.className = 'hint opt-help'
      help.textContent = o.help
      wrap.append(help)
      box.append(wrap)
    }
    estimate()
  }

  function impOptions() {
    const out = {}
    for (const o of plugin()?.options || []) {
      const el = $('#impOpt-' + o.name)
      out[o.name] = o.kind === 'flag' ? el.checked : el.value.trim()
    }
    return out
  }

  // "4 Lightning Bolt" style lines → rough card count before fetching (links cannot be counted)
  function estimate() {
    const lines = $('#impDeck').value.split('\n').map((l) => l.trim()).filter(Boolean)
    let n = 0
    for (const l of lines) { const m = l.match(/^(\d+)\s*x?\s+\S/i); if (m) n += +m[1] }
    $('#impEstimate').textContent = n ? t('imp.estimate', { n }) : ''
  }

  async function runImport() {
    const p = plugin()
    if (!p) return
    store.set('impFormat', { ...store.get('impFormat', {}), [p.id]: $('#impFormat').value })
    try {
      imp.deck = await post('api/decks/fetch', { plugin: p.id, format: $('#impFormat').value, deck: $('#impDeck').value, options: impOptions() })
    } catch (e) { toast(t('import.err.' + e.message) !== 'import.err.' + e.message ? t('import.err.' + e.message) : e.message); return }
    setView('deck')
    watchDeck()
  }

  async function openDeck(id) {
    imp.deck = await api(`api/decks/${id}`)
    setView('deck')
    if (imp.deck.state === 'running') watchDeck()
  }

  function watchDeck() {
    clearInterval(impPoll)
    impPoll = setInterval(async () => {
      imp.deck = await api(`api/decks/${imp.deck.id}`)
      if (imp.deck.state !== 'running') { clearInterval(impPoll); loadHistory() }
      renderImport()
    }, 1200)
  }

  async function loadHistory() {
    imp.history = await api('api/decks')
    $('#histCount').textContent = imp.history.length ? `(${imp.history.length})` : ''
    if (imp.view === 'history') renderHistory()
  }

  function setView(v) {
    imp.view = v
    renderImport()
  }

  // plugin file names are "<deck index><card name><copy no>"; group the copies back into one tile
  function groupCards(files) {
    const groups = new Map()
    for (const f of files) {
      const m = f.stem.match(/^(\d+)_?(.*?)_?(\d+)$/)
      const key = m ? m[1] + '|' + m[2] : f.stem
      const g = groups.get(key) || { name: m ? m[2] : f.stem, files: [] }
      g.files.push(f)
      groups.set(key, g)
    }
    return [...groups.values()]
  }

  function renderDeckGrid() {
    const d = imp.deck
    const grid = $('#deckGrid')
    grid.textContent = ''
    if (!d) return
    const dsStems = new Set(d.ds.map((f) => f.stem))
    const groups = groupCards(d.front)
    if (!groups.length) grid.innerHTML = `<p class="empty">${t(d.state === 'running' ? 'imp.waiting' : 'cards.none')}</p>`
    for (const g of groups) {
      const f = g.files[0]
      const div = document.createElement('div')
      div.className = 'fc'
      div.innerHTML = `<img alt="" loading="lazy">${g.files.length > 1 ? `<span class="qty">×${g.files.length}</span>` : ''}${g.files.some((x) => dsStems.has(x.stem)) ? `<span class="dsb">${t('imp.statDs')}</span>` : ''}<div class="nm"></div>`
      div.querySelector('img').src = `api/decks/${d.id}/img/front/${encodeURIComponent(f.name)}`
      div.querySelector('.nm').textContent = g.name.replace(/([a-z])([A-Z])/g, '$1 $2')
      div.title = g.name
      grid.append(div)
    }
    const w = d.warnings || []
    $('#warnBox').hidden = !w.length
    $('#warnList').innerHTML = w.map((s) => `<li>${esc(s)}</li>`).join('')
  }

  function renderHistory() {
    const box = $('#view-history')
    box.textContent = ''
    if (!imp.history.length) { box.innerHTML = `<p class="empty">${t('imp.historyEmpty')}</p>`; return }
    for (const h of imp.history) {
      const div = document.createElement('div')
      div.className = 'hist'
      const when = new Date(h.created * 1000).toLocaleString(st.lang === 'th' ? 'th-TH' : 'en-GB', { dateStyle: 'medium', timeStyle: 'short' })
      div.innerHTML = `${h.cover ? '<img alt="" loading="lazy">' : '<span class="ph"></span>'}
        <div class="tx"><div class="t">${abbr(h.plugin)}<span class="gm"></span></div>
          <div class="s">${t('imp.cards', { n: h.count })} · ${esc(h.format)} · ${when}${h.used ? ' · ' + t('imp.used') : ''}</div>
          <div class="s dk"></div></div>
        <div class="acts"><button type="button" class="btn" data-a="open">${t('imp.open')}</button><button type="button" class="btn ghost danger" data-a="del">${t('imp.delete')}</button></div>`
      if (h.cover) div.querySelector('img').src = `api/decks/${h.id}/img/front/${encodeURIComponent(h.cover)}`
      div.querySelector('.gm').textContent = h.game
      div.querySelector('.dk').textContent = (h.deck || '').split('\n').slice(0, 2).join(' · ')
      div.querySelector('[data-a=open]').addEventListener('click', () => openDeck(h.id))
      div.querySelector('[data-a=del]').addEventListener('click', async () => {
        try { await api(`api/decks/${h.id}`, { method: 'DELETE' }) } catch (e) { toast(e.message); return }
        if (imp.deck?.id === h.id) imp.deck = null
        await loadHistory()
        renderImport()
      })
      box.append(div)
    }
  }

  function renderImport() {
    if (!plugins) return
    const v = imp.view === 'deck' && !imp.deck ? 'pick' : imp.view
    $$('[data-view]').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.view === v)))
    $('#resultTab').hidden = !imp.deck
    $('#view-pick').hidden = v !== 'pick'
    $('#view-history').hidden = v !== 'history'
    $('#view-deck').hidden = v !== 'deck'
    $('#gameSearch').hidden = v !== 'pick'
    $('#impForm').hidden = v === 'deck'
    $('#impResult').hidden = v !== 'deck'
    if (v === 'history') renderHistory()
    if (v !== 'deck') return
    const d = imp.deck
    renderDeckGrid()
    const running = d.state === 'running'
    $('#resTitle').textContent = t(running ? 'imp.fetching' : d.state === 'done' ? 'imp.doneTitle' : d.state === 'cancelled' ? 'imp.cancelledTitle' : 'imp.errorTitle')
    $('#resSub').textContent = `${d.game} · ${d.format}${d.took ? ' · ' + t('imp.took', { s: d.took }) : ''}${d.error ? ' · ' + d.error : ''}`
    $('#resProg').className = 'prog ' + d.state
    $('#stCards').textContent = d.front.length
    $('#stKinds').textContent = groupCards(d.front).length
    $('#stDs').textContent = d.ds.length
    $('#stWarn').textContent = (d.warnings || []).length
    const have = st.job?.front.length || 0
    $('#appendHint').textContent = t('imp.appendHint', { n: have })
    $('#impCancel').hidden = !running
    $('#impUse').disabled = running || !d.front.length
    const pre = $('#impLog')
    pre.textContent = (d.log || []).join('\n')
    pre.scrollTop = pre.scrollHeight
  }

  async function useDeck() {
    const mode = $('input[name=useMode]:checked').value
    let r
    try { r = await post(`api/decks/${imp.deck.id}/use`, { job: st.job.id, mode }) } catch (e) { toast(e.message); return }
    st.job = r
    toast(t('imp.added', { n: r.added }))
    loadHistory()
    showWs('create')
    go('cards')
    renderAll()
  }

  function editDeck() {
    const d = imp.deck
    if (d) {
      imp.game = d.plugin
      renderGames()
      renderPlugin()
      $('#impFormat').value = d.format
      $('#impDeck').value = d.deck || ''
      for (const [k, v] of Object.entries(d.options || {})) {
        const el = $('#impOpt-' + k)
        if (!el) continue
        if (el.type === 'checkbox') el.checked = !!v
        else el.value = v
      }
      estimate()
    }
    setView('pick')
  }

  // ------------------------------------------------------------ C. machine setup
  async function renderMachine() {
    const sel = $('#tplPaper')
    if (!sel.options.length) {
      for (const [k, p] of Object.entries(st.opts.papers)) sel.append(new Option(`${label(k)} · ${fmt(p.w)} × ${fmt(p.h)} mm`, k))
      sel.value = st.settings.paper
    }
    const list = await api(`api/templates?paper=${sel.value}`)
    const ul = $('#tplList')
    ul.textContent = ''
    for (const x of list) {
      const li = document.createElement('li')
      const cur = sel.value === st.settings.paper && x.card === st.settings.card && x.borderless === !!st.settings.borderless
      li.innerHTML = `<span class="${cur ? 'cur' : ''}">${cur ? '★ ' : ''}${esc(label(x.card))}${x.borderless ? ' · ' + t('mach.borderless') : ''}<br><code>${esc(x.name)}.studio3</code></span><a download></a>`
      const a = li.querySelector('a')
      a.href = `api/template/${x.name}?borderless=${x.borderless ? 1 : 0}`
      a.textContent = '⬇ .studio3'
      ul.append(li)
    }
  }

  // ------------------------------------------------------------ make
  let poll
  async function generate() {
    if (!st.job.front.length) { toast(t('make.noFronts')); return }
    const s = st.settings
    const body = {
      paper: s.paper, card: s.card, borderless: s.borderless, registration: s.registration, fit: s.fit,
      extendBleed: s.extendBleed.trim(), crop: s.crop.trim(), specialty: s.specialty,
      onlyFronts: $('#onlyFronts').checked, label: $('#label').value.trim(),
      showOutline: $('#showOutline').checked, useOffset: $('#useOffset').checked,
    }
    try { st.job = await post(`api/jobs/${st.job.id}/generate`, body) } catch (e) { toast(e.message); return }
    renderMake()
    clearInterval(poll)
    poll = setInterval(async () => {
      st.job = await api(`api/jobs/${st.job.id}`)
      if (st.job.status.state !== 'running') {
        clearInterval(poll)
        if (st.job.status.state === 'done') traceCuts()
      }
      renderMake()
      renderCut()
    }, 900)
  }

  function renderMake() {
    const s = st.job.status
    const status = $('#makeStatus')
    const btn = $('#generate')
    btn.disabled = s.state === 'running'
    status.className = 'status ' + s.state
    status.textContent = s.state === 'running' ? t('make.running')
      : s.state === 'done' ? t('make.done', { s: s.took, n: st.job.pages.length })
      : s.state === 'error' ? s.error : ''
    const done = st.job.pdf && s.state !== 'running'
    $('#pdfActions').hidden = !done
    const name = `${st.settings.paper}-${st.settings.card}`
    $('#downloadPdf').href = `api/jobs/${st.job.id}/pdf?dl=1&name=${name}`
    $('#openPdf').href = `api/jobs/${st.job.id}/pdf?v=${Date.now()}`
    // PNG sheets carry the real DPI (pHYs) so Silhouette Studio imports them at paper size
    const png = st.job.png
    const f0 = png?.files?.[0]
    $('#pdfInfo').textContent = f0 ? t('make.pdfInfo', { w: f0.mm[0], h: f0.mm[1] }) : ''
    $('#downloadPng').parentElement.hidden = !f0
    $('#downloadStudio').parentElement.hidden = !f0
    if (f0) {
      const v = `v=${s.took}`
      $('#downloadPng').href = `api/jobs/${st.job.id}/png.zip?${v}`
      $('#downloadStudio').href = `api/jobs/${st.job.id}/studio.zip?${v}`
      $('#pngInfo').textContent = t('make.pngInfo', { n: png.files.length, px: `${f0.px[0]} × ${f0.px[1]}`, dpi: png.ppi, w: f0.mm[0], h: f0.mm[1] })
      $('#studioInfo').textContent = png.borderless ? t('make.studioBorderless')
        : png.templateAvailable ? t('make.studioInfo', { tpl: `${png.template}.studio3`, o: t(png.portrait ? 'make.portrait' : 'make.landscape') })
        : t('make.studioNoTpl')
      $('#downloadStudio').hidden = !!png.borderless
    }
    const pages = $('#pages')
    pages.textContent = ''
    if (done) {
      st.job.pages.forEach((p, i) => {
        const fig = document.createElement('figure')
        fig.innerHTML = `<img alt="" loading="lazy"><figcaption></figcaption>`
        fig.querySelector('img').src = `api/jobs/${st.job.id}/page/${p}?v=${s.took}`
        fig.querySelector('figcaption').textContent = `${i + 1} · ${i % 2 ? t('make.back') : t('make.front')}`
        pages.append(fig)
      })
    }
    $('#logBox').hidden = !s.log
    $('#log').textContent = s.log || ''
  }

  // ------------------------------------------------------------ cut & calibration
  function renderCut() {
    const L = st.layout
    const a = $('#downloadTpl')
    const ok = L?.templateAvailable
    a.hidden = !ok
    $('#tplMissing').hidden = !!ok
    if (ok) a.href = `api/template/${L.template}?borderless=${st.settings.borderless && !st.settings.specialty ? 1 : 0}`
    $('#measureText').textContent = t('cut.measure', { w: L ? fmt(L.cardW) : '—' })
    $('#downloadCal').href = `api/calibration/${st.settings.paper}`

    const route = store.get('route', 'pdf')
    $$('input[name=route]').forEach((r) => (r.checked = r.value === route))
    $$('[data-pane=cut] [data-route]').forEach((li) => (li.hidden = li.dataset.route !== route))
    $('#routeHint').textContent = t(route === 'studio' ? 'route.studioHint' : 'route.pdfHint')
    const f0 = st.job?.png?.files?.[0]
    const s2 = $('#downloadStudio2')
    const borderless = !!st.job?.png?.borderless
    s2.hidden = !f0 || borderless
    $('#studioMissing').hidden = !!f0 && !borderless
    $('#studioMissing').textContent = t(borderless ? 'make.studioBorderless' : 'cutS.missing')
    // marks-only sheet: re-feed a front printed without marks; measure the first card's art edge first
    const S = st.settings
    const q = new URLSearchParams({ paper: S.paper, card: S.card, borderless: S.borderless && !S.specialty ? 1 : 0,
      specialty: S.specialty || '', registration: S.registration, kind: 'pdf' })
    $('#downloadMarks').href = `api/marks?${q}`
    if (L) {
      const s0 = L.slots.reduce((a, b) => (b.y < a.y || (b.y === a.y && b.x < a.x) ? b : a))
      const [bx, by] = L.bleed || [0, 0]
      $('[data-i18n="marks.lead"]').textContent = t('marks.lead', { x: fmt(s0.x - bx), y: fmt(s0.y - by) })
      const nm = `${L.paper}-${S.card}${S.borderless && !S.specialty ? '-borderless' : ''}-marks-${S.registration}`
      $('#marksInfo').textContent = t('marks.info', { name: nm })
    }
    // borderless cut files declare a page 13 mm larger than the paper → the sheet sits 6.5 mm in from the grid
    $('#borderlessMat').hidden = !(st.settings.borderless && !st.settings.specialty)
    if (f0) s2.href = `api/jobs/${st.job.id}/studio.zip?v=${st.job.status.took}`
    $('#placeText').textContent = t('cutS.place', { w: f0 ? (f0.studioMm || f0.mm)[0] : '—', h: f0 ? (f0.studioMm || f0.mm)[1] : '—' })
  }

  async function refreshOffset() {
    const o = await api('api/offset')
    $('#offX').value = o.x; $('#offY').value = o.y; $('#offA').value = o.angle
    $('#offEnabled').checked = !!o.enabled
    $('#offsetNow').textContent = o.enabled ? `(x ${o.x}, y ${o.y}, ${o.angle}°)` : ''
    $('#useOffset').disabled = !o.enabled
  }

  async function saveOffset() {
    await post('api/offset', { x: +$('#offX').value || 0, y: +$('#offY').value || 0, angle: +$('#offA').value || 0, enabled: $('#offEnabled').checked })
    $('#offStatus').textContent = t('cal.saved')
    refreshOffset()
  }

  // ------------------------------------------------------------ render all
  function renderAll() {
    if (!st.job || !st.opts) return
    renderCards()
    renderFacts()
    renderStage()
    renderMake()
    renderCut()
    renderImport()
    if (plugins) { renderGames(); renderPlugin() }
    $('[data-bind=cardsCount]').textContent = st.job.front.length ? String(st.job.front.length) : ''
    $('[data-bind=cardsCountStep]').textContent = st.job.front.length ? String(st.job.front.length) : ''
    $('[data-bind=layoutName]').textContent = st.layout ? `${label(st.settings.card)} · ${label(st.settings.paper)}` : ''
    $('[data-bind=makeState]').textContent = st.job.pdf ? 'PDF' : ''
  }

  // ------------------------------------------------------------ boot
  async function boot() {
    $$('[data-lang]').forEach((b) => b.addEventListener('click', () => { st.lang = b.dataset.lang; store.set('lang', st.lang); applyLang() }))
    $$('[data-step]').forEach((b) => b.addEventListener('click', () => go(b.dataset.step)))
    $('#fileFront').addEventListener('change', (e) => { upload('front', [...e.target.files]); e.target.value = '' })
    $('#fileBack').addEventListener('change', (e) => { upload('back', [...e.target.files]); e.target.value = '' })
    bindDrop($('#dropFront'), 'front')
    bindDrop($('#backSlot'), 'back')
    $('#useSample').addEventListener('click', async () => { st.job = await post(`api/jobs/${st.job.id}/sample`); renderAll() })
    $('#clearAll').addEventListener('click', async () => {
      for (const f of [...st.job.front]) await api(`api/jobs/${st.job.id}/files/front/${encodeURIComponent(f.name)}`, { method: 'DELETE' })
      st.job = await api(`api/jobs/${st.job.id}`)
      renderAll()
    })
    ;['paper', 'card', 'borderless', 'registration', 'fit', 'extendBleed', 'crop', 'specialty'].forEach((id) => $('#' + id).addEventListener('change', onSetting))
    $('#generate').addEventListener('click', generate)
    $$('[data-ws]').forEach((b) => b.addEventListener('click', () => showWs(b.dataset.ws)))
    $$('[data-goto]').forEach((b) => b.addEventListener('click', () => showWs(b.dataset.goto)))
    $('#toImport').addEventListener('click', () => showWs('import'))
    $$('[data-view]').forEach((b) => b.addEventListener('click', () => setView(b.dataset.view)))
    $('#gameSearch').addEventListener('input', renderGames)
    $('#impDeck').addEventListener('input', estimate)
    $('#impRun').addEventListener('click', runImport)
    $('#impUse').addEventListener('click', useDeck)
    $('#impEdit').addEventListener('click', editDeck)
    $('#impCancel').addEventListener('click', async () => { imp.deck = await post(`api/decks/${imp.deck.id}/cancel`); renderImport() })
    $('#tplPaper').addEventListener('change', renderMachine)
    $('#saveOffset').addEventListener('click', saveOffset)
    $$('input[name=route]').forEach((r) => r.addEventListener('change', () => { store.set('route', r.value); renderCut() }))
    $('#prevSheet').addEventListener('click', () => { st.sheet = Math.max(0, st.sheet - 1); renderStage() })
    $('#nextSheet').addEventListener('click', () => { st.sheet = Math.min(sheetCount() - 1, st.sheet + 1); renderStage() })

    st.opts = await api('api/options')
    await ensureJob()
    fillSelects()
    await loadLayout()
    applyLang()
    go('cards')
    showWs(store.get('ws', 'create'))
    if (st.job.status.state === 'running') generate()
  }
  boot()
})()
