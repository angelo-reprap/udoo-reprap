#!/usr/bin/env node
/**
 * Erzeugt i18n/<lang>/timezone.json für alle CRM-Sprachen.
 * Quelle: Intl.supportedValuesOf('timeZone') + UTC
 *
 *   node Repo_abpe/abpe_crm/incoming/bin/generate_timezone_i18n.js
 */
'use strict';

const fs = require('fs');
const path = require('path');

const ROOT = path.resolve(__dirname, '../i18n');
const LANGS = ['de', 'en', 'fr', 'es', 'it', 'pt', 'nl', 'pl', 'ru', 'tr', 'ar', 'zh', 'ja', 'ko'];

const UI = {
  de: { title: 'Zeitzone', region: 'Region', zone: 'Zeitzone', hint: 'Alle IANA-Zeitzonen. Termine und E-Mails werden in dieser Zeitzone angezeigt. Standard: Europa → Berlin.', search: 'Zeitzone suchen…', custom: 'Gespeicherte Zeitzone' },
  en: { title: 'Time zone', region: 'Region', zone: 'Time zone', hint: 'All IANA time zones. Meetings and emails use this zone. Default: Europe → Berlin.', search: 'Search time zone…', custom: 'Saved time zone' },
  fr: { title: 'Fuseau horaire', region: 'Région', zone: 'Fuseau horaire', hint: 'Tous les fuseaux IANA. Les rendez-vous et e-mails utilisent ce fuseau. Défaut : Europe → Berlin.', search: 'Rechercher un fuseau…', custom: 'Fuseau enregistré' },
  es: { title: 'Zona horaria', region: 'Región', zone: 'Zona horaria', hint: 'Todas las zonas IANA. Citas y correos usan esta zona. Predeterminado: Europa → Berlín.', search: 'Buscar zona horaria…', custom: 'Zona guardada' },
  it: { title: 'Fuso orario', region: 'Regione', zone: 'Fuso orario', hint: 'Tutti i fusi IANA. Appuntamenti ed e-mail usano questo fuso. Predefinito: Europa → Berlino.', search: 'Cerca fuso orario…', custom: 'Fuso salvato' },
  pt: { title: 'Fuso horário', region: 'Região', zone: 'Fuso horário', hint: 'Todos os fusos IANA. Reuniões e e-mails usam este fuso. Padrão: Europa → Berlim.', search: 'Pesquisar fuso…', custom: 'Fuso guardado' },
  nl: { title: 'Tijdzone', region: 'Regio', zone: 'Tijdzone', hint: 'Alle IANA-tijdzones. Afspraken en e-mails gebruiken deze zone. Standaard: Europa → Berlijn.', search: 'Tijdzone zoeken…', custom: 'Opgeslagen tijdzone' },
  pl: { title: 'Strefa czasowa', region: 'Region', zone: 'Strefa czasowa', hint: 'Wszystkie strefy IANA. Terminy i e-maile w tej strefie. Domyślnie: Europa → Berlin.', search: 'Szukaj strefy…', custom: 'Zapisana strefa' },
  ru: { title: 'Часовой пояс', region: 'Регион', zone: 'Часовой пояс', hint: 'Все часовые пояса IANA. Встречи и письма в этом поясе. По умолчанию: Европа → Берлин.', search: 'Поиск пояса…', custom: 'Сохранённый пояс' },
  tr: { title: 'Saat dilimi', region: 'Bölge', zone: 'Saat dilimi', hint: 'Tüm IANA saat dilimleri. Randevular ve e-postalar bu dilimde. Varsayılan: Avrupa → Berlin.', search: 'Saat dilimi ara…', custom: 'Kayıtlı dilim' },
  ar: { title: 'المنطقة الزمنية', region: 'المنطقة', zone: 'المنطقة الزمنية', hint: 'جميع المناطق IANA. المواعيد والبريد بهذه المنطقة. الافتراضي: أوروبا → برlin.', search: 'بحث…', custom: 'منطقة محفوظة' },
  zh: { title: '时区', region: '地区', zone: '时区', hint: '全部 IANA 时区。约会和邮件使用此时区。默认：欧洲 → 柏林。', search: '搜索时区…', custom: '已保存的时区' },
  ja: { title: 'タイムゾーン', region: '地域', zone: 'タイムゾーン', hint: 'すべての IANA タイムゾーン。予定とメールに使用。既定：ヨーロッパ → ベルリン。', search: 'タイムゾーンを検索…', custom: '保存済み' },
  ko: { title: '시간대', region: '지역', zone: '시간대', hint: '모든 IANA 시간대. 일정과 이메일에 사용. 기본: 유럽 → 베를린.', search: '시간대 검색…', custom: '저장된 시간대' },
};

