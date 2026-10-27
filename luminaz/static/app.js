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
