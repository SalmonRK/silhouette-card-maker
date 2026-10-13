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
      { paper: 'a4', card: 'standard', borderless: false, registration: '3', fit: 'stretch', extendBleed: '', extendCorners: '', extendEdges: '', crop: '', specialty: '' },
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
    $('#frontCount').textContent = t('cards.count', { n: front.length })
    $('#frontCount').hidden = !front.length
    $('#clearAll').hidden = !front.length
    const list = $('#cardList')
    list.textContent = ''
    if (!front.length) {
      const li = document.createElement('li')
      li.className = 'none'
      li.textContent = t('cards.none')
      list.append(li)
    }
    // thumbnails as in the design: number, remove, and "+ own back" / "own back" on each card
    front.forEach((f, i) => {
      const li = document.createElement('li')
      li.className = 'th'
      const own = dsBy[f.stem]
      li.innerHTML = `
        <img alt="" loading="lazy">
        <span class="i">${i + 1}</span>
        <button type="button" class="x" aria-label="${t('cards.remove')} ${esc(f.name)}">${icon('x')}</button>
        <label class="${own ? 'flip' : 'add'}" title="${t('cards.ownBack')}">
          <input type="file" accept="image/*" hidden>${icon(own ? 'flip-horizontal-2' : 'plus')}<span>${t('cards.ownBack')}</span>
        </label>`
      li.querySelector('img').src = img('front', f.name)
      li.title = f.name
      li.querySelector('input').addEventListener('change', (e) => upload('ds', e.target.files, f.name))
      li.querySelector('.x').addEventListener('click', () => remove('front', f.name))
      list.append(li)
    })
    const b = back[0]
    $('#backImg').hidden = !b
    $('#backEmpty').hidden = !!b
    $('#backName').textContent = b ? b.name : t('cards.backNone')
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
  // SRK presets (webui/presets.py) carry their own name in i18n; upstream specialty layouts use the key
  const specialtyLabel = (k) => (I18N.en[`preset.${k}`] ? t(`preset.${k}`) : label(k))

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
    sp.innerHTML = `<option value="">${t('layout.none')}</option>` + specialty.map((s) => `<option value="${s}">${specialtyLabel(s)}</option>`).join('')
    sp.value = st.settings.specialty
    $('#borderless').checked = st.settings.borderless
    $('#registration').value = st.settings.registration
    $('#fit').value = st.settings.fit
    $('#extendBleed').value = st.settings.extendBleed
    $('#extendCorners').value = st.settings.extendCorners
    $('#extendEdges').value = st.settings.extendEdges
    $('#crop').value = st.settings.crop
    renderPaperTiles()
    renderCardTiles(ok)
  }

  // ------------------------------------------------------------ step 2 picture tiles (Figma D2 / D2b)
  // Each tile sets its native control and fires 'change', so onSetting stays the only write path.
  const PAPERS = ['a4', 'letter', 'legal', 'a3', 'tabloid', 'arch_b']
  const FEATURED = ['standard', 'poker', 'japanese', 'bridge', 'tarot', 'mini']
  function setNative(id, value) {
    const n = $('#' + id)
    if (n.value === value) return
    n.value = value
    n.dispatchEvent(new Event('change'))
  }
  function tile(set, val, inner) {
    const b = document.createElement('button')
    b.type = 'button'
    b.className = 'tile'
    b.setAttribute('role', 'radio')
    b.dataset.set = set
    b.dataset.val = val
    b.innerHTML = inner
    return b
  }
  // the sheet's real orientation (borderless A4 is portrait) → "210 × 297", not the paper's stored landscape size
  const portrait = () => (st.layout ? st.layout.pageW < st.layout.pageH : !!st.settings.borderless)
  function renderPaperTiles() {
    const box = $('#paperTiles')
    const papers = st.opts.papers
    const keys = PAPERS.filter((k) => papers[k]).concat(Object.keys(papers).filter((k) => !PAPERS.includes(k)))
    $('#paperCount').textContent = t('layout.paperCount', { n: keys.length })
    box.textContent = ''
    for (const k of keys) {
      const p = papers[k], long = Math.max(p.w, p.h), short = Math.min(p.w, p.h)
      const L = Math.min(44, Math.max(30, 30 + (long - 279) * 0.08)), S = (L * short) / long
      const [pw, ph] = portrait() ? [S, L] : [L, S]
      const [dw, dh] = portrait() ? [short, long] : [long, short]
      box.append(tile('paper', k, `<span class="pict"><i class="paper" style="width:${pw}px;height:${ph}px"></i></span>
        <span class="t">${label(k)}</span><span class="s">${fmt(dw)} × ${fmt(dh)}</span>`))
    }
  }
  function renderCardTiles(ok) {
    const box = $('#cardTiles')
    const cards = st.opts.cards
    box.textContent = ''
    for (const k of FEATURED.filter((k) => ok.has(k) && cards[k])) {
      const c = cards[k], s = Math.min(0.43, 42 / c.h)
      box.append(tile('card', k, `<span class="pict"><i class="card" style="width:${c.w * s}px;height:${c.h * s}px"></i></span>
        <span class="t">${label(k)}</span><span class="s">${fmt(c.w)} × ${fmt(c.h)}</span>`))
    }
  }
  function renderTiles() {
    const s = st.settings
    $$('[data-pane=layout] [data-set]').forEach((b) => b.setAttribute('aria-checked', String(s[b.dataset.set] === b.dataset.val)))
    const L = st.layout
    $('#marksInset').textContent = L ? t('layout.marksInset', { n: fmt(L.registration.inset) }) : ''
    $('#cardCount').textContent = t('layout.cardCount', { n: $('#card').options.length })
  }

  async function loadLayout() {
    const s = st.settings
    const q = new URLSearchParams({ paper: s.paper, card: s.card, borderless: s.borderless ? '1' : '0', specialty: s.specialty })
    try {
      st.layout = await api(`api/layout?${q}`)
      // borderless: also ask how many the normal layout fits, to show what the switch gains (A4 8 → 9)
      st.normalCount = null
      if (s.borderless) {
        q.set('borderless', '0')
        st.normalCount = await api(`api/layout?${q}`).then((n) => n.slots.length, () => null)
      }
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
    if (k === 'extendCorners') delete st.settings.cornersFrom
    store.set('settings', st.settings)
    if (['paper', 'borderless'].includes(k)) fillSelects()
    if (['paper', 'card', 'borderless', 'specialty'].includes(k)) loadLayout()
    else renderAll()
  }

  const perSheet = () => (st.layout ? st.layout.slots.length : 0)
  const sheetCount = () => Math.max(1, Math.ceil((st.job?.front.length || 0) / Math.max(1, perSheet())))

  // facts as chips under the sheet (design: the floating bar on the mat)
  function renderFacts() {
    const L = st.layout
    const box = $('#stageMeta')
    if (!L) { box.textContent = ''; return }
    const r = L.registration
    const chip = (ic, html, title = '', cls = '') => `<span class="fact ${cls}" title="${esc(title)}">${icon(ic)}${html}</span>`
    const gain = gainCount()
    const job = st.job || { front: [], back: [], ds: [] }
    const f0 = job.png?.files?.[0]
    if (st.step === 'cards') {
      box.innerHTML = [
        chip('image', t('cards.factCards', { n: job.front.length })),
        chip('layers', t('layout.factSheets', { n: sheetCount() })),
        chip('flip-horizontal-2', t('cards.factBacks', { b: job.back.length, d: job.ds.length })),
      ].join('')
      return
    }
    if (st.step === 'make' && job.pdf && f0) {
      box.innerHTML = [
        chip('file-text', `PDF <b>${f0.mm[0]} × ${f0.mm[1]}</b> mm`),
        chip('file-image', `PNG <b>${f0.px[0]} × ${f0.px[1]}</b> px · <b>${job.png.ppi}</b> dpi`),
        chip('layers', t('make.factPages', { n: job.pages.length })),
      ].join('')
      return
    }
    if (st.step === 'cut') {
      box.innerHTML = [
        chip('ruler', t('cut.factWidth', { w: fmt(L.cardW) })),
        chip('crosshair', t('cut.factMarks', { n: st.settings.registration })),
        chip('file-text', `<b>${L.templateAvailable ? esc(L.template) + '.studio3' : t('layout.noTemplate')}</b>`),
      ].join('')
      return
    }
    box.innerHTML = [
      chip(L.cols === 3 && L.rows === 3 ? 'grid-3x3' : 'grid-2x2', t('layout.factPerSheet', { n: L.slots.length, c: L.cols, r: L.rows }), t('layout.perSheet')),
      chip('layers', t('layout.factSheets', { n: sheetCount() }), t('layout.sheets')),
      chip('ruler', `<b>${fmt(L.cardW)} × ${fmt(L.cardH)}</b> mm · ${label(L.paper)} ${portrait() ? t('layout.portrait') : t('layout.landscape')}`, t('layout.cardSize')),
      chip('file-text', `<b>${L.templateAvailable ? esc(L.template) + '.studio3' : t('layout.noTemplate')}</b>`,
        `${t('layout.template')} · ${t('layout.marksVal')} ${fmt(r.length)} / ${fmt(r.thickness)} / ${fmt(r.inset)} mm`),
      gain ? chip('trending-up', t('layout.gain', gain), '', 'gain') : '',
    ].join('')
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
    renderFacts()
  }

  // borderless only matters when it fits more cards; null when off or no gain
  function gainCount() {
    const L = st.layout, from = st.normalCount
    return st.settings.borderless && L && from && L.slots.length > from ? { from, n: L.slots.length } : null
  }

  function renderBorderless() {
    const L = st.layout, on = st.settings.borderless && L, gain = gainCount()
    const inset = L ? fmt(L.registration.inset) : ''
    $('#borderlessHint').textContent = on && gain ? t('layout.borderlessOn', { inset, ...gain }) : t('layout.borderlessHint')
    $('#borderlessNote').hidden = !on
    if (on) $('#borderlessText').innerHTML = t('layout.borderlessNote', { inset })
    $('#cornersFrom').hidden = !(st.settings.cornersFrom && st.settings.extendCorners)
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
    $('#impOptSub').textContent = p.options.length ? t('imp.optCount', { n: p.options.length }) : t('imp.noOptions')
    for (const o of p.options) {
      const id = 'impOpt-' + o.name
      const wrap = document.createElement(o.kind === 'flag' ? 'label' : 'div')
      if (o.kind === 'flag') {
        wrap.className = 'switch-line opt-flag'
        wrap.innerHTML = `<span></span><input type="checkbox" id="${id}" role="switch" class="switch">`
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
    // Scryfall images have rounded corners and no bleed: fill the corners unless the user already chose a value
    const corners = imp.deck.plugin === 'mtg' && !st.settings.extendCorners
    if (corners) {
      st.settings.extendCorners = '3.5mm'
      st.settings.cornersFrom = 'mtg'
      store.set('settings', st.settings)
      $('#extendCorners').value = st.settings.extendCorners
    }
    toast(t('imp.added', { n: r.added }) + (corners ? ' · ' + t('imp.cornersOn') : ''))
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
    $('#tplCount').textContent = t('mach.files', { n: list.length })
    // file rows as in the design; the size in use comes first and is highlighted
    const isCur = (x) => sel.value === st.settings.paper && x.card === st.settings.card && x.borderless === !!st.settings.borderless
    for (const x of [...list.filter(isCur), ...list.filter((x) => !isCur(x))]) {
      const li = document.createElement('li')
      const cur = isCur(x)
      const c = st.opts.cards[x.card]
      li.className = 'file' + (cur ? ' rec' : '')
      li.innerHTML = `<span class="fi">${icon('file-down')}</span>
        <span class="tx"><span class="t">${esc(label(x.card))}${c ? ` <small>${fmt(c.w)} × ${fmt(c.h)}</small>` : ''}${x.borderless ? ` <span class="pill">${t('mach.borderless')}</span>` : ''}${cur ? ` <span class="pill ref">${t('mach.inUse')}</span>` : ''}</span>
        <code>${esc(x.name)}.studio3</code></span>
        <a class="btn sm ${cur ? 'cut' : 'ghost'}" download aria-label="${t('mach.download')} ${esc(x.name)}.studio3">${icon('download')}</a>`
      li.querySelector('a').href = `api/template/${x.name}?borderless=${x.borderless ? 1 : 0}`
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
      extendBleed: s.extendBleed.trim(), extendCorners: s.extendCorners.trim(), extendEdges: s.extendEdges.trim(), crop: s.crop.trim(), specialty: s.specialty,
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
    // result banner (design: green "made in 2.2 s" with the page count)
    status.className = 'status ' + s.state
    status.hidden = !['running', 'done', 'error'].includes(s.state)
    $('#makeStatusT').textContent = s.state === 'running' ? t('make.running')
      : s.state === 'done' ? t('make.doneT', { s: s.took }) : s.state === 'error' ? t('make.errorT') : ''
    $('#makeStatusS').textContent = s.state === 'done' ? t('make.doneS', { n: st.job.pages.length })
      : s.state === 'error' ? s.error || '' : ''
    $('#generate span').textContent = t(s.state === 'done' ? 'make.again' : 'make.go')
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
      const pdfOnly = png.pdfOnly ?? png.borderless
      $('#studioInfo').textContent = pdfOnly ? t(png.matOffset ? 'make.studioPreset' : 'make.studioBorderless')
        : png.templateAvailable ? t('make.studioInfo', { tpl: `${png.template}.studio3`, o: t(png.portrait ? 'make.portrait' : 'make.landscape') })
        : t('make.studioNoTpl')
      $('#downloadStudio').hidden = !!pdfOnly
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
    if (st.layout) renderFacts()
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
    $('#tplName').textContent = ok ? `${L.template}.studio3` : t('cut.tpl')
    // SRK preset: upstream has no cut file → hand out the DXF to build one in Studio (once)
    const dxf = $('#downloadPresetDxf')
    dxf.hidden = !L?.preset
    if (L?.preset) dxf.href = `api/preset/${st.settings.specialty}.dxf`
    $('#tplMissing').textContent = L?.preset && !ok ? t('cut.presetTpl', { tpl: `${L.template}.studio3` }) : t('cut.tplMissing')
    $('#measureText').textContent = t('cut.measure', { w: L ? fmt(L.cardW) : '—' })
    $('#downloadCal').href = `api/calibration/${st.settings.paper}`

    const route = store.get('route', 'pdf')
    $$('input[name=route]').forEach((r) => (r.checked = r.value === route))
    $$('[data-pane=cut] [data-route]').forEach((li) => (li.hidden = li.dataset.route !== route))
    $('#routeHint').textContent = t(route === 'studio' ? 'route.studioHint' : 'route.pdfHint')
    const f0 = st.job?.png?.files?.[0]
    const s2 = $('#downloadStudio2')
    const png = st.job?.png
    const borderless = !!(png?.pdfOnly ?? png?.borderless)
    s2.hidden = !f0 || borderless
    $('#studioMissing').hidden = !!f0 && !borderless
    $('#studioMissing').textContent = t(!borderless ? 'cutS.missing' : png?.matOffset ? 'make.studioPreset' : 'make.studioBorderless')
    // marks-only sheet: re-feed a front printed without marks; measure the first card's art edge first
    const S = st.settings
    const q = new URLSearchParams({ paper: S.paper, card: S.card, borderless: S.borderless && !S.specialty ? 1 : 0,
      specialty: S.specialty || '', registration: S.registration, kind: 'pdf' })
    $('#downloadMarks').href = `api/marks?${q}`
    if (L) {
      const s0 = L.slots.reduce((a, b) => (b.y < a.y || (b.y === a.y && b.x < a.x) ? b : a))
      const [bx, by] = L.bleed || [0, 0]
      $('[data-i18n="marks.lead"]').textContent = t('marks.lead', { x: fmt(s0.x - bx), y: fmt(s0.y - by) })
      const nm = `${L.preset ? S.specialty : `${L.paper}-${S.card}${S.borderless && !S.specialty ? '-borderless' : ''}`}-marks-${S.registration}`
      $('#marksInfo').textContent = t('marks.info', { name: nm })
    }
    // borderless cut files declare a page 13 mm larger than the paper → the sheet sits 6.5 mm in from the grid
    // SRK presets with marks under 10 mm use the same trick with their own offset
    const mat = $('#borderlessMat')
    mat.hidden = !((st.settings.borderless && !st.settings.specialty) || L?.matOffset)
    $('#borderlessMatText').textContent = L?.matOffset
      ? t('cut.presetMat', { o: fmt(L.matOffset), w: Math.round(L.pageW + 2 * L.matOffset), h: Math.round(L.pageH + 2 * L.matOffset), inset: fmt(L.registration.inset) })
      : t('cut.borderlessMat')
    if (f0) s2.href = `api/jobs/${st.job.id}/studio.zip?v=${st.job.status.took}`
    $('#placeText').textContent = t('cutS.place', { w: f0 ? (f0.studioMm || f0.mm)[0] : '—', h: f0 ? (f0.studioMm || f0.mm)[1] : '—' })
  }

  async function refreshOffset() {
    const o = await api('api/offset')
    $('#offX').value = o.x; $('#offY').value = o.y; $('#offA').value = o.angle
    $('#offEnabled').checked = !!o.enabled
    $('#offsetNow').textContent = o.enabled ? `X ${o.x} · Y ${o.y} · ${o.angle}°` : t('make.offsetOff')
    // no saved offset → the switch reads off and is locked; it comes back on once an offset is saved
    const u = $('#useOffset')
    if (!o.enabled) u.checked = false
    else if (u.disabled) u.checked = true
    u.disabled = !o.enabled
    $('#calState').hidden = !o.enabled
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
    renderPaperTiles()
    renderTiles()
    renderBorderless()
    renderStage()
    renderMake()
    renderCut()
    renderImport()
    if (plugins) { renderGames(); renderPlugin() }
    $('[data-bind=cardsCount]').textContent = st.job.front.length ? String(st.job.front.length) : ''
    $('[data-bind=cardsCountStep]').textContent = st.job.front.length ? String(st.job.front.length) : ''
    $('[data-bind=layoutName]').textContent = st.layout ? `${label(st.settings.card)} · ${label(st.settings.paper)}${st.settings.borderless ? ' · ' + t('layout.borderlessShort') : ''}` : ''
    $('[data-bind=makeState]').textContent = st.job.pdf ? 'PDF' : ''
  }

  // ------------------------------------------------------------ boot
  async function boot() {
    fillIcons()
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
    ;['paper', 'card', 'borderless', 'registration', 'fit', 'extendBleed', 'extendCorners', 'extendEdges', 'crop', 'specialty'].forEach((id) => $('#' + id).addEventListener('change', onSetting))
    $('[data-pane=layout]').addEventListener('click', (e) => {
      const b = e.target.closest('button[data-set]')
      if (b) setNative(b.dataset.set, b.dataset.val)
    })
    $$('[data-next]').forEach((b) => b.addEventListener('click', () => go(b.dataset.next)))
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
