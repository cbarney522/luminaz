/* Counts two things for the founders' daily numbers, with no cookie and nothing stored on the device:
   - "installed": the browser says Luminaz was added to a home screen (Android and desktop Chrome/Edge report this; iPhones do not)
   - "opened": this page was launched from a home-screen icon
   The server keeps one row per visitor per day. See investor.app_event. */
(function () {
  function send(kind) {
    try {
      var data = new FormData();
      data.append("kind", kind);
      if (navigator.sendBeacon) { navigator.sendBeacon("/app-event", data); }
      else { fetch("/app-event", { method: "POST", body: data, keepalive: true }); }
    } catch (e) { /* counting must never break the page */ }
  }
  window.addEventListener("appinstalled", function () { send("installed"); });
  var standalone = (window.matchMedia && window.matchMedia("(display-mode: standalone)").matches) || window.navigator.standalone === true;
  if (standalone) { send("opened"); }
})();

/* Display choices from the Accessibility page (change 41). Kept in this browser only (localStorage); nothing is sent to the server. */
(function () {
  var KEY = "lz-display", root = document.documentElement, sizes = ["lz-small", "", "lz-large", "lz-xlarge"];
  function load() { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch (e) { return {}; } }
  function save(v) { try { localStorage.setItem(KEY, JSON.stringify(v)); } catch (e) { /* private mode: the choice lasts for this page only */ } }
  function apply(v) {
    sizes.forEach(function (c) { if (c) { root.classList.remove(c); } });
    var i = typeof v.size === "number" ? v.size : 1;
    if (sizes[i]) { root.classList.add(sizes[i]); }
    root.classList.toggle("lz-contrast", !!v.contrast);
  }
  var state = load(); apply(state);
  document.addEventListener("DOMContentLoaded", function () {
    var buttons = document.querySelectorAll("[data-lz]");
    if (!buttons.length) { return; }
    var status = document.getElementById("lz-status");
    var names = ["Smaller", "Normal", "Larger", "Largest"];
    function sync(msg) {
      var c = document.querySelector('[data-lz="contrast"]');
      if (c) { c.setAttribute("aria-pressed", state.contrast ? "true" : "false"); }
      if (status && msg) { status.textContent = msg; }
    }
    sync("");
    buttons.forEach(function (b) {
      b.addEventListener("click", function () {
        var what = b.getAttribute("data-lz"), i = typeof state.size === "number" ? state.size : 1;
        if (what === "larger") { state.size = Math.min(3, i + 1); }
        if (what === "smaller") { state.size = Math.max(0, i - 1); }
        if (what === "contrast") { state.contrast = !state.contrast; }
        if (what === "reset") { state = {}; }
        save(state); apply(state);
        sync("Text size: " + names[typeof state.size === "number" ? state.size : 1] + ". High contrast: " + (state.contrast ? "on" : "off") + ".");
      });
    });
  });
})();
