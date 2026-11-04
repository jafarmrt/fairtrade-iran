/*
 * Persian file fields. The browser draws <input type="file"> in the language of the
 * computer, so on most machines in Iran a Persian form said "Choose File / No file chosen".
 * On Persian pages each visible file field gets a «انتخاب فایل» button and the chosen
 * file's name beside it; the real input stays in the form (hidden) and is what is sent.
 * Loaded by the site (templates/base.html) and the admin (core/wagtail_hooks.py).
 */
(function () {
  "use strict";
  if ((document.documentElement.lang || "").slice(0, 2) !== "fa") return;

  function digits(text) {
    return String(text).replace(/[0-9]/g, function (d) { return "۰۱۲۳۴۵۶۷۸۹"[d]; });
  }

  function enhance(input) {
    if (input.dataset.ftFile || input.dataset.ftNative !== undefined) return;
    // Wagtail's own styled upload buttons (drop zones) already have Persian text.
    if (input.closest(".replace-file-input, .drop-zone, .ft-file")) return;
    var style = getComputedStyle(input);
    if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0" || !input.offsetWidth) return;
    input.dataset.ftFile = "1";

    var box = document.createElement("span");
    box.className = "ft-file";
    var button = document.createElement("button");
    button.type = "button";
    button.className = "ft-file__button";
    button.textContent = input.multiple ? "انتخاب فایل‌ها" : "انتخاب فایل";
    var name = document.createElement("span");
    name.className = "ft-file__name";
    name.setAttribute("aria-live", "polite");

    function show() {
      var files = input.files || [];
      if (!files.length) name.textContent = "فایلی انتخاب نشده";
      else if (files.length === 1) name.textContent = files[0].name;
      else name.textContent = digits(files.length) + " فایل انتخاب شد";
    }

    // The visible button names the field for screen readers, like the input did.
    var label = input.id && document.querySelector('label[for="' + input.id + '"]');
    if (label) button.setAttribute("aria-label", label.textContent.trim() + "، " + button.textContent);
    if (input.disabled) button.disabled = true;

    input.parentNode.insertBefore(box, input);
    box.appendChild(button);
    box.appendChild(name);
    box.appendChild(input);
    input.classList.add("ft-file__input");
    input.tabIndex = -1;
    button.addEventListener("click", function () { input.click(); });
    input.addEventListener("change", show);
    // The browser keeps a chosen file after "back"; and a form reset empties it.
    if (input.form) input.form.addEventListener("reset", function () { setTimeout(show, 0); });
    show();
  }

  function scan(root) {
    if (root.matches && root.matches('input[type="file"]')) enhance(root);
    if (root.querySelectorAll) root.querySelectorAll('input[type="file"]').forEach(enhance);
  }

  function start() {
    scan(document);
    // Admin forms add fields later (inline panels, «افزودن» in a list of images).
    new MutationObserver(function (records) {
      records.forEach(function (r) { r.addedNodes.forEach(function (n) { if (n.nodeType === 1) scan(n); }); });
    }).observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