const GROUPS = {
  de: { Africa: 'Afrika', America: 'Amerika', Antarctica: 'Antarktis', Arctic: 'Arktis', Asia: 'Asien', Atlantic: 'Atlantik', Australia: 'Australien', Europe: 'Europa', Indian: 'Indischer Ozean', Pacific: 'Pazifik', UTC: 'UTC' },
  en: { Africa: 'Africa', America: 'Americas', Antarctica: 'Antarctica', Arctic: 'Arctic', Asia: 'Asia', Atlantic: 'Atlantic', Australia: 'Australia', Europe: 'Europe', Indian: 'Indian Ocean', Pacific: 'Pacific', UTC: 'UTC' },
  fr: { Africa: 'Afrique', America: 'Amériques', Antarctica: 'Antarctique', Arctic: 'Arctique', Asia: 'Asie', Atlantic: 'Atlantique', Australia: 'Australie', Europe: 'Europe', Indian: 'Océan Indien', Pacific: 'Pacifique', UTC: 'UTC' },
  es: { Africa: 'África', America: 'Américas', Antarctica: 'Antártida', Arctic: 'Ártico', Asia: 'Asia', Atlantic: 'Atlántico', Australia: 'Australia', Europe: 'Europa', Indian: 'Océano Índico', Pacific: 'Pacífico', UTC: 'UTC' },
  it: { Africa: 'Africa', America: 'Americhe', Antarctica: 'Antartide', Arctic: 'Artico', Asia: 'Asia', Atlantic: 'Atlantico', Australia: 'Australia', Europe: 'Europa', Indian: 'Oceano Indiano', Pacific: 'Pacifico', UTC: 'UTC' },
  pt: { Africa: 'África', America: 'Américas', Antarctica: 'Antártida', Arctic: 'Ártico', Asia: 'Ásia', Atlantic: 'Atlântico', Australia: 'Austrália', Europe: 'Europa', Indian: 'Oceano Índico', Pacific: 'Pacífico', UTC: 'UTC' },
  nl: { Africa: 'Afrika', America: 'Amerika', Antarctica: 'Antarctica', Arctic: 'Arctisch', Asia: 'Azië', Atlantic: 'Atlantische Oceaan', Australia: 'Australië', Europe: 'Europa', Indian: 'Indische Oceaan', Pacific: 'Stille Oceaan', UTC: 'UTC' },
  pl: { Africa: 'Afryka', America: 'Ameryka', Antarctica: 'Antarktyda', Arctic: 'Arktyka', Asia: 'Azja', Atlantic: 'Atlantyk', Australia: 'Australia', Europe: 'Europa', Indian: 'Ocean Indyjski', Pacific: 'Pacyfik', UTC: 'UTC' },
  ru: { Africa: 'Африка', America: 'Америка', Antarctica: 'Антарктида', Arctic: 'Арктика', Asia: 'Азия', Atlantic: 'Атлантика', Australia: 'Австралия', Europe: 'Европа', Indian: 'Индийский океан', Pacific: 'Тихий океан', UTC: 'UTC' },
  tr: { Africa: 'Afrika', America: 'Amerika', Antarctica: 'Antarktika', Arctic: 'Arktik', Asia: 'Asya', Atlantic: 'Atlantik', Australia: 'Avustralya', Europe: 'Avrupa', Indian: 'Hint Okyanusu', Pacific: 'Pasifik', UTC: 'UTC' },
  ar: { Africa: 'أفريقيا', America: 'الأمريكتان', Antarctica: 'القارة القطبية', Arctic: 'القطب الشمالي', Asia: 'آسيا', Atlantic: 'الأطلسي', Australia: 'أستراليا', Europe: 'أوروبا', Indian: 'المحيط الهندي', Pacific: 'المحيط الهادئ', UTC: 'UTC' },
  zh: { Africa: '非洲', America: '美洲', Antarctica: '南极洲', Arctic: '北极', Asia: '亚洲', Atlantic: '大西洋', Australia: '澳大利亚', Europe: '欧洲', Indian: '印度洋', Pacific: '太平洋', UTC: 'UTC' },
  ja: { Africa: 'アフリカ', America: 'アメリカ', Antarctica: '南極', Arctic: '北極', Asia: 'アジア', Atlantic: '大西洋', Australia: 'オーストラリア', Europe: 'ヨーロッパ', Indian: 'インド洋', Pacific: '太平洋', UTC: 'UTC' },
  ko: { Africa: '아프리카', America: '아메리카', Antarctica: '남극', Arctic: '북극', Asia: '아시아', Atlantic: '대서양', Australia: '호주', Europe: '유럽', Indian: '인도양', Pacific: '태평양', UTC: 'UTC' },
};

