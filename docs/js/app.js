// Reads schedule.json (generated locally by scripts/generate.py) and
// renders today's 50 products, the 31-day calendar, and the seasonal
// alerts list. No server involved -- everything here runs in the
// browser against a static JSON file.

const MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December"];
const WEEKDAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];

const SEASON_BADGES = {
  PEAK: { emoji: "\u{1F534}", label: "PEAK" },     // red
  HIGH: { emoji: "\u{1F7E1}", label: "HIGH" },     // yellow
  NORMAL: { emoji: "⚪", label: "NORMAL" },     // white
  LOW: { emoji: "\u{1F535}", label: "LOW" },       // blue
  OFF: { emoji: "⚫", label: "OFF" },          // black
};

let scheduleData = null;
let viewedDay = null;

// fetch() returns a Promise -- it resolves once the browser has the
// response, but the response body itself needs a second await (.json())
// to actually parse. async/await just lets us write this top-to-bottom
// instead of chaining .then() callbacks.
async function loadSchedule() {
  const response = await fetch("schedule.json");
  if (!response.ok) {
    throw new Error(`schedule.json returned ${response.status}`);
  }
  return response.json();
}

function todayDayOfMonth() {
  return new Date().getDate(); // 1-31, matches how algorithm.py assigned schedule days
}

function renderHeader() {
  const now = new Date();
  const day = todayDayOfMonth();
  document.getElementById("day-heading").textContent = `Day ${day} of 31`;
  document.getElementById("date-line").textContent =
    `${WEEKDAY_NAMES[now.getDay()]} ${now.getDate()} ${MONTH_NAMES[now.getMonth()]} ${now.getFullYear()}`;
}

// Counts PEAK products within TODAY'S 50-product list specifically,
// not the whole 31-day cycle's alert backlog -- a pharmacy can
// genuinely have hundreds of products in peak season during summer,
// so a whole-catalog count would be a permanently alarming, useless
// number. Tying it to today's actual list keeps it small and actionable.
function renderSeasonalBanner(todayProducts) {
  const banner = document.getElementById("seasonal-banner");
  const peakCount = todayProducts.filter((p) => p.si_category === "PEAK").length;
  if (peakCount === 0) {
    banner.classList.add("hidden");
    return;
  }
  banner.textContent = `⚠ ${peakCount} of today's products are entering PEAK season — check below`;
  banner.classList.remove("hidden");
}

function badgeHtml(category) {
  const badge = SEASON_BADGES[category] || SEASON_BADGES.NORMAL;
  return `<span class="badge badge-${category}">${badge.emoji} ${badge.label}</span>`;
}

function renderDay(day) {
  viewedDay = day;
  const products = (scheduleData.days[String(day)] || { products: [] }).products;

  document.getElementById("viewing-label").textContent =
    day === todayDayOfMonth() ? "Today's products" : `Day ${day} products`;

  const tbody = document.getElementById("products-tbody");
  const emptyMsg = document.getElementById("empty-day-message");
  tbody.innerHTML = "";

  // Defensive: schedule.json should always have all 31 day keys, but
  // if it's ever malformed or only partially generated, show a clear
  // message instead of silently rendering a blank table.
  if (products.length === 0) {
    emptyMsg.textContent = `No products scheduled for day ${day}.`;
    emptyMsg.classList.remove("hidden");
  } else {
    emptyMsg.classList.add("hidden");
    products.forEach((p, i) => {
      const row = document.createElement("tr");
      row.innerHTML = `
        <td>${i + 1}</td>
        <td>${p.name}</td>
        <td>${p.recommended_qty}</td>
        <td>${badgeHtml(p.si_category)}</td>
      `;
      tbody.appendChild(row);
    });
  }

  document.querySelectorAll(".calendar-day").forEach((btn) => {
    btn.classList.toggle("selected", Number(btn.dataset.day) === day);
  });
}

function renderCalendar() {
  const grid = document.getElementById("calendar-grid");
  grid.innerHTML = "";
  const today = todayDayOfMonth();
  for (let day = 1; day <= 31; day++) {
    const btn = document.createElement("button");
    btn.className = "calendar-day";
    btn.dataset.day = day;
    btn.textContent = day;
    if (day === today) btn.classList.add("today");
    btn.addEventListener("click", () => renderDay(day));
    grid.appendChild(btn);
  }
}

function renderAlerts(alerts) {
  document.getElementById("alerts-count").textContent = alerts.length;
  const list = document.getElementById("alerts-list");
  list.innerHTML = alerts
    .map(
      (a) => `
      <div class="alert-row">
        ${badgeHtml(a.category)}
        <strong>${a.product}</strong>
        — peak in ${a.month_name}, suggested ${a.suggested_multiplier}x normal qty
        (${a.confidence} confidence, ${a.days_away} days away)
      </div>`
    )
    .join("");
}

// Builds a CSV in-browser (no server) and triggers a download via a
// temporary object URL -- this is the standard way to let users save
// a file from purely client-side JavaScript.
function downloadCsv() {
  const products = (scheduleData.days[String(viewedDay)] || { products: [] }).products;
  const header = "Product Name,Recommended Qty,Seasonal Index,Season,Velocity";
  const rows = products.map(
    (p) => `"${p.name}",${p.recommended_qty},${p.si},${p.si_category},${p.velocity}`
  );
  const csv = [header, ...rows].join("\n");

  const blob = new Blob([csv], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `day-${viewedDay}-products.csv`;
  link.click();
  URL.revokeObjectURL(url);
}

function showStatus(message, isError) {
  const el = document.getElementById("status-message");
  el.textContent = message;
  el.classList.remove("hidden");
  el.classList.toggle("status-error", Boolean(isError));
  document.getElementById("main-content").classList.add("hidden");
}

function hideStatus() {
  document.getElementById("status-message").classList.add("hidden");
  document.getElementById("main-content").classList.remove("hidden");
}

function renderLastUpdated() {
  document.getElementById("last-updated").textContent = `Last updated: ${scheduleData.generated_on}`;
}

async function init() {
  renderHeader();
  showStatus("Loading schedule...");

  try {
    scheduleData = await loadSchedule();
  } catch (err) {
    // Most likely cause: generate.py hasn't been run yet, so
    // docs/schedule.json doesn't exist (fetch returns a 404).
    showStatus("No schedule found — has generate.py been run yet?", true);
    return;
  }

  hideStatus();
  renderLastUpdated();

  const todayProducts = (scheduleData.days[String(todayDayOfMonth())] || { products: [] }).products;
  renderSeasonalBanner(todayProducts);
  renderCalendar();
  renderDay(todayDayOfMonth());
  renderAlerts(scheduleData.alerts);

  document.getElementById("download-csv").addEventListener("click", downloadCsv);
  document.getElementById("toggle-alerts").addEventListener("click", () => {
    document.getElementById("alerts-list").classList.toggle("hidden");
  });
}

init();
