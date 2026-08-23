// momuk-data.js — dish taxonomy for the menu suggester
// Same pattern as cafes-data.js: a hand-curated set, versioned in the repo.
//
// FIELDS
//   id     unique slug
//   ko/en  display names
//   cuisine 한식 · 중식 · 일식 · 양식 · 분식 · 아시안
//   temp   'hot' | 'cold' | 'room'   — how it's served. Highest-signal field vs weather.
//   soup   0-3   dry → 국물 요리
//   spice  0-3
//   heavy  0-3   how full it leaves you. Matched against the hunger slider.
//   price  1-3   ₩10k 이하 / ₩10-20k / ₩20k+
//   speed  'fast' | 'sit'
//   solo   0|1   fine to eat alone
//   share  0|1   works for a group
//   ubiq   1-3   findable near anywhere → worth a trek. Stands in for a places API.
//   tags   해장 · 야식 · 보양 · 비오는날 · 미세먼지 · 다이어트 · 국물 · 면 · 밥 · 고기 · 술안주 · 혼밥 · 여름 · 겨울 · 분식

window.MOMUK_DATA = [
// ── 한식 · 국물/찌개/탕 ──────────────────────────────────────
{ id:'kimchi-jjigae',   ko:'김치찌개',     en:'Kimchi stew',            cuisine:'한식', temp:'hot',  soup:3, spice:2, heavy:2, price:1, speed:'fast', solo:1, share:1, ubiq:3, tags:['해장','국물','밥'] },
{ id:'doenjang-jjigae', ko:'된장찌개',     en:'Soybean paste stew',     cuisine:'한식', temp:'hot',  soup:3, spice:1, heavy:2, price:1, speed:'fast', solo:1, share:1, ubiq:3, tags:['국물','밥'] },
{ id:'sundubu',         ko:'순두부찌개',   en:'Soft tofu stew',         cuisine:'한식', temp:'hot',  soup:3, spice:2, heavy:1, price:1, speed:'fast', solo:1, share:1, ubiq:3, tags:['국물','밥','해장'] },
{ id:'budae-jjigae',    ko:'부대찌개',     en:'Army stew',              cuisine:'한식', temp:'hot',  soup:3, spice:2, heavy:3, price:2, speed:'sit',  solo:0, share:1, ubiq:3, tags:['국물','술안주'] },
{ id:'cheonggukjang',   ko:'청국장',       en:'Rich fermented stew',    cuisine:'한식', temp:'hot',  soup:3, spice:1, heavy:2, price:2, speed:'sit',  solo:1, share:1, ubiq:1, tags:['국물','밥'] },
{ id:'galbitang',       ko:'갈비탕',       en:'Short rib soup',         cuisine:'한식', temp:'hot',  soup:3, spice:0, heavy:2, price:3, speed:'sit',  solo:1, share:1, ubiq:2, tags:['국물','보양'] },
{ id:'seolleongtang',   ko:'설렁탕',       en:'Ox bone soup',           cuisine:'한식', temp:'hot',  soup:3, spice:0, heavy:2, price:2, speed:'fast', solo:1, share:0, ubiq:3, tags:['국물','해장','겨울'] },
{ id:'gomtang',         ko:'곰탕',         en:'Beef bone soup',         cuisine:'한식', temp:'hot',  soup:3, spice:0, heavy:2, price:2, speed:'fast', solo:1, share:0, ubiq:2, tags:['국물','해장'] },
{ id:'samgyetang',      ko:'삼계탕',       en:'Ginseng chicken soup',   cuisine:'한식', temp:'hot',  soup:3, spice:0, heavy:3, price:3, speed:'sit',  solo:1, share:0, ubiq:2, tags:['보양','여름','국물'] },
{ id:'yukgaejang',      ko:'육개장',       en:'Spicy beef soup',        cuisine:'한식', temp:'hot',  soup:3, spice:3, heavy:2, price:2, speed:'fast', solo:1, share:0, ubiq:3, tags:['국물','해장'] },
{ id:'gamjatang',       ko:'감자탕',       en:'Pork bone stew',         cuisine:'한식', temp:'hot',  soup:3, spice:2, heavy:3, price:2, speed:'sit',  solo:0, share:1, ubiq:3, tags:['국물','해장','술안주'] },
{ id:'haejangguk',      ko:'뼈해장국',     en:'Pork bone hangover soup',cuisine:'한식', temp:'hot',  soup:3, spice:2, heavy:2, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['해장','국물'] },
{ id:'kongnamul-gukbap',ko:'콩나물국밥',   en:'Bean sprout soup rice',  cuisine:'한식', temp:'hot',  soup:3, spice:1, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:2, tags:['해장','국물','다이어트'] },
{ id:'sundae-gukbap',   ko:'순대국밥',     en:'Blood sausage soup',     cuisine:'한식', temp:'hot',  soup:3, spice:1, heavy:2, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['해장','국물'] },
{ id:'dwaeji-gukbap',   ko:'돼지국밥',     en:'Pork soup rice',         cuisine:'한식', temp:'hot',  soup:3, spice:1, heavy:2, price:1, speed:'fast', solo:1, share:0, ubiq:2, tags:['해장','국물'] },
{ id:'chueotang',       ko:'추어탕',       en:'Loach soup',             cuisine:'한식', temp:'hot',  soup:3, spice:2, heavy:2, price:2, speed:'sit',  solo:1, share:0, ubiq:1, tags:['보양','국물'] },
{ id:'maeuntang',       ko:'매운탕',       en:'Spicy fish stew',        cuisine:'한식', temp:'hot',  soup:3, spice:3, heavy:2, price:2, speed:'sit',  solo:0, share:1, ubiq:2, tags:['국물','술안주'] },
{ id:'daegutang',       ko:'대구탕',       en:'Cod soup',               cuisine:'한식', temp:'hot',  soup:3, spice:1, heavy:1, price:2, speed:'sit',  solo:1, share:0, ubiq:1, tags:['해장','국물','다이어트'] },
{ id:'tteokguk',        ko:'떡국',         en:'Rice cake soup',         cuisine:'한식', temp:'hot',  soup:3, spice:0, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:2, tags:['국물','겨울'] },
{ id:'manduguk',        ko:'만둣국',       en:'Dumpling soup',          cuisine:'한식', temp:'hot',  soup:3, spice:0, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:2, tags:['국물','겨울'] },
{ id:'sujebi',          ko:'수제비',       en:'Hand-torn noodle soup',  cuisine:'한식', temp:'hot',  soup:3, spice:1, heavy:1, price:1, speed:'fast', solo:1, share:1, ubiq:2, tags:['비오는날','국물','면'] },
{ id:'kalguksu',        ko:'칼국수',       en:'Knife-cut noodle soup',  cuisine:'한식', temp:'hot',  soup:3, spice:0, heavy:1, price:1, speed:'fast', solo:1, share:1, ubiq:3, tags:['비오는날','국물','면'] },
{ id:'bajirak-kalguksu',ko:'바지락칼국수', en:'Clam knife-cut noodles', cuisine:'한식', temp:'hot',  soup:3, spice:0, heavy:1, price:2, speed:'sit',  solo:1, share:1, ubiq:2, tags:['비오는날','국물','면'] },
{ id:'dak-kalguksu',    ko:'닭칼국수',     en:'Chicken knife noodles',  cuisine:'한식', temp:'hot',  soup:3, spice:1, heavy:2, price:2, speed:'sit',  solo:1, share:1, ubiq:2, tags:['비오는날','국물','면','보양'] },
{ id:'pajeon',          ko:'해물파전',     en:'Seafood scallion pancake',cuisine:'한식',temp:'hot',  soup:0, spice:0, heavy:2, price:2, speed:'sit',  solo:0, share:1, ubiq:2, tags:['비오는날','술안주'] },
{ id:'kimchijeon',      ko:'김치전',       en:'Kimchi pancake',         cuisine:'한식', temp:'hot',  soup:0, spice:1, heavy:2, price:1, speed:'sit',  solo:0, share:1, ubiq:2, tags:['비오는날','술안주'] },

// ── 한식 · 밥/구이/볶음 ──────────────────────────────────────
{ id:'bibimbap',        ko:'비빔밥',       en:'Bibimbap',               cuisine:'한식', temp:'room', soup:0, spice:1, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['밥','다이어트'] },
{ id:'dolsot-bibimbap', ko:'돌솥비빔밥',   en:'Hot stone bibimbap',     cuisine:'한식', temp:'hot',  soup:0, spice:1, heavy:2, price:2, speed:'sit',  solo:1, share:0, ubiq:2, tags:['밥'] },
{ id:'jeyuk-bokkeum',   ko:'제육볶음',     en:'Spicy stir-fried pork',  cuisine:'한식', temp:'hot',  soup:0, spice:3, heavy:2, price:1, speed:'fast', solo:1, share:1, ubiq:3, tags:['밥','고기'] },
{ id:'bulgogi',         ko:'불고기',       en:'Bulgogi',                cuisine:'한식', temp:'hot',  soup:0, spice:0, heavy:2, price:2, speed:'sit',  solo:1, share:1, ubiq:3, tags:['고기','밥'] },
{ id:'galbi',           ko:'갈비',         en:'Grilled short ribs',     cuisine:'한식', temp:'hot',  soup:0, spice:0, heavy:3, price:3, speed:'sit',  solo:0, share:1, ubiq:2, tags:['고기','술안주'] },
{ id:'samgyeopsal',     ko:'삼겹살',       en:'Pork belly',             cuisine:'한식', temp:'hot',  soup:0, spice:0, heavy:3, price:3, speed:'sit',  solo:0, share:1, ubiq:3, tags:['고기','술안주','미세먼지'] },
{ id:'moksal',          ko:'목살',         en:'Pork shoulder',          cuisine:'한식', temp:'hot',  soup:0, spice:0, heavy:3, price:3, speed:'sit',  solo:0, share:1, ubiq:3, tags:['고기','술안주','미세먼지'] },
{ id:'sogogi-gui',      ko:'소고기구이',   en:'Grilled beef',           cuisine:'한식', temp:'hot',  soup:0, spice:0, heavy:3, price:3, speed:'sit',  solo:0, share:1, ubiq:2, tags:['고기','술안주'] },
{ id:'gopchang',        ko:'곱창',         en:'Grilled intestines',     cuisine:'한식', temp:'hot',  soup:0, spice:1, heavy:3, price:3, speed:'sit',  solo:0, share:1, ubiq:2, tags:['고기','술안주','야식'] },
{ id:'dakgalbi',        ko:'닭갈비',       en:'Spicy stir-fried chicken',cuisine:'한식',temp:'hot',  soup:0, spice:3, heavy:2, price:2, speed:'sit',  solo:0, share:1, ubiq:2, tags:['고기','술안주'] },
{ id:'jjimdak',         ko:'찜닭',         en:'Braised chicken',        cuisine:'한식', temp:'hot',  soup:1, spice:2, heavy:2, price:2, speed:'sit',  solo:0, share:1, ubiq:2, tags:['고기','밥'] },
{ id:'dakbokkeumtang',  ko:'닭볶음탕',     en:'Spicy chicken stew',     cuisine:'한식', temp:'hot',  soup:2, spice:3, heavy:2, price:2, speed:'sit',  solo:0, share:1, ubiq:2, tags:['고기','국물'] },
{ id:'bossam',          ko:'보쌈',         en:'Boiled pork wraps',      cuisine:'한식', temp:'room', soup:0, spice:0, heavy:3, price:3, speed:'sit',  solo:0, share:1, ubiq:2, tags:['고기','술안주'] },
{ id:'jokbal',          ko:'족발',         en:'Braised pig trotters',   cuisine:'한식', temp:'room', soup:0, spice:0, heavy:3, price:3, speed:'sit',  solo:0, share:1, ubiq:3, tags:['고기','술안주','야식'] },
{ id:'nakji-bokkeum',   ko:'낙지볶음',     en:'Spicy stir-fried octopus',cuisine:'한식',temp:'hot',  soup:0, spice:3, heavy:2, price:2, speed:'sit',  solo:1, share:1, ubiq:2, tags:['밥','술안주'] },
{ id:'jjukkumi',        ko:'쭈꾸미볶음',   en:'Spicy baby octopus',     cuisine:'한식', temp:'hot',  soup:0, spice:3, heavy:2, price:2, speed:'sit',  solo:0, share:1, ubiq:2, tags:['밥','술안주'] },
{ id:'ojingeo-bokkeum', ko:'오징어볶음',   en:'Spicy stir-fried squid', cuisine:'한식', temp:'hot',  soup:0, spice:3, heavy:2, price:2, speed:'fast', solo:1, share:1, ubiq:2, tags:['밥'] },
{ id:'godeungeo-gui',   ko:'고등어구이',   en:'Grilled mackerel',       cuisine:'한식', temp:'hot',  soup:0, spice:0, heavy:1, price:2, speed:'fast', solo:1, share:0, ubiq:2, tags:['밥','다이어트'] },
{ id:'galchi-gui',      ko:'갈치구이',     en:'Grilled hairtail',       cuisine:'한식', temp:'hot',  soup:0, spice:0, heavy:1, price:3, speed:'sit',  solo:1, share:0, ubiq:1, tags:['밥'] },
{ id:'saengseon-baekban',ko:'생선구이백반',en:'Grilled fish set meal',  cuisine:'한식', temp:'hot',  soup:1, spice:0, heavy:1, price:2, speed:'fast', solo:1, share:0, ubiq:2, tags:['밥','다이어트'] },
{ id:'ganjang-gejang',  ko:'간장게장',     en:'Soy-marinated crab',     cuisine:'한식', temp:'cold', soup:0, spice:0, heavy:2, price:3, speed:'sit',  solo:0, share:1, ubiq:1, tags:['밥'] },
{ id:'kimchi-bokkeumbap',ko:'김치볶음밥',  en:'Kimchi fried rice',      cuisine:'한식', temp:'hot',  soup:0, spice:2, heavy:2, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['밥','혼밥'] },
{ id:'gyeran-bokkeumbap',ko:'계란볶음밥',  en:'Egg fried rice',         cuisine:'한식', temp:'hot',  soup:0, spice:0, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:2, tags:['밥','혼밥'] },
{ id:'baekban',         ko:'백반',         en:'Home-style set meal',    cuisine:'한식', temp:'hot',  soup:1, spice:1, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['밥'] },

// ── 분식 ─────────────────────────────────────────────────────
{ id:'tteokbokki',      ko:'떡볶이',       en:'Tteokbokki',             cuisine:'분식', temp:'hot',  soup:1, spice:3, heavy:2, price:1, speed:'fast', solo:1, share:1, ubiq:3, tags:['야식','분식'] },
{ id:'rose-tteokbokki', ko:'로제떡볶이',   en:'Rosé tteokbokki',        cuisine:'분식', temp:'hot',  soup:1, spice:2, heavy:2, price:1, speed:'fast', solo:1, share:1, ubiq:2, tags:['야식','분식'] },
{ id:'gimbap',          ko:'김밥',         en:'Gimbap',                 cuisine:'분식', temp:'room', soup:0, spice:0, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['혼밥','다이어트','분식'] },
{ id:'chamchi-gimbap',  ko:'참치김밥',     en:'Tuna gimbap',            cuisine:'분식', temp:'room', soup:0, spice:0, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['혼밥','분식'] },
{ id:'ramyeon',         ko:'라면',         en:'Ramyeon',                cuisine:'분식', temp:'hot',  soup:3, spice:2, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['야식','국물','면','해장'] },
{ id:'jjolmyeon',       ko:'쫄면',         en:'Chewy cold noodles',     cuisine:'분식', temp:'cold', soup:0, spice:3, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:2, tags:['면','여름'] },
{ id:'janchi-guksu',    ko:'잔치국수',     en:'Warm somen noodles',     cuisine:'분식', temp:'hot',  soup:3, spice:0, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:2, tags:['국물','면'] },
{ id:'bibim-guksu',     ko:'비빔국수',     en:'Spicy cold noodles',     cuisine:'분식', temp:'cold', soup:0, spice:2, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:2, tags:['면','여름'] },
{ id:'udon',            ko:'우동',         en:'Udon',                   cuisine:'분식', temp:'hot',  soup:3, spice:0, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['국물','면'] },
{ id:'sundae',          ko:'순대',         en:'Sundae',                 cuisine:'분식', temp:'hot',  soup:0, spice:0, heavy:2, price:1, speed:'fast', solo:1, share:1, ubiq:3, tags:['분식','야식'] },
{ id:'twigim',          ko:'튀김',         en:'Assorted fritters',      cuisine:'분식', temp:'hot',  soup:0, spice:0, heavy:2, price:1, speed:'fast', solo:1, share:1, ubiq:3, tags:['분식','야식'] },
{ id:'mandu',           ko:'만두',         en:'Dumplings',              cuisine:'분식', temp:'hot',  soup:0, spice:0, heavy:1, price:1, speed:'fast', solo:1, share:1, ubiq:3, tags:['분식'] },
{ id:'eomuk',           ko:'어묵',         en:'Fish cake skewers',      cuisine:'분식', temp:'hot',  soup:2, spice:0, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['겨울','분식','국물'] },
{ id:'toast',           ko:'토스트',       en:'Street toast',           cuisine:'분식', temp:'hot',  soup:0, spice:0, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['혼밥','분식'] },

// ── 냉/여름 ──────────────────────────────────────────────────
{ id:'mul-naengmyeon',  ko:'물냉면',       en:'Cold broth noodles',     cuisine:'한식', temp:'cold', soup:2, spice:0, heavy:1, price:2, speed:'fast', solo:1, share:0, ubiq:3, tags:['여름','면'] },
{ id:'bibim-naengmyeon',ko:'비빔냉면',     en:'Spicy cold noodles',     cuisine:'한식', temp:'cold', soup:0, spice:3, heavy:1, price:2, speed:'fast', solo:1, share:0, ubiq:3, tags:['여름','면'] },
{ id:'pyeongyang-naengmyeon',ko:'평양냉면',en:'Pyongyang cold noodles', cuisine:'한식', temp:'cold', soup:2, spice:0, heavy:1, price:3, speed:'sit',  solo:1, share:0, ubiq:1, tags:['여름','면'] },
{ id:'milmyeon',        ko:'밀면',         en:'Busan wheat cold noodles',cuisine:'한식',temp:'cold', soup:2, spice:2, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:1, tags:['여름','면'] },
{ id:'kongguksu',       ko:'콩국수',       en:'Chilled soybean noodles',cuisine:'한식', temp:'cold', soup:2, spice:0, heavy:2, price:2, speed:'sit',  solo:1, share:0, ubiq:2, tags:['여름','면'] },
{ id:'chogye-guksu',    ko:'초계국수',     en:'Chilled chicken noodles',cuisine:'한식', temp:'cold', soup:2, spice:1, heavy:1, price:2, speed:'sit',  solo:1, share:0, ubiq:1, tags:['여름','면','다이어트'] },
{ id:'makguksu',        ko:'막국수',       en:'Buckwheat cold noodles', cuisine:'한식', temp:'cold', soup:1, spice:2, heavy:1, price:2, speed:'sit',  solo:1, share:0, ubiq:1, tags:['여름','면'] },
{ id:'naeng-momil',     ko:'냉모밀',       en:'Chilled soba',           cuisine:'일식', temp:'cold', soup:1, spice:0, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:2, tags:['여름','면','다이어트'] },

// ── 중식 ─────────────────────────────────────────────────────
{ id:'jjajangmyeon',    ko:'짜장면',       en:'Jjajangmyeon',           cuisine:'중식', temp:'hot',  soup:0, spice:0, heavy:2, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['면'] },
{ id:'jjamppong',       ko:'짬뽕',         en:'Spicy seafood noodles',  cuisine:'중식', temp:'hot',  soup:3, spice:3, heavy:2, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['국물','면','해장'] },
{ id:'junghwa-bokkeumbap',ko:'중화볶음밥', en:'Chinese fried rice',     cuisine:'중식', temp:'hot',  soup:0, spice:0, heavy:2, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['밥'] },
{ id:'tangsuyuk',       ko:'탕수육',       en:'Sweet and sour pork',    cuisine:'중식', temp:'hot',  soup:0, spice:0, heavy:3, price:2, speed:'sit',  solo:0, share:1, ubiq:3, tags:['고기'] },
{ id:'mapa-dubu',       ko:'마파두부',     en:'Mapo tofu',              cuisine:'중식', temp:'hot',  soup:1, spice:2, heavy:2, price:2, speed:'fast', solo:1, share:0, ubiq:1, tags:['밥'] },
{ id:'kkanpunggi',      ko:'깐풍기',       en:'Sweet-spicy fried chicken',cuisine:'중식',temp:'hot', soup:0, spice:2, heavy:3, price:3, speed:'sit',  solo:0, share:1, ubiq:1, tags:['고기','술안주'] },
{ id:'malatang',        ko:'마라탕',       en:'Malatang',               cuisine:'중식', temp:'hot',  soup:3, spice:3, heavy:2, price:2, speed:'fast', solo:1, share:0, ubiq:3, tags:['국물','면'] },
{ id:'mala-xiangguo',   ko:'마라샹궈',     en:'Mala xiang guo',         cuisine:'중식', temp:'hot',  soup:0, spice:3, heavy:3, price:2, speed:'sit',  solo:0, share:1, ubiq:2, tags:['술안주'] },
{ id:'huoguo',          ko:'훠궈',         en:'Hot pot',                cuisine:'중식', temp:'hot',  soup:3, spice:3, heavy:3, price:3, speed:'sit',  solo:0, share:1, ubiq:1, tags:['국물','겨울'] },
{ id:'guobaorou',       ko:'꿔바로우',     en:'Guo bao rou',            cuisine:'중식', temp:'hot',  soup:0, spice:0, heavy:3, price:2, speed:'sit',  solo:0, share:1, ubiq:2, tags:['고기'] },
{ id:'dimsum',          ko:'딤섬',         en:'Dim sum',                cuisine:'중식', temp:'hot',  soup:0, spice:0, heavy:1, price:2, speed:'sit',  solo:0, share:1, ubiq:1, tags:[] },

// ── 일식 ─────────────────────────────────────────────────────
{ id:'chobap',          ko:'초밥',         en:'Sushi',                  cuisine:'일식', temp:'cold', soup:0, spice:0, heavy:1, price:3, speed:'sit',  solo:1, share:1, ubiq:2, tags:['다이어트'] },
{ id:'hoe',             ko:'회',           en:'Sashimi',                cuisine:'일식', temp:'cold', soup:0, spice:0, heavy:1, price:3, speed:'sit',  solo:0, share:1, ubiq:2, tags:['술안주','다이어트'] },
{ id:'hoedeopbap',      ko:'회덮밥',       en:'Sashimi rice bowl',      cuisine:'일식', temp:'cold', soup:0, spice:1, heavy:1, price:2, speed:'fast', solo:1, share:0, ubiq:2, tags:['밥','다이어트'] },
{ id:'yeoneo-deopbap',  ko:'연어덮밥',     en:'Salmon rice bowl',       cuisine:'일식', temp:'cold', soup:0, spice:0, heavy:1, price:2, speed:'fast', solo:1, share:0, ubiq:2, tags:['밥'] },
{ id:'gyudon',          ko:'규동',         en:'Beef rice bowl',         cuisine:'일식', temp:'hot',  soup:0, spice:0, heavy:2, price:1, speed:'fast', solo:1, share:0, ubiq:2, tags:['밥','혼밥'] },
{ id:'katsudon',        ko:'가츠동',       en:'Pork cutlet rice bowl',  cuisine:'일식', temp:'hot',  soup:0, spice:0, heavy:3, price:2, speed:'fast', solo:1, share:0, ubiq:2, tags:['밥','혼밥'] },
{ id:'oyakodon',        ko:'오야코동',     en:'Chicken and egg bowl',   cuisine:'일식', temp:'hot',  soup:0, spice:0, heavy:2, price:2, speed:'fast', solo:1, share:0, ubiq:1, tags:['밥','혼밥'] },
{ id:'tendon',          ko:'텐동',         en:'Tempura rice bowl',      cuisine:'일식', temp:'hot',  soup:0, spice:0, heavy:3, price:2, speed:'fast', solo:1, share:0, ubiq:1, tags:['밥'] },
{ id:'donkatsu',        ko:'돈카츠',       en:'Tonkatsu',               cuisine:'일식', temp:'hot',  soup:0, spice:0, heavy:3, price:2, speed:'fast', solo:1, share:0, ubiq:3, tags:['고기'] },
{ id:'soba',            ko:'소바',         en:'Soba',                   cuisine:'일식', temp:'cold', soup:1, spice:0, heavy:1, price:2, speed:'fast', solo:1, share:0, ubiq:2, tags:['면','여름','다이어트'] },
{ id:'ramen',           ko:'라멘',         en:'Ramen',                  cuisine:'일식', temp:'hot',  soup:3, spice:1, heavy:3, price:2, speed:'fast', solo:1, share:0, ubiq:3, tags:['국물','면','야식'] },
{ id:'tonkotsu-ramen',  ko:'돈코츠라멘',   en:'Tonkotsu ramen',         cuisine:'일식', temp:'hot',  soup:3, spice:0, heavy:3, price:2, speed:'fast', solo:1, share:0, ubiq:2, tags:['국물','면'] },
{ id:'tsukemen',        ko:'츠케멘',       en:'Tsukemen',               cuisine:'일식', temp:'hot',  soup:2, spice:1, heavy:3, price:2, speed:'sit',  solo:1, share:0, ubiq:1, tags:['면'] },
{ id:'yakitori',        ko:'야키토리',     en:'Yakitori',               cuisine:'일식', temp:'hot',  soup:0, spice:0, heavy:2, price:2, speed:'sit',  solo:0, share:1, ubiq:1, tags:['술안주','고기','야식'] },
{ id:'okonomiyaki',     ko:'오코노미야키', en:'Okonomiyaki',            cuisine:'일식', temp:'hot',  soup:0, spice:0, heavy:2, price:2, speed:'sit',  solo:0, share:1, ubiq:1, tags:['비오는날','술안주'] },
{ id:'takoyaki',        ko:'타코야키',     en:'Takoyaki',               cuisine:'일식', temp:'hot',  soup:0, spice:0, heavy:1, price:1, speed:'fast', solo:1, share:1, ubiq:2, tags:['분식','야식'] },
{ id:'curry-rice',      ko:'카레라이스',   en:'Japanese curry rice',    cuisine:'일식', temp:'hot',  soup:1, spice:1, heavy:2, price:1, speed:'fast', solo:1, share:0, ubiq:2, tags:['밥','혼밥'] },
{ id:'nabe',            ko:'나베',         en:'Nabe hot pot',           cuisine:'일식', temp:'hot',  soup:3, spice:1, heavy:2, price:3, speed:'sit',  solo:0, share:1, ubiq:1, tags:['국물','겨울'] },

// ── 양식 ─────────────────────────────────────────────────────
{ id:'carbonara',       ko:'까르보나라',   en:'Carbonara',              cuisine:'양식', temp:'hot',  soup:0, spice:0, heavy:3, price:2, speed:'sit',  solo:1, share:0, ubiq:3, tags:['면'] },
{ id:'aglio-olio',      ko:'알리오올리오', en:'Aglio e olio',           cuisine:'양식', temp:'hot',  soup:0, spice:1, heavy:2, price:2, speed:'sit',  solo:1, share:0, ubiq:2, tags:['면'] },
{ id:'rose-pasta',      ko:'로제파스타',   en:'Rosé pasta',             cuisine:'양식', temp:'hot',  soup:0, spice:1, heavy:3, price:2, speed:'sit',  solo:1, share:0, ubiq:3, tags:['면'] },
{ id:'vongole',         ko:'봉골레',       en:'Vongole',                cuisine:'양식', temp:'hot',  soup:1, spice:0, heavy:1, price:2, speed:'sit',  solo:1, share:0, ubiq:2, tags:['면','다이어트'] },
{ id:'tomato-pasta',    ko:'토마토파스타', en:'Tomato pasta',           cuisine:'양식', temp:'hot',  soup:0, spice:1, heavy:2, price:2, speed:'sit',  solo:1, share:0, ubiq:3, tags:['면'] },
{ id:'pizza',           ko:'피자',         en:'Pizza',                  cuisine:'양식', temp:'hot',  soup:0, spice:0, heavy:3, price:2, speed:'sit',  solo:0, share:1, ubiq:3, tags:['야식'] },
{ id:'hamburger',       ko:'햄버거',       en:'Burger',                 cuisine:'양식', temp:'hot',  soup:0, spice:0, heavy:3, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['혼밥'] },
{ id:'sujebeoger',      ko:'수제버거',     en:'Craft burger',           cuisine:'양식', temp:'hot',  soup:0, spice:0, heavy:3, price:2, speed:'sit',  solo:1, share:0, ubiq:2, tags:[] },
{ id:'steak',           ko:'스테이크',     en:'Steak',                  cuisine:'양식', temp:'hot',  soup:0, spice:0, heavy:3, price:3, speed:'sit',  solo:0, share:1, ubiq:2, tags:['고기'] },
{ id:'risotto',         ko:'리조또',       en:'Risotto',                cuisine:'양식', temp:'hot',  soup:1, spice:0, heavy:2, price:2, speed:'sit',  solo:1, share:0, ubiq:2, tags:['밥'] },
{ id:'salad',           ko:'샐러드',       en:'Salad',                  cuisine:'양식', temp:'cold', soup:0, spice:0, heavy:0, price:2, speed:'fast', solo:1, share:0, ubiq:2, tags:['다이어트','혼밥'] },
{ id:'sandwich',        ko:'샌드위치',     en:'Sandwich',               cuisine:'양식', temp:'room', soup:0, spice:0, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:3, tags:['혼밥','다이어트'] },
{ id:'brunch',          ko:'브런치',       en:'Brunch plate',           cuisine:'양식', temp:'hot',  soup:0, spice:0, heavy:2, price:3, speed:'sit',  solo:0, share:1, ubiq:2, tags:[] },
{ id:'fried-chicken',   ko:'후라이드치킨', en:'Fried chicken',          cuisine:'양식', temp:'hot',  soup:0, spice:0, heavy:3, price:2, speed:'sit',  solo:0, share:1, ubiq:3, tags:['야식','술안주'] },
{ id:'yangnyeom-chicken',ko:'양념치킨',    en:'Sweet-spicy chicken',    cuisine:'양식', temp:'hot',  soup:0, spice:2, heavy:3, price:2, speed:'sit',  solo:0, share:1, ubiq:3, tags:['야식','술안주'] },
{ id:'ganjang-chicken', ko:'간장치킨',     en:'Soy-glazed chicken',     cuisine:'양식', temp:'hot',  soup:0, spice:0, heavy:3, price:2, speed:'sit',  solo:0, share:1, ubiq:3, tags:['야식','술안주'] },

// ── 아시안 ───────────────────────────────────────────────────
{ id:'pho',             ko:'쌀국수',       en:'Pho',                    cuisine:'아시안', temp:'hot', soup:3, spice:0, heavy:1, price:2, speed:'fast', solo:1, share:0, ubiq:3, tags:['국물','면','해장','다이어트'] },
{ id:'buncha',          ko:'분짜',         en:'Bun cha',                cuisine:'아시안', temp:'room',soup:1, spice:1, heavy:2, price:2, speed:'sit',  solo:1, share:0, ubiq:1, tags:['면'] },
{ id:'padthai',         ko:'팟타이',       en:'Pad thai',               cuisine:'아시안', temp:'hot', soup:0, spice:1, heavy:2, price:2, speed:'fast', solo:1, share:0, ubiq:2, tags:['면'] },
{ id:'banhmi',          ko:'반미',         en:'Banh mi',                cuisine:'아시안', temp:'room',soup:0, spice:1, heavy:1, price:1, speed:'fast', solo:1, share:0, ubiq:2, tags:['혼밥'] },
{ id:'tomyum',          ko:'똠얌꿍',       en:'Tom yum goong',          cuisine:'아시안', temp:'hot', soup:3, spice:3, heavy:1, price:2, speed:'sit',  solo:0, share:1, ubiq:1, tags:['국물'] },
{ id:'curry-indian',    ko:'커리',         en:'Indian curry',           cuisine:'아시안', temp:'hot', soup:1, spice:2, heavy:2, price:2, speed:'sit',  solo:1, share:1, ubiq:2, tags:['밥'] },
{ id:'kebab',           ko:'케밥',         en:'Kebab',                  cuisine:'아시안', temp:'room',soup:0, spice:1, heavy:2, price:1, speed:'fast', solo:1, share:0, ubiq:2, tags:['혼밥','야식'] },
{ id:'burrito',         ko:'부리토',       en:'Burrito',                cuisine:'아시안', temp:'room',soup:0, spice:1, heavy:3, price:2, speed:'fast', solo:1, share:0, ubiq:1, tags:['혼밥'] },
{ id:'taco',            ko:'타코',         en:'Tacos',                  cuisine:'아시안', temp:'room',soup:0, spice:1, heavy:2, price:2, speed:'sit',  solo:0, share:1, ubiq:1, tags:[] }
];
