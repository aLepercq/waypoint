"use strict";

// Polls the API every 15 s and redraws every second from the last answer, so
// the countdown stays live between polls. Times come from the server clock.
const POLL_MS = 15000;
const WINDOW_MIN = 45;
const TZ = "Europe/Paris";

const $ = (id) => document.getElementById(id);
const board = document.querySelector(".board");
const hhmm = new Intl.DateTimeFormat("fr-FR", { hour: "2-digit", minute: "2-digit", timeZone: TZ });

let data = null;
let clockOffset = 0; // server time minus local time
let lastOk = null;
let fetchFailed = false;

const now = () => Date.now() + clockOffset;
const fmt = (d) => hhmm.format(d);
const minutesFloor = (ms) => Math.max(0, Math.floor(ms / 60000));
const minutesCeil = (ms) => Math.max(0, Math.ceil(ms / 60000));

function el(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function delayText(seconds, realtime) {
  if (!realtime) return "horaire prévu";
  if (Math.abs(seconds) < 45) return "à l'heure";
  const m = Math.max(1, Math.round(Math.abs(seconds) / 60));
  return seconds > 0 ? `${m} min de retard` : `${m} min d'avance`;
}

function parse(d) {
  return {
    dep: new Date(d.departure),
    leave: new Date(d.leave_at),
    arrival: d.arrival ? new Date(d.arrival) : null,
    travel: d.travel_minutes,
    delay: d.delay_seconds,
    realtime: d.realtime,
  };
}

function renderHero(hero, t) {
  const verdict = $("verdict");
  const num = $("num");
  const unit = $("unit");

  if (!hero) {
    board.dataset.state = data ? "none" : "loading";
    verdict.textContent = data ? "Pas de bus annoncé pour l'instant" : "Chargement des horaires";
    num.textContent = "";
    unit.textContent = "";
    return;
  }

  const leaveIn = hero.leave - t;
  const busIn = hero.dep - t;
  if (leaveIn >= 90 * 60000) {
    board.dataset.state = "wait";
    verdict.textContent = "Pars à";
    num.textContent = fmt(hero.leave);
    unit.textContent = "";
  } else if (leaveIn >= 60000) {
    board.dataset.state = "wait";
    verdict.textContent = "Pars dans";
    num.textContent = String(minutesFloor(leaveIn));
    unit.textContent = "min";
  } else {
    board.dataset.state = leaveIn >= 0 ? "now" : "hurry";
    verdict.textContent = leaveIn >= 0
      ? "Pars maintenant, le bus passe dans"
      : "Presse le pas, le bus passe dans";
    num.textContent = String(minutesCeil(busIn));
    unit.textContent = "min";
  }

  const bus = $("bus-time");
  bus.replaceChildren(fmt(hero.dep), el("span", delayText(hero.delay, hero.realtime), "delay"));
  $("arrival-label").textContent = `Arrivée ${data.destination}`;
  const arr = $("arrival-time");
  if (hero.arrival) {
    arr.replaceChildren(fmt(hero.arrival), el("span", `${hero.travel} min de trajet`, "delay"));
  } else {
    arr.textContent = "durée inconnue";
  }
}

function renderTrack(deps, hero, t) {
  const track = $("track");
  const span = WINDOW_MIN * 60000;
  const pos = (date) => `${((date - t) / span) * 100}%`;
  const inside = (date) => date - t >= 0 && date - t <= span;
  const nodes = [];

  // A tick every 10 minutes, on round times; none at the very edge, where its
  // centred label would overflow the screen.
  const first = Math.ceil(t / 600000) * 600000;
  for (let ms = first; ms <= t + span * 0.92; ms += 600000) {
    const tick = el("div", undefined, "tick");
    tick.style.left = pos(new Date(ms));
    tick.append(el("span", fmt(new Date(ms))));
    nodes.push(tick);
  }

  if (hero) {
    const start = Math.max(hero.leave.getTime(), t);
    if (hero.dep - start > 0 && inside(hero.dep)) {
      const walk = el("div", undefined, "walk");
      walk.style.left = pos(new Date(start));
      walk.style.width = `${((hero.dep - start) / span) * 100}%`;
      nodes.push(walk);
    }
  }

  for (const d of deps) {
    if (!inside(d.dep)) continue;
    const dot = el("div", undefined, d === hero ? "bus next" : "bus");
    dot.style.left = pos(d.dep);
    dot.append(el("span", fmt(d.dep)));
    nodes.push(dot);
  }
  track.replaceChildren(...nodes);
}

function renderLater(deps, hero, t) {
  const items = deps
    .filter((d) => d !== hero)
    .slice(0, 3)
    .map((d) => {
      const missed = hero ? d.dep < hero.dep : true;
      const li = el("li", undefined, missed ? "missed" : "");
      li.append(el("strong", fmt(d.dep)));
      li.append(el("span", missed ? "trop tard pour celui-ci" : `pars dans ${minutesFloor(d.leave - t)} min`));
      const detail = d.arrival
        ? `${data.destination} à ${fmt(d.arrival)}, ${delayText(d.delay, d.realtime)}`
        : delayText(d.delay, d.realtime);
      li.append(el("small", detail));
      return li;
    });
  if (!items.length) items.push(el("li", "Aucun autre passage annoncé", "empty"));
  $("later").replaceChildren(...items);
}

function renderStatus(t) {
  const status = $("status");
  const parts = [];
  let warn = false;
  if (fetchFailed && (!lastOk || t - lastOk > 60000)) {
    parts.push("Serveur waypoint injoignable : affichage des dernières données reçues.");
    warn = true;
  }
  if (data) {
    const fetched = data.fetched_at ? new Date(data.fetched_at) : null;
    if (!fetched) {
      parts.push("En attente de la première réponse de Naolib.");
      warn = Boolean(data.error);
    } else if (data.error || t - fetched > 120000) {
      parts.push(`Flux Naolib indisponible, données de ${fmt(fetched)}.`);
      warn = true;
    } else {
      parts.push(`Temps réel Naolib, mis à jour il y a ${Math.max(0, Math.round((t - fetched) / 1000))} s.`);
    }
    if (!data.gtfs_loaded_at) parts.push("Durées de trajet en cours de chargement.");
  }
  status.textContent = parts.join(" ");
  status.classList.toggle("warn", warn);
}

function render() {
  const t = now();
  $("clock").textContent = fmt(new Date(t));
  if (data) {
    $("line").textContent = data.line;
    $("stop").textContent = data.stop;
    $("destination").textContent = data.destination;
  }
  const walkMs = (data ? data.walk_minutes : 3) * 60000;
  const deps = data ? data.departures.map(parse).filter((d) => d.dep - t > -30000) : [];
  // Catchable: the walk fits, give or take a minute of brisk walking.
  const hero = deps.find((d) => d.dep - t >= walkMs - 60000) || null;
  renderHero(hero, t);
  renderTrack(deps, hero, t);
  renderLater(deps, hero, t);
  renderStatus(t);
}

async function poll() {
  try {
    const response = await fetch("/api/next", { cache: "no-store" });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const body = await response.json();
    clockOffset = new Date(body.now).getTime() - Date.now();
    data = body;
    lastOk = now();
    fetchFailed = false;
  } catch (err) {
    fetchFailed = true;
  }
  render();
}

poll();
setInterval(poll, POLL_MS);
setInterval(render, 1000);
