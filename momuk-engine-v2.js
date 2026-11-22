// momuk-engine-v2.js — the measured engine
//
// v1 (momuk-engine.js) scored dishes with hand-set weights on folklore rules.
// v2 replaces the guessed rules with what the data pipeline measured from ten
// years of Naver searches and weather (data/momuk-model.json, refreshed weekly):
//
//   score(dish) = log( √popularity × rain × temperature × region
//                      × meal time × weekend × food day )      ← measured
//               + hunger + party + fine dust + recently eaten   ← kept from v1
//   P(dish)     = softmax(score / τ) over the top N             ← kept from v1
//   why         = the largest positive terms, with their real multipliers
//
// Working in log space turns the pipeline's multipliers into additive terms,
// so each one is a contribution the explanation can rank, exactly like v1.
// Budget and solo/sharing are filters, as decided in DECISIONS.md.

(function (global) {
  'use strict';

  var clamp = function (v, lo, hi) { return Math.max(lo, Math.min(hi, v)); };
  var ln = Math.log;
  var OFF_MEAL = 0.3;          // same as notebook 02: a dish off its meal keeps 30% of its score
  var CHIP_MIN = ln(1.15);     // a measured effect needs at least ×1.15 to be named as a reason

  var x = function (m) { return '×' + (m >= 10 ? Math.round(m) : (Math.round(m * 10) / 10).toFixed(1)); };

  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function isoDate(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }

  // Nearest of the 17 province points; null when the user is not in Korea.
  function nearestProvince(model, lat, lon) {
    if (lat == null || lon == null) return null;
    var best = null, bestKm = Infinity;
    model.provinces.forEach(function (p) {
      var dLat = (p.lat - lat) * Math.PI / 180, dLon = (p.lon - lon) * Math.PI / 180;
      var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
              Math.cos(lat * Math.PI / 180) * Math.cos(p.lat * Math.PI / 180) *
              Math.sin(dLon / 2) * Math.sin(dLon / 2);
      var km = 12742 * Math.asin(Math.sqrt(a));
      if (km < bestKm) { bestKm = km; best = p; }
    });
    return bestKm <= 150 ? best : null;
  }

  // ── context ───────────────────────────────────────────────
  function buildContext(input, model) {
    var now = input.now || new Date();
    var hour = now.getHours();
    // Same hours as the pipeline's meal columns (notebook 02).
    var meal = hour >= 5 && hour <= 10 ? 'morning' : hour >= 11 && hour <= 15 ? 'lunch'
             : hour >= 16 && hour <= 20 ? 'dinner' : 'late';
    var today = isoDate(now);
    var tempMean = input.tempMeanC != null ? input.tempMeanC : (input.tempC != null ? input.tempC : null);
    var bin = model.temp_bin || 5;
    return {
      hasWeather: !!input.hasWeather,
      feelsC: input.feelsC, tempC: tempMean,
      tempBin: tempMean == null ? null : String(clamp(Math.floor(tempMean / bin) * bin, -10, 30)),
      // A rainy day in the pipeline is ≥1 mm of rain that day; also count rain falling right now.
      isRainy: !!input.hasWeather && ((input.rainTodayMm || 0) >= 1 || (input.rainMm || 0) >= 0.2),
      pm25: input.pm25 != null ? input.pm25 : 15,
      province: nearestProvince(model, input.lat, input.lon),
      hour: hour, meal: meal,
      slot: { morning: 'breakfast', lunch: 'lunch', dinner: 'dinner', late: 'late' }[meal],  // v1 name, for the app
      isWeekend: now.getDay() === 0 || now.getDay() === 6,
      events: model.calendar.filter(function (e) { return e.date === today; }),
      hunger: input.hunger != null ? input.hunger : 5,   // 1-10
      budget: input.budget != null ? input.budget : 2,   // 1-3
      party: input.party != null ? input.party : 1,
      recent: input.recent || [],
      exclude: input.exclude || [],       // turned down with "안 땡겨" this round — never shown again
      prefs: input.prefs || {}            // answers to the narrowing questions: spice, base, novelty
    };
  }

  // ── terms ─────────────────────────────────────────────────
  // Each term returns { v: log-score contribution, reason: {ko,en} | null }.
  // measured: true → from the pipeline; folklore: true → kept v1 heuristic, untested.
  var TERMS = [
    {
      key: 'popular', measured: true,
      f: function (d, c, m) {
        if (!d.popularity) return { v: 0 };
        var v = 0.5 * ln(d.popularity / m.medianPopularity);     // √popularity, centred on the median dish
        return { v: v, reason: d.popularity >= m.topQuartile
          ? { ko: '요즘 많이 찾는 메뉴', en: 'Searched a lot lately' } : null };
      }
    },
    {
      key: 'rain', measured: true,
      f: function (d, c) {
        if (!c.isRainy || !d.rain) return { v: 0 };
        return { v: ln(d.rain), reason: { ko: '비 오는 날 검색 ' + x(d.rain), en: 'Rainy days: searched ' + x(d.rain) } };
      }
    },
    {
      key: 'temp', measured: true,
      f: function (d, c) {
        var b = c.tempBin != null && d.temp[c.tempBin];
        if (!b) return { v: 0 };
        var t = Math.round(c.tempC);
        return { v: ln(b), reason: { ko: t + '°C엔 평소의 ' + x(b), en: 'At ' + t + '°C: ' + x(b) + ' its usual searches' } };
      }
    },
    {
      key: 'region', measured: true,
      f: function (d, c) {
        var l = c.province && d.region[c.province.geo];
        if (!l) return { v: 0 };
        return { v: ln(l), reason: { ko: c.province.ko + '에서 ' + x(l) + ' 더 찾는 메뉴',
                                     en: c.province.en + ' searches it ' + x(l) + ' the national level' } };
      }
    },
    {
      key: 'meal', measured: false,
      f: function (d, c) {
        var fit = d.meal[c.meal] != null ? d.meal[c.meal] : 1;
        var label = { morning: ['아침', 'breakfast'], lunch: ['점심', 'lunch'], dinner: ['저녁', 'dinner'], late: ['야식', 'late night'] }[c.meal];
        return { v: ln(OFF_MEAL + (1 - OFF_MEAL) * fit),       // never positive: it only holds back off-hour dishes
                 reason: fit >= 1 ? { ko: label[0] + '으로 딱', en: 'Right for ' + label[1] } : null, weak: true };
      }
    },
    {
      key: 'weekend', measured: true,
      f: function (d, c) {
        if (!c.isWeekend || !d.weekend) return { v: 0 };
        return { v: ln(d.weekend), reason: { ko: '주말엔 ' + x(d.weekend), en: 'Weekends: ' + x(d.weekend) } };
      }
    },
    {
      key: 'foodday', measured: true,
      f: function (d, c) {
        var v = 0, best = null;
        c.events.forEach(function (e) {
          var lift = d.events[e.event];
          if (!lift) return;
          v += ln(lift.lift);                                   // clipped at ×3 for the score…
          if (!best || lift.raw > best.raw) best = { e: e, raw: lift.raw };
        });
        if (!best) return { v: 0 };
        return { v: v, reason: {                                // …but the reason shows the true effect
          ko: best.e.label + ' — 평소의 ' + x(best.raw), en: best.e.label_en + ': ' + x(best.raw) + ' its usual searches' } };
      }
    },
    // kept from v1 ───────────────────────────────────────────
    {
      key: 'hunger', w: 2.2,
      f: function (d, c) {
        var want = (c.hunger - 1) / 9 * 3;
        var v = 2.2 * (1 - 2 * Math.abs(d.heavy - want) / 3);
        var reason = c.hunger >= 7 ? { ko: '배고픔 ' + c.hunger + '/10 — 든든하게', en: 'Hunger ' + c.hunger + '/10 — go big' }
                   : c.hunger <= 3 ? { ko: '배고픔 ' + c.hunger + '/10 — 가볍게', en: 'Hunger ' + c.hunger + '/10 — keep it light' }
                   : { ko: '배고픔 ' + c.hunger + '/10 — 적당히', en: 'Hunger ' + c.hunger + '/10 — middle of the road' };
        return { v: v, reason: reason, weak: true };
      }
    },
    {
      key: 'party', w: 2.0,
      f: function (d, c) { return { v: c.party >= 3 && !d.share ? -0.4 : 0 }; }   // solo is a filter, see rank()
    },
    {
      key: 'dust', w: 0.9, folklore: true,
      f: function (d, c) {
        if (c.pm25 < 35 || d.tags.indexOf('미세먼지') < 0) return { v: 0 };
        return { v: 0.9 * clamp((c.pm25 - 35) / 45, 0.3, 1),
                 reason: { ko: '미세먼지 ' + Math.round(c.pm25) + '㎍ — 속설대로라면',
                           en: 'PM2.5 at ' + Math.round(c.pm25) + ' — if the folklore holds' } };
      }
    },
    {
      key: 'recent', w: 3.5,
      f: function (d, c) { return { v: c.recent.indexOf(d.id) > -1 ? -3.5 : 0 }; }
    }
  ];

  // ── scoring ───────────────────────────────────────────────
  function prepare(model) {
    if (model._ready) return model;
    var pops = model.dishes.map(function (d) { return d.popularity; }).filter(Boolean).sort(function (a, b) { return a - b; });
    model.medianPopularity = pops[Math.floor(pops.length / 2)] || 1;
    model.topQuartile = pops[Math.floor(pops.length * 0.75)] || Infinity;
    model._ready = true;
    return model;
  }

  function scoreDish(dish, ctx, model) {
    var total = 0, parts = [];
    TERMS.forEach(function (t) {
      var r = t.f(dish, ctx, model);
      total += r.v;
      parts.push({ key: t.key, v: r.v, w: 1, contrib: r.v, reason: r.reason || null,
                   measured: !!t.measured, folklore: !!t.folklore, weak: !!r.weak });
    });
    return { total: total, parts: parts };
  }

  // Narrowing questions, asked after every three "안 땡겨". Strict: once answered, only dishes that
  // match are eligible — a dish whose attribute is unknown doesn't match.
  function isFamiliar(d, model) { return d.ubiq >= 2 && d.popularity >= model.medianPopularity; }
  function matchesPrefs(d, p, model) {
    if (p.spice === 'hot' && !(d.spice >= 2)) return false;
    if (p.spice === 'mild' && !(d.spice != null && d.spice <= 1)) return false;
    if (p.base && d.base !== p.base) return false;
    if (p.soup === 'yes' && !(d.soup >= 2)) return false;                   // a proper broth (catalog soup 2-3)
    if (p.soup === 'no' && !(d.soup != null && d.soup <= 1)) return false;
    if (p.speed && d.speed !== (p.speed === 'fast' ? 'fast' : 'sit')) return false;
    if (p.novelty) {
      if (d.ubiq == null || !d.popularity) return false;
      if ((p.novelty === 'familiar') !== isFamiliar(d, model)) return false;
    }
    return true;
  }

  // Which narrowing questions this model can answer (older model files lack spice, base, ubiq).
  var NEEDS = { spice: 'spice', base: 'base', novelty: 'ubiq', soup: 'soup', speed: 'speed' };
  function canAsk(key, model) {
    return model.dishes.some(function (d) { return d[NEEDS[key]] != null; });
  }

  function rank(ctx, model) {
    var out = [];
    model.dishes.forEach(function (d) {
      if (d.price > ctx.budget) return;                // budget is a hard filter
      if (ctx.exclude.indexOf(d.id) > -1) return;      // already turned down this round
      // Early morning and late at night most restaurants are closed: only dishes marked for that time
      // (breakfast places, 24-hour places, delivery, 포차) can be had, so the others are left out
      // rather than scored down — a dish you can't get isn't "less likely", it's unavailable.
      if ((ctx.meal === 'late' || ctx.meal === 'morning') && !(d.meal[ctx.meal] > 0)) return;
      if (!matchesPrefs(d, ctx.prefs, model)) return;
      if (ctx.party === 1 && !d.solo) return;          // so is eating alone (파전 stays a sharing dish)
      var s = scoreDish(d, ctx, model);
      out.push({ dish: d, score: s.total, parts: s.parts });
    });
    out.sort(function (a, b) { return b.score - a.score; });
    return out;
  }

  function sample(ranked, tau, poolSize) {
    var pool = ranked.slice(0, poolSize || 25);
    if (!pool.length) return null;
    var top = pool[0].score;
    var weights = pool.map(function (r) { return Math.exp((r.score - top) / (tau || 0.7)); });
    var sum = weights.reduce(function (a, b) { return a + b; }, 0);
    var r = Math.random() * sum;
    for (var i = 0; i < pool.length; i++) {
      r -= weights[i];
      if (r <= 0) return { pick: pool[i], p: weights[i] / sum };
    }
    return { pick: pool[pool.length - 1], p: weights[weights.length - 1] / sum };
  }

  // Reasons: measured effects first (they carry real numbers), then the kept heuristics.
  function explain(result, lang, max) {
    var byContrib = function (a, b) { return b.contrib - a.contrib; };
    var named = result.parts.filter(function (p) { return p.reason && p.contrib >= CHIP_MIN; });
    var strong = named.filter(function (p) { return !p.weak; }).sort(byContrib);
    var chosen = strong.length >= 2 ? strong : strong.concat(named.filter(function (p) { return p.weak; }).sort(byContrib));
    // A recommendation with no stated reason is worse than none (v1's rule), so fall back to
    // whatever reasons exist — e.g. "right for lunch" — on a day when nothing stands out.
    if (!chosen.length) chosen = result.parts.filter(function (p) { return p.reason; }).sort(byContrib);
    return chosen.slice(0, max || 3).map(function (p) {
      return { key: p.key, text: lang === 'en' ? p.reason.en : p.reason.ko,
               measured: p.measured, folklore: p.folklore, contrib: p.contrib };
    });
  }

  function suggest(input, opts) {
    opts = opts || {};
    var model = prepare(global.MOMUK_MODEL);
    var ctx = buildContext(input, model);
    var ranked = rank(ctx, model);
    if (!ranked.length) return { ctx: ctx, ranked: [], picked: null, why: [] };
    var s = sample(ranked, opts.tau, opts.poolSize);
    return { ctx: ctx, ranked: ranked, picked: s.pick, p: s.p, why: explain(s.pick, opts.lang || 'ko', 3) };
  }

  global.MomukV2 = {
    buildContext: function (input) { return buildContext(input, prepare(global.MOMUK_MODEL)); },
    nearestProvince: nearestProvince,
    canAsk: function (key) { return canAsk(key, global.MOMUK_MODEL); },
    scoreDish: scoreDish, rank: rank, sample: sample, explain: explain, suggest: suggest,
    TERMS: TERMS
  };
})(window);
