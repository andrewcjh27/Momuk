// momuk-engine.js — context builder + scoring model for the menu suggester
//
// The model is a transparent weighted sum, deliberately not ML:
//
//   score(dish) = Σ wᵢ · fᵢ(context, dish)     each fᵢ returns -1..1
//   P(dish)     = softmax(score / τ) over the top N
//   why         = the top positive terms, rendered as text
//
// Every term carries its own reason text, so the explanation chips are real
// feature attribution rather than copy written to sound smart.

(function (global) {
  'use strict';

  var clamp = function (v, lo, hi) { return Math.max(lo, Math.min(hi, v)); };

  // ── context ───────────────────────────────────────────────
  // Builds the feature vector the model scores against. Weather fields are
  // optional — the model degrades gracefully to a mild-day default.
  function buildContext(input) {
    var now = input.now || new Date();
    var hour = now.getHours();
    var day = now.getDate();
    var slot =
      hour >= 5 && hour < 10 ? 'breakfast' :
      hour >= 10 && hour < 15 ? 'lunch' :
      hour >= 15 && hour < 21 ? 'dinner' : 'late';

    // Korean payday convention: the 25th.
    var daysSincePayday = day >= 25 ? day - 25 : day + (30 - 25);
    var daysToPayday = day <= 25 ? 25 - day : 30 - day + 25;

    return {
      feelsC:   input.feelsC   != null ? input.feelsC   : 18,
      tempC:    input.tempC    != null ? input.tempC    : 18,
      rainMm:   input.rainMm   != null ? input.rainMm   : 0,
      humidity: input.humidity != null ? input.humidity : 55,
      pm25:     input.pm25     != null ? input.pm25     : 15,
      hasWeather: !!input.hasWeather,
      hour: hour,
      slot: slot,
      month: now.getMonth() + 1,
      isWeekend: now.getDay() === 0 || now.getDay() === 6,
      daysSincePayday: daysSincePayday,
      daysToPayday: daysToPayday,
      hunger: input.hunger != null ? input.hunger : 5,   // 1-10
      budget: input.budget != null ? input.budget : 2,   // 1-3
      party:  input.party  != null ? input.party  : 1,
      recent: input.recent || []                          // array of dish ids
    };
  }

  // ── terms ─────────────────────────────────────────────────
  // Each term: { key, w, f(dish, ctx) -> -1..1, reason(dish, ctx) -> {ko,en} }
  // Terms marked folklore:true are cultural heuristics, not established fact.
  // They are exactly the ones v2 should test against logged decisions.
  var TERMS = [
    {
      key: 'temp', w: 2.4,
      f: function (d, c) {
        var t = clamp((c.feelsC - 2) / 26, 0, 1);      // 0 at ≤2°C, 1 at ≥28°C
        if (d.temp === 'hot')  return 1 - 2 * t;
        if (d.temp === 'cold') return 2 * t - 1;
        return 0.15;
      },
      reason: function (d, c) {
        var t = Math.round(c.feelsC);
        return d.temp === 'cold'
          ? { ko: t + '°C — 시원한 걸로', en: t + '°C out — go cold' }
          : { ko: t + '°C — 뜨끈한 게 낫죠', en: t + '°C out — you want it hot' };
      }
    },
    {
      key: 'soup', w: 1.6,
      f: function (d, c) {
        if (d.temp === 'cold') return 0;   // 냉면 broth is not "soup weather" soup
        var cold = clamp((20 - c.feelsC) / 22, 0, 1);
        var wet = clamp(c.rainMm / 3, 0, 1);
        var want = clamp(cold * 0.6 + wet * 0.4, 0, 1);
        // At 1am nobody is reasoning about the weather. Damp the term.
        var scale = c.slot === 'late' ? 0.45 : 1;
        return scale * (1 - 2 * Math.abs(d.soup / 3 - want));
      },
      reason: function (d) {
        return d.soup >= 2
          ? { ko: '국물이 있어야 하는 날', en: 'A soup kind of day' }
          : { ko: '국물 없이 가볍게', en: 'Dry, not soupy' };
      }
    },
    {
      key: 'rain', w: 1.6, folklore: true,
      f: function (d, c) {
        if (c.rainMm < 0.2) return 0;
        return d.tags.indexOf('비오는날') > -1 ? clamp(c.rainMm / 2, 0.4, 1) : 0;
      },
      reason: function () {
        return { ko: '비 오는 날엔 이거죠', en: 'Raining — the classic call' };
      }
    },
    {
      key: 'dust', w: 0.9, folklore: true,
      f: function (d, c) {
        if (c.pm25 < 35) return 0;
        return d.tags.indexOf('미세먼지') > -1 ? clamp((c.pm25 - 35) / 45, 0.3, 1) : 0;
      },
      reason: function (d, c) {
        return { ko: '미세먼지 ' + Math.round(c.pm25) + '㎍ — 속설대로라면',
                 en: 'PM2.5 at ' + Math.round(c.pm25) + ' — if the folklore holds' };
      }
    },
    {
      key: 'hunger', w: 2.2,
      f: function (d, c) {
        var want = (c.hunger - 1) / 9 * 3;
        return 1 - 2 * Math.abs(d.heavy - want) / 3;
      },
      reason: function (d, c) {
        return c.hunger >= 7
          ? { ko: '배고픔 ' + c.hunger + '/10 — 든든하게', en: 'Hunger ' + c.hunger + '/10 — go big' }
          : c.hunger <= 3
          ? { ko: '배고픔 ' + c.hunger + '/10 — 가볍게', en: 'Hunger ' + c.hunger + '/10 — keep it light' }
          : { ko: '배고픔 ' + c.hunger + '/10 — 적당히', en: 'Hunger ' + c.hunger + '/10 — middle of the road' };
      }
    },
    {
      key: 'slot', w: 1.4,
      f: function (d, c) {
        if (c.slot === 'lunch') {
          if (!c.isWeekend) return (d.speed === 'fast' ? 0.6 : -0.5) + (d.heavy === 3 ? -0.3 : 0);
          return c.party > 1 && d.share ? 0.4 : 0;      // weekend lunch: no clock pressure
        }
        if (c.slot === 'dinner') {
          return (c.party > 1 && d.share ? 0.5 : 0) + (d.speed === 'sit' ? 0.2 : 0);
        }
        if (c.slot === 'late') {
          return d.tags.indexOf('야식') > -1 ? 1.2 : -0.2;
        }
        return (d.soup >= 2 ? 0.5 : 0) + (d.heavy === 3 ? -0.6 : 0);
      },
      reason: function (d, c) {
        if (c.slot === 'late') return { ko: '야식 시간대', en: 'Late-night hours' };
        if (c.slot === 'breakfast') return { ko: '아침엔 속 편한 걸로', en: 'Easy on an empty stomach' };
        if (c.slot === 'lunch')
          return c.isWeekend
            ? { ko: '주말 점심 — 급할 것 없죠', en: 'Weekend lunch — no clock' }
            : { ko: '평일 점심 — 빨리 먹고 들어가야죠', en: 'Weekday lunch — in and out' };
        return c.party > 1
          ? { ko: c.party + '명이면 나눠 먹는 걸로', en: 'Party of ' + c.party + ' — something to share' }
          : { ko: '저녁은 좀 여유 있게', en: 'Dinner, no rush' };
      }
    },
    {
      key: 'ubiq', w: 1.2,
      f: function (d, c) {
        var urgency = (c.slot === 'lunch' && !c.isWeekend) ? 1 : c.slot === 'late' ? 0.8 : 0.3;
        return (d.ubiq - 2) * urgency;
      },
      reason: function () {
        return { ko: '어디서나 쉽게 찾을 수 있어요', en: 'Findable just about anywhere' };
      }
    },
    {
      key: 'payday', w: 0.9, folklore: true,
      f: function (d, c) {
        if (c.daysSincePayday <= 4) return d.price === 3 ? 0.7 : d.price === 1 ? -0.2 : 0;
        // Budget is what they *can* spend; payday is only a prior on what they
        // *want* to. An explicit top budget overrides the prior.
        if (c.daysToPayday <= 7 && c.budget < 3) return d.price === 1 ? 0.7 : d.price === 3 ? -0.6 : 0;
        return 0;
      },
      reason: function (d, c) {
        return c.daysSincePayday <= 4
          ? { ko: '월급날 직후 — 좀 쓰셔도 됩니다', en: 'Just after payday — treat yourself' }
          : { ko: '월급까지 ' + c.daysToPayday + '일', en: c.daysToPayday + ' days to payday' };
      }
    },
    {
      key: 'season', w: 0.7, folklore: true,
      f: function (d, c) {
        if (c.month >= 7 && c.month <= 8 && d.tags.indexOf('보양') > -1) return 0.9;
        if (c.feelsC < 5 && d.tags.indexOf('겨울') > -1) return 0.7;
        return 0;
      },
      reason: function (d, c) {
        return (c.month >= 7 && c.month <= 8)
          ? { ko: '한여름엔 보양식', en: 'Peak summer — restorative food' }
          : { ko: '추운 날 음식', en: 'Cold-weather food' };
      }
    },
    {
      key: 'party', w: 2.0,
      f: function (d, c) {
        if (c.party === 1 && !d.solo) return -1;    // 삼겹살 alone is genuinely awkward
        if (c.party >= 3 && !d.share) return -0.2;  // mild, not disqualifying
        return 0;
      },
      reason: function () { return { ko: '', en: '' }; }   // only ever penalises
    },
    {
      key: 'recent', w: 3.5,
      f: function (d, c) {
        if (c.recent.indexOf(d.id) > -1) return -1;
        return 0;
      },
      reason: function () { return { ko: '', en: '' }; }
    }
  ];

  // ── scoring ───────────────────────────────────────────────
  function scoreDish(dish, ctx) {
    var total = 0, parts = [];
    for (var i = 0; i < TERMS.length; i++) {
      var t = TERMS[i];
      var v = t.f(dish, ctx);
      var contrib = v * t.w;
      total += contrib;
      parts.push({ key: t.key, v: v, w: t.w, contrib: contrib, folklore: !!t.folklore, term: t });
    }
    return { total: total, parts: parts };
  }

  function rank(ctx, dishes) {
    var out = [];
    for (var i = 0; i < dishes.length; i++) {
      var d = dishes[i];
      if (d.price > ctx.budget) continue;               // budget is a hard filter
      var s = scoreDish(d, ctx);
      out.push({ dish: d, score: s.total, parts: s.parts });
    }
    out.sort(function (a, b) { return b.score - a.score; });
    return out;
  }

  // Sample rather than take the max — argmax makes the same weather always
  // return the same dish, which reads as broken rather than confident.
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

  // The chips: top positive contributions, deduped, with text from the term itself.
  function explain(result, ctx, lang, max) {
    return result.parts
      .filter(function (p) { return p.contrib > 0.45; })
      .sort(function (a, b) { return b.contrib - a.contrib; })
      .slice(0, max || 3)
      .map(function (p) {
        var r = p.term.reason(result.dish, ctx);
        return { key: p.key, text: lang === 'en' ? r.en : r.ko, folklore: p.folklore, contrib: p.contrib };
      })
      .filter(function (c) { return c.text; });
  }

  function suggest(input, opts) {
    opts = opts || {};
    var ctx = buildContext(input);
    var ranked = rank(ctx, global.MOMUK_DATA || []);
    if (!ranked.length) return { ctx: ctx, ranked: [], picked: null, why: [] };
    var s = sample(ranked, opts.tau, opts.poolSize);
    return {
      ctx: ctx,
      ranked: ranked,
      picked: s.pick,
      p: s.p,
      why: explain(s.pick, ctx, opts.lang || 'ko', 3)
    };
  }

  global.Momuk = {
    buildContext: buildContext,
    scoreDish: scoreDish,
    rank: rank,
    sample: sample,
    explain: explain,
    suggest: suggest,
    TERMS: TERMS
  };
})(window);
