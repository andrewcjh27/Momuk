/* momuk-app.js — flow controller
   Landing → Q1 (party) → Q2 (hunger) → Q3 (budget) → thinking → response.
   The engine (momuk-engine.js) does the deciding; this file only gathers
   context, sequences the screens, and renders the result. */

(function () {
  'use strict';

  var $ = function (s) { return document.querySelector(s); };
  var $$ = function (s) { return [].slice.call(document.querySelectorAll(s)); };

  // ── copy ───────────────────────────────────────────────
  var S = {
    ko: {
      start: '시작하기', next: '다음', suggest: '추천받기', skip: '넘기기',
      q1: '몇 명이야?', q2: '얼마나 배고파?', q3: '가격 범위는?',
      q2lo: '가볍게', q2hi: '든든하게', q3lo: '저렴하게', q3hi: '상관없어',
      people: ['혼자', '둘이서', '셋이서', '넷 이상'],
      peopleSub: ['혼밥도 좋죠', '', '', '나눠 먹기 좋게'],
      hunger: function (v) {
        return v <= 2 ? '아주 가볍게' : v <= 4 ? '가볍게' : v <= 6 ? '적당히'
             : v <= 8 ? '든든하게' : '아주 든든하게';
      },
      budget: ['₩10,000 이하', '₩10,000 – 20,000', '상관없어'],
      lead: '내 추천은…', accept: '이걸로!', again: '음… 안 땡겨!',
      restart: '다시 고르기', doneNote: '맛있게 드세요',
      locating: '위치 확인 중…',
      weather: function (t, p, where) { return (where ? '<b>' + where + '</b> · ' : '') + '체감 <b>' + t + '°C</b> · 미세먼지 <b>' + p + '</b>'; },
      noloc: '위치 없이 전국 기준으로 고를게요',
      skipLoc: '위치 없이 고르기', useLoc: '내 위치 쓰기',
      empty: '조건에 맞는 게 없어요. 가격대를 바꿔볼까요?',
      allShown: '맞는 메뉴는 다 보여드렸어요. 조건을 바꿔볼까요?',
      changeAnswers: '조건 바꾸기',
      relaxedPrice: '이 가격대는 다 봤어요 — 다른 가격대에서 골라봤어요',
      askLoc: '시작하면 날씨를 보려고 위치를 물어볼게요',
      refineLead: function (n) { return n + '개 다 별로였구나 — 좀 더 좁혀볼게'; },
      refine: {
        spice:   { ask: '매운 거 땡겨?', options: [['hot', '맵게'], ['mild', '안 맵게']] },
        base:    { ask: '뭐가 땡겨?', options: [['rice', '밥'], ['noodle', '면'], ['bread', '빵'], ['meat', '고기']] },
        novelty: { ask: '새로운 거, 익숙한 거?', options: [['new', '새로운 거'], ['familiar', '익숙한 거']] },
        soup:    { ask: '국물 있는 거?', options: [['yes', '국물 있게'], ['no', '국물 없이']] },
        speed:   { ask: '빨리 먹을 거?', options: [['fast', '빨리'], ['slow', '여유 있게']] },
        any: '상관없어'
      },
      think: {
        loc: '지금 날씨를 보는 중…', national: '전국 기준으로 보는 중…',
        weather: function (t, r) { return '체감 ' + t + '°C' + (r > 0.2 ? ', 비가 오네요' : ''); },
        slot: { breakfast: '아침 메뉴 중에서', lunch: '점심 메뉴 중에서', dinner: '저녁 메뉴 중에서', late: '야식 중에서' },
        count: function (n) { return n + '개를 추려보는 중…'; }
      }
    },
    en: {
      start: 'Start', next: 'Next', suggest: 'Suggest', skip: 'Skip',
      q1: 'How many people?', q2: 'How hungry?', q3: 'Price range?',
      q2lo: 'Light', q2hi: 'Heavy', q3lo: 'Cheap', q3hi: "Doesn't matter",
      people: ['Just me', 'Two', 'Three', 'Four or more'],
      peopleSub: ['Solo is good', '', '', 'Something to share'],
      hunger: function (v) {
        return v <= 2 ? 'Barely peckish' : v <= 4 ? 'Light' : v <= 6 ? 'Middling'
             : v <= 8 ? 'Properly hungry' : 'Starving';
      },
      budget: ['Under ₩10,000', '₩10,000 – 20,000', "Doesn't matter"],
      lead: 'How about…', accept: "Let's go", again: 'Eh… give me another',
      restart: 'Start over', doneNote: 'Enjoy',
      locating: 'Finding you…',
      weather: function (t, p, where) { return (where ? '<b>' + where + '</b> · ' : '') + 'Feels <b>' + t + '°C</b> · PM2.5 <b>' + p + '</b>'; },
      noloc: 'No location — going on nationwide patterns',
      skipLoc: 'Skip location', useLoc: 'Use my location',
      empty: 'Nothing fits. Try another price range?',
      allShown: "That's every dish that fits. Change an answer?",
      changeAnswers: 'Change my answers',
      relaxedPrice: "That's every dish in your price range — here's one from another",
      askLoc: "We'll ask for your location when you start, to check the weather",
      refineLead: function (n) { return 'None of those ' + n + ' — let me narrow it down'; },
      refine: {
        spice:   { ask: 'Spicy?', options: [['hot', 'Spicy'], ['mild', 'Not spicy']] },
        base:    { ask: 'What kind?', options: [['rice', 'Rice'], ['noodle', 'Noodles'], ['bread', 'Bread'], ['meat', 'Meat']] },
        novelty: { ask: 'Something new, or something familiar?', options: [['new', 'Something new'], ['familiar', 'Something familiar']] },
        soup:    { ask: 'Something with broth?', options: [['yes', 'With broth'], ['no', 'No broth']] },
        speed:   { ask: 'In a hurry?', options: [['fast', 'Quick'], ['slow', 'Take my time']] },
        any: "Doesn't matter"
      },
      think: {
        loc: 'Checking the weather…', national: 'Going on nationwide patterns…',
        weather: function (t, r) { return 'Feels ' + t + '°C' + (r > 0.2 ? ', and raining' : ''); },
        slot: { breakfast: 'Among breakfast dishes', lunch: 'Among lunch dishes', dinner: 'Among dinner dishes', late: 'Among late-night dishes' },
        count: function (n) { return 'Narrowing ' + n + ' down…'; }
      }
    }
  };

  var lang = (localStorage.getItem('momuk.lang') || 'ko');

  // ── engine ─────────────────────────────────────────────
  // v2 scores on what the data pipeline measured (data/momuk-model.json, refreshed weekly).
  // If that file can't be loaded, v1's hand-weighted rules still give an answer.
  var engine = function () { return window.MOMUK_MODEL ? window.MomukV2 : window.Momuk; };
  var dishCount = function () { return window.MOMUK_MODEL ? window.MOMUK_MODEL.dishes.length : window.MOMUK_DATA.length; };
  fetch('data/momuk-model.json', { cache: 'no-cache' })
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (m) { window.MOMUK_MODEL = m; renderStatus(statusKind); })
    .catch(function () { /* stay on v1 */ });
  var t = function () { return S[lang]; };

  // ── state ──────────────────────────────────────────────
  var state = {
    party: 1, hunger: 5, budget: 2,
    weather: { hasWeather: false },
    useLocation: true,         // false once the person picks "위치 없이 고르기"
    locating: false,
    recent: JSON.parse(localStorage.getItem('momuk.recent') || '[]'),
    rejected: [],              // dishes turned down with "안 땡겨" since the last answers
    prefs: {},                 // answers to the narrowing questions this round
    asked: 0,                  // how many narrowing questions this round
    locAsked: false,
    last: null
  };

  var ORDER = ['landing', 'q1', 'q2', 'q3', 'thinking', 'response', 'done'];
  var current = 'landing';
  var answered = 0;          // drives the bowl fill
  var DEBUG = /[?&]debug=1/.test(location.search);
  // The reason chips under the dish are hidden for now (decided 2026-11-22). The engine still
  // computes them; ?debug=1 shows the full breakdown, and flipping this brings them back.
  var SHOW_REASONS = false;

  // ── screens ────────────────────────────────────────────
  function show(name) {
    var from = $('#s-' + current);
    var to = $('#s-' + name);
    if (from && from !== to) {
      from.classList.add('is-leaving');
      from.classList.remove('is-active');
      setTimeout(function () { from.classList.remove('is-leaving'); }, 340);
    }
    to.classList.add('is-active');
    current = name;

    $('#bowlDock').classList.toggle('is-centred', name === 'landing');
    $('#bowl').classList.toggle('is-steaming', name === 'response' || name === 'done');

    // replay entrance animations on the screen we just moved to
    to.querySelectorAll('.enter, .reveal').forEach(function (el) {
      el.style.animation = 'none';
      void el.offsetWidth;
      el.style.animation = '';
    });
  }

  function setProgress(n) {
    answered = Math.max(0, Math.min(3, n));
    // liquid rect is 52 tall; translate it down by the empty fraction
    $('#bowlFill').setAttribute('transform', 'translate(0 ' + (52 * (1 - answered / 3)) + ')');
  }

  // ── weather: keyless, straight from the browser ────────
  var statusKind = '';
  function renderStatus(kind) {
    statusKind = kind;
    var el = $('#status'), w = state.weather;
    if (kind === 'weather' && w.hasWeather) {
      var p = window.MOMUK_MODEL && window.MomukV2.nearestProvince(window.MOMUK_MODEL, w.lat, w.lon);
      el.innerHTML = t().weather(Math.round(w.feelsC), Math.round(w.pm25), p ? p[lang] : '');
    } else if (kind) {
      el.textContent = t()[kind];
    }
    // The person can always choose: skip location while it's being found, or turn it back on.
    var action = kind === 'locating' || kind === 'askLoc' ? 'skipLoc'
               : kind === 'noloc' && navigator.geolocation ? 'useLoc' : null;
    if (action) {
      var b = document.createElement('button');
      b.className = 'linkbtn status__act';
      b.textContent = t()[action];
      b.addEventListener('click', action === 'skipLoc' ? skipLocation : function () {
        state.useLocation = true; loadWeather();
      });
      el.appendChild(document.createTextNode(' · '));
      el.appendChild(b);
    }
  }

  // Without location the engine uses only nationwide signals — popularity, meal time, weekend,
  // food days. No local weather and no regional lean (v2 leaves both out when there's no position).
  function skipLocation() {
    state.useLocation = false;
    state.locating = false;
    state.weather = { hasWeather: false };
    renderStatus('noloc');
  }

  var locRun = 0;
  function loadWeather() {
    if (!navigator.geolocation) { renderStatus('noloc'); return; }
    var run = ++locRun;                    // a later run, or "위치 없이 고르기", makes this one stale
    var live = function () { return run === locRun && state.useLocation; };
    state.locating = true;
    renderStatus('locating');

    var settled = false;
    var giveUp = setTimeout(function () {
      if (!settled && live()) { settled = true; state.locating = false; renderStatus('noloc'); }
    }, 9000);
    var done = function (kind) {
      if (settled || !live()) return;
      settled = true; clearTimeout(giveUp); state.locating = false; renderStatus(kind);
    };

    navigator.geolocation.getCurrentPosition(function (pos) {
      var la = pos.coords.latitude.toFixed(3), lo = pos.coords.longitude.toFixed(3);
      Promise.all([
        fetch('https://api.open-meteo.com/v1/forecast?latitude=' + la + '&longitude=' + lo +
              '&current=temperature_2m,apparent_temperature,precipitation,relative_humidity_2m' +
              '&daily=temperature_2m_mean,rain_sum&timezone=auto&forecast_days=1')
          .then(function (r) { return r.json(); }),
        fetch('https://air-quality-api.open-meteo.com/v1/air-quality?latitude=' + la +
              '&longitude=' + lo + '&current=pm2_5')
          .then(function (r) { return r.json(); }).catch(function () { return null; })
      ]).then(function (res) {
        if (!live()) return;               // they chose to go without location meanwhile
        var c = res[0].current, day = res[0].daily || {};
        state.weather = {
          hasWeather: true,
          lat: +la, lon: +lo,
          tempMeanC: day.temperature_2m_mean ? day.temperature_2m_mean[0] : null,   // the pipeline bins daily means
          rainTodayMm: day.rain_sum ? day.rain_sum[0] : null,
          tempC: c.temperature_2m,
          feelsC: c.apparent_temperature,
          rainMm: c.precipitation,
          humidity: c.relative_humidity_2m,
          pm25: res[1] && res[1].current ? res[1].current.pm2_5 : 15
        };
        done('weather');
      }).catch(function () { done('noloc'); });
    }, function () { done('noloc'); }, { timeout: 8000, maximumAge: 600000 });
  }

  // ── the thinking beat ──────────────────────────────────
  // Not a spinner: it shows the signals actually landing, which is the
  // only honest way to buy time and the cheapest way to look intelligent.
  function think(after) {
    var box = $('#thinkingLines');
    box.innerHTML = '';
    var w = state.weather;
    var ctx = engine().buildContext(inputs());
    var lines = [
      w.hasWeather ? t().think.weather(Math.round(w.feelsC), w.rainMm)
                   : state.locating ? t().think.loc : t().think.national,
      t().think.slot[ctx.slot],
      t().think.count(dishCount())
    ];
    lines.forEach(function (text, i) {
      var p = document.createElement('p');
      p.className = 'thinking__line';
      p.textContent = text;
      p.style.animationDelay = (i * 380) + 'ms';
      box.appendChild(p);
    });
    setTimeout(after, 1500);
  }

  // ── suggesting ─────────────────────────────────────────
  function inputs() {
    var w = state.weather;
    return {
      feelsC: w.feelsC, tempC: w.tempC, rainMm: w.rainMm,
      tempMeanC: w.tempMeanC, rainTodayMm: w.rainTodayMm, lat: w.lat, lon: w.lon,
      humidity: w.humidity, pm25: w.pm25, hasWeather: w.hasWeather,
      hunger: state.hunger, budget: state.budget, party: state.party,
      recent: state.recent,
      exclude: state.rejected,
      prefs: state.prefs
    };
  }

  function suggest() {
    var out = engine().suggest(inputs(), { lang: lang });
    if (!out.picked) { showExhausted(state.rejected.length ? t().allShown : t().empty); return; }
    state.last = out;

    var d = out.picked.dish;
    $('#answerLead').textContent = out.relaxed === 'price' ? t().relaxedPrice : t().lead;
    $('#dish').textContent = lang === 'en' ? d.en : d.ko;
    $('#dishEn').textContent = lang === 'en' ? d.ko : d.en;

    var why = $('#why');
    why.innerHTML = '';
    why.hidden = !SHOW_REASONS;
    if (SHOW_REASONS) out.why.forEach(function (w, i) {
      var li = document.createElement('li');
      li.className = 'reveal' + (w.folklore ? ' is-folk' : '');
      li.style.setProperty('--i', 3 + i);
      li.textContent = w.text;
      if (w.folklore) li.title = lang === 'en'
        ? 'a folk heuristic — being tested against real choices'
        : '속설에 기반한 이유 — 실제 선택으로 검증 중';
      if (w.measured) li.title = lang === 'en'
        ? 'measured from ten years of Naver searches and weather'
        : '10년간의 네이버 검색과 날씨 데이터로 측정한 값';
      why.appendChild(li);
    });

    if (DEBUG) renderDebug(out);
    show('response');
  }

  // ── narrowing questions ────────────────────────────────
  var REFINE = ['spice', 'base', 'novelty', 'soup', 'speed'];   // one per three "안 땡겨", in a random order each round
  state.prefOrder = [];

  function shuffled(list) {
    var a = list.slice();
    for (var i = a.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1)), tmp = a[i]; a[i] = a[j]; a[j] = tmp;
    }
    return a;
  }

  function newRound() {
    state.rejected = []; state.prefs = {}; state.prefOrder = []; state.asked = 0;
    state.refineOrder = shuffled(REFINE);
  }
  newRound();

  // The next question this round that the data can answer (skips ones the model file can't).
  function nextRefine() {
    var order = state.refineOrder;
    while (state.asked < order.length && !window.MomukV2.canAsk(order[state.asked])) state.asked++;
    return state.asked < order.length;
  }

  function askRefine() {
    $('#refineSkip').hidden = false;
    var key = state.refineOrder[state.asked++];
    var q = t().refine[key];
    $('#refineLead').textContent = t().refineLead(state.rejected.length);
    $('#refineAsk').textContent = q.ask;
    var box = $('#refineOptions');
    box.innerHTML = '';
    q.options.concat([[null, t().refine.any]]).forEach(function (opt, i) {
      var b = document.createElement('button');
      b.className = 'pill enter';
      b.style.setProperty('--i', i + 1);
      b.innerHTML = '<span>' + opt[1] + '</span>';
      b.addEventListener('click', function () { answerRefine(key, opt[0]); });
      box.appendChild(b);
    });
    show('refine');
  }

  function answerRefine(key, value) {
    if (value) { state.prefs[key] = value; state.prefOrder.push(key); }
    show('thinking');
    think(suggest);
  }

  $('#refineSkip').addEventListener('click', function () { answerRefine(null, null); });

  // Nothing left that fits every answer: say so plainly, on the same screen as the questions,
  // and offer to change the answers (no answer is quietly loosened).
  function showExhausted(message) {
    $('#refineLead').textContent = '';
    $('#refineAsk').textContent = message;
    var box = $('#refineOptions');
    box.innerHTML = '';
    var b = document.createElement('button');
    b.className = 'pill enter';
    b.style.setProperty('--i', 1);
    b.innerHTML = '<span>' + t().changeAnswers + '</span>';
    b.addEventListener('click', function () { setProgress(0); show('q1'); });
    box.appendChild(b);
    $('#refineSkip').hidden = true;
    show('refine');
  }

  // ── wiring ─────────────────────────────────────────────
  function buildOptions() {
    var box = $('#q1Options');
    box.innerHTML = '';
    [1, 2, 3, 4].forEach(function (n, i) {
      var b = document.createElement('button');
      b.className = 'pill enter';
      b.style.setProperty('--i', i + 1);
      b.innerHTML = '<span>' + t().people[i] + '</span>' +
        (t().peopleSub[i] ? '<span class="pill__sub">' + t().peopleSub[i] + '</span>' : '');
      b.addEventListener('click', function () {
        state.party = n;
        $$('#q1Options .pill').forEach(function (p) { p.classList.remove('is-chosen'); });
        b.classList.add('is-chosen');
        setProgress(1);
        setTimeout(function () { show('q2'); }, 200);
      });
      box.appendChild(b);
    });
  }

  // Show the value, not just the word — the word duplicates the track's end label.
  function readHunger() {
    $('#hungerRead').textContent = state.hunger + ' / 10 · ' + t().hunger(state.hunger);
  }
  function readBudget() { $('#budgetRead').textContent = t().budget[state.budget - 1]; }

  function applyLang() {
    $('#langKo').setAttribute('aria-pressed', String(lang === 'ko'));
    $('#langEn').setAttribute('aria-pressed', String(lang === 'en'));
    document.documentElement.lang = lang;
    localStorage.setItem('momuk.lang', lang);

    $('#start').textContent = t().start;
    $('#q1Ask').textContent = t().q1;
    $('#q2Ask').textContent = t().q2;
    $('#q3Ask').textContent = t().q3;
    $('#q2Lo').textContent = t().q2lo; $('#q2Hi').textContent = t().q2hi;
    $('#q3Lo').textContent = t().q3lo; $('#q3Hi').textContent = t().q3hi;
    $('#accept').textContent = t().accept;
    $('#again').textContent = t().again;
    $('#restart').textContent = t().restart;
    $$('[data-skip]').forEach(function (b) { b.textContent = t().skip; });
    $('#refineSkip').textContent = t().skip;
    $('#s-q2 [data-next]').textContent = t().next;
    $('#s-q3 [data-next]').textContent = t().suggest;
    buildOptions(); readHunger(); readBudget();
    if (state.last) { $('#answerLead').textContent = t().lead; }
    renderStatus(statusKind);
  }

  $('#langKo').addEventListener('click', function () { lang = 'ko'; applyLang(); });
  $('#langEn').addEventListener('click', function () { lang = 'en'; applyLang(); });

  $('#start').addEventListener('click', function () {
    if (!state.locAsked && state.useLocation) { state.locAsked = true; loadWeather(); }
    show('q1');
  });

  $('#hunger').addEventListener('input', function () {
    state.hunger = +this.value; readHunger();
  });
  $('#budget').addEventListener('input', function () {
    state.budget = +this.value; readBudget();
  });

  $('#s-q2 [data-next]').addEventListener('click', function () {
    setProgress(2); show('q3');
  });
  $('#s-q3 [data-next]').addEventListener('click', function () {
    newRound();
    setProgress(3); show('thinking'); think(suggest);
  });

  $$('[data-skip]').forEach(function (b) {
    b.addEventListener('click', function () {
      var i = ORDER.indexOf(current);
      setProgress(i);                       // skipping still advances the bowl
      if (current === 'q3') { newRound(); show('thinking'); think(suggest); }
      else show(ORDER[i + 1]);
    });
  });

  $$('[data-back]').forEach(function (b) {
    b.addEventListener('click', function () {
      var i = ORDER.indexOf(current);
      var prev = current === 'response' ? 'q3' : ORDER[i - 1];
      setProgress(ORDER.indexOf(prev) - 1);
      show(prev);
    });
  });

  $('#again').addEventListener('click', function () {
    // "음… 안 땡겨!" — that dish is out for the rest of this round, so the next pick is always new.
    if (state.last && state.last.picked) state.rejected.push(state.last.picked.dish.id);
    // After every third "안 땡겨", ask one narrowing question before the next pick
    // (only with the measured model, which knows spice, base and how common each dish is).
    if (window.MOMUK_MODEL && state.rejected.length % 3 === 0 && nextRefine()) {
      askRefine(); return;
    }
    show('thinking');
    think(suggest);
  });

  $('#accept').addEventListener('click', function () {
    if (!state.last) return;
    var d = state.last.picked.dish;
    state.recent.unshift(d.id);
    state.recent = state.recent.slice(0, 7);
    localStorage.setItem('momuk.recent', JSON.stringify(state.recent));
    // v2: POST {context, shown, accepted} to a log endpoint here.
    $('#doneDish').textContent = lang === 'en' ? d.en : d.ko;
    $('#doneNote').textContent = t().doneNote;
    show('done');
  });

  $('#restart').addEventListener('click', function () {
    setProgress(0);
    show('landing');
  });

  // ── debug (?debug=1) ───────────────────────────────────
  function renderDebug(out) {
    var el = document.getElementById('debugPanel');
    if (!el) {
      el = document.createElement('div');
      el.id = 'debugPanel'; el.className = 'debug';
      document.body.appendChild(el);
    }
    var top = out.ranked.slice(0, 8).map(function (r, i) {
      return '<tr><td>' + (i + 1) + '</td><td>' + r.dish.ko + '</td><td class="n">' + r.score.toFixed(2) + '</td></tr>';
    }).join('');
    var parts = out.picked.parts.filter(function (p) { return Math.abs(p.contrib) > 0.01; })
      .sort(function (a, b) { return b.contrib - a.contrib; })
      .map(function (p) {
        return '<tr><td>' + p.key + (p.folklore ? ' *' : '') + '</td><td class="n">' + p.v.toFixed(2) +
               '</td><td class="n">×' + p.w + '</td><td class="n' + (p.contrib < 0 ? ' neg' : '') + '">' +
               p.contrib.toFixed(2) + '</td></tr>';
      }).join('');
    el.innerHTML = '<table><tr><th>#</th><th>top of ' + out.ranked.length + '</th><th class="n">score</th></tr>' +
      top + '</table><table><tr><th>term</th><th class="n">f</th><th class="n">w</th><th class="n">contrib</th></tr>' +
      parts + '</table><p>p(pick) = ' + (out.p * 100).toFixed(1) + '% · * = folk heuristic</p>';
  }

  // ── go ─────────────────────────────────────────────────
  applyLang();
  setProgress(0);
  renderStatus(navigator.geolocation ? 'askLoc' : 'noloc');
})();