function allTimezones() {
  const list = Intl.supportedValuesOf('timeZone').slice();
  if (!list.includes('UTC')) list.push('UTC');
  list.sort();
  return list;
}

function groupOf(tzId) {
  if (tzId === 'UTC') return 'UTC';
  const i = tzId.indexOf('/');
  return i > 0 ? tzId.slice(0, i) : tzId;
}

function cityPart(tzId) {
  if (tzId === 'UTC') return 'UTC';
  return tzId.split('/').slice(1).join(' / ').replace(/_/g, ' ');
}

function zoneLabel(tzId, lang) {
  if (tzId === 'UTC') {
    const u = { de: 'Koordinierte Weltzeit (UTC)', en: 'Coordinated Universal Time (UTC)', fr: 'Temps universel coordonné (UTC)' };
    return u[lang] || u.en;
  }
  const city = cityPart(tzId);
  let tzName = '';
  try {
    const parts = new Intl.DateTimeFormat(lang, { timeZone: tzId, timeZoneName: 'longGeneric' }).formatToParts(new Date());
    tzName = (parts.find((p) => p.type === 'timeZoneName') || {}).value || '';
  } catch (e) { /* ignore */ }
  return tzName ? `${city} (${tzName})` : city;
}

function buildBaseIndex(tzList) {
  const groups = {};
  for (const tz of tzList) {
    const g = groupOf(tz);
    if (!groups[g]) groups[g] = [];
    groups[g].push(tz);
  }
  const order = ['UTC', 'Africa', 'America', 'Antarctica', 'Arctic', 'Asia', 'Atlantic', 'Australia', 'Europe', 'Indian', 'Pacific'];
  const sorted = {};
  for (const g of order) {
    if (groups[g]) sorted[g] = groups[g];
  }
  for (const g of Object.keys(groups).sort()) {
    if (!sorted[g]) sorted[g] = groups[g];
  }
  return { version: 1, default: 'Europe/Berlin', count: tzList.length, groups: sorted };
}

function main() {
  const tzList = allTimezones();
  const base = buildBaseIndex(tzList);

  fs.mkdirSync(ROOT, { recursive: true });
  fs.writeFileSync(path.join(ROOT, 'timezone.base.json'), JSON.stringify(base, null, 2) + '\n');
  console.log('Wrote timezone.base.json —', base.count, 'zones');

  for (const lang of LANGS) {
    const groups = { ...(GROUPS[lang] || GROUPS.en) };
    for (const g of Object.keys(base.groups)) {
      if (!groups[g]) groups[g] = g;
    }
    const zones = {};
    for (const tz of tzList) zones[tz] = zoneLabel(tz, lang);

    const out = {
      _meta: { lang, file: 'timezone.json', zones: tzList.length },
      ui: UI[lang] || UI.en,
      groups,
      zones,
    };

    const dir = path.join(ROOT, lang);
    fs.mkdirSync(dir, { recursive: true });
    const file = path.join(dir, 'timezone.json');
    fs.writeFileSync(file, JSON.stringify(out, null, 2) + '\n');
    console.log('Wrote', path.relative(ROOT, file), '—', Object.keys(zones).length, 'labels');
  }
}

main();
