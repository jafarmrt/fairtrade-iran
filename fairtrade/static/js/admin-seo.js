/*
 * Length counts under «عنوان سئو» and «توضیحات جست‌وجو» in the page editor («سئو و منو» tab).
 *
 * core/admin_panels.py marks the two fields with data-ft-seo="title" / "description" and
 * passes the site name, the limits and what is used when the field is left empty.
 * Google shows about 60 characters of a title and 160 of a description and cuts the rest.
 */
(function () {
  "use strict";

  var EN = (document.documentElement.lang || "").toLowerCase().indexOf("en") === 0;
  var FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹";
  var SEP = " ";

  function num(n) {
    return EN ? String(n) : String(n).replace(/\d/g, function (d) { return FA_DIGITS[d]; });
  }

  function clean(text) {
    return (text || "").replace(/\s+/g, " ").trim();
  }

  // Characters as a reader sees them: an emoji counts once, and the zero-width
  // non-joiner of Persian words (half-space) and direction marks not at all; they stay
  // attached to the character before them so the preview keeps them.
  var INVISIBLE = /[\u200b-\u200f\u2066-\u2069]/;

  function chars(text) {
    var list = [];
    var pending = "";
    Array.from(text).forEach(function (ch) {
      if (!INVISIBLE.test(ch)) {
        list.push(pending + ch);
        pending = "";
      } else if (list.length) {
        list[list.length - 1] += ch;
      } else {
        pending += ch;
      }
    });
    return list;
  }

  // Text of another field of the page form (the page title, or the summary used as
  // the description). Rich text keeps its content as JSON (Draftail) or HTML.
  function fieldText(form, name) {
    var field = form && form.elements[name];
    if (!field || !field.value) return "";
    if (field.type !== "hidden") return clean(field.value);
    try {
      var data = JSON.parse(field.value);
      if (data && data.blocks) {
        return clean(data.blocks.map(function (block) { return block.text || ""; }).join(" "));
      }
    } catch (error) { /* not JSON: HTML */ }
    return clean(new DOMParser().parseFromString(field.value, "text/html").body.textContent);
  }

  var T = EN ? {
    count: function (n, max) { return n + " characters (Google shows about " + max + ")."; },
    titleEmpty: "Empty: the page title is used. ",
    titleOk: "Google shows all of it.",
    titleSiteCut: "The end of the site name is cut, which is fine.",
    titleLong: function (over) { return over + " characters at the end are cut in Google. Write a shorter title."; },
    titleNone: "Write the page title first (in the Content tab).",
    preview: "In search results:",
    descOk: "A good length.",
    descShort: function (min, max) { return "Short: " + min + " to " + max + " characters is better."; },
    descLong: function (over) { return over + " characters at the end are cut in Google."; },
    descFallback: function (label, n) {
      return "Empty: the page's “" + label + "” (" + n + " characters) is used instead. A description of its own is better.";
    },
    descDefault: "Empty: the site's default description (Settings › SEO) is used, the same for every page. Write one for this page.",
    descNone: "Empty: no description is sent, and Google picks a piece of the page text itself."
  } : {
    count: function (n, max) { return num(n) + " نویسه (گوگل حدود " + num(max) + " تا را نشان می‌دهد)."; },
    titleEmpty: "خالی است؛ عنوان صفحه به کار می‌رود. ",
    titleOk: "همه‌اش در گوگل دیده می‌شود.",
    titleSiteCut: "انتهای نام سایت بریده می‌شود که اشکالی ندارد.",
    titleLong: function (over) { return num(over) + " نویسهٔ آخر در گوگل بریده می‌شود. عنوان کوتاه‌تری بنویسید."; },
    titleNone: "اول عنوان صفحه را در زبانهٔ «محتوا» بنویسید.",
    preview: "در نتیجهٔ جست‌وجو:",
    descOk: "اندازه‌اش خوب است.",
    descShort: function (min, max) { return "کوتاه است؛ " + num(min) + " تا " + num(max) + " نویسه بهتر است."; },
    descLong: function (over) { return num(over) + " نویسهٔ آخر در گوگل بریده می‌شود."; },
    descFallback: function (label, n) {
      return "خالی است؛ به جای آن «" + label + "» صفحه (" + num(n) + " نویسه) به کار می‌رود. بهتر است توضیحی جدا بنویسید.";
    },
    descDefault: "خالی است؛ توضیح پیش‌فرض سایت (تنظیمات › سئو) به کار می‌رود که برای همهٔ صفحه‌ها یکی است. برای این صفحه توضیحی بنویسید.",
    descNone: "خالی است و توضیحی فرستاده نمی‌شود؛ گوگل خودش تکه‌ای از متن صفحه را برمی‌دارد."
  };

  function setStatus(box, state, text) {
    box.dataset.state = state;
    box.querySelector(".ft-seo-count__status").textContent = text;
  }

  // The title as Google shows it: the part that fits, then the cut part struck through.
  function setPreview(box, list, max) {
    var preview = box.querySelector(".ft-seo-count__preview");
    var shown = preview.querySelector("bdi");
    shown.textContent = list.slice(0, max).join("");
    if (list.length > max) {
      var cut = document.createElement("s");
      cut.textContent = list.slice(max).join("");
      shown.appendChild(cut);
    }
    preview.hidden = list.length === 0;
  }

  function updateTitle(input, box) {
    var max = Number(input.dataset.ftSeoMax);
    var site = input.dataset.ftSeoSite || "";
    var own = clean(input.value);
    var title = own || fieldText(input.form, "title");
    if (!title) {
      setStatus(box, "empty", T.titleNone);
      setPreview(box, [], max);
      return;
    }
    // As fairtrade/templates/base.html builds <title>.
    var full = site && title !== site ? title + " | " + site : title;
    var list = chars(full);
    var prefix = own ? "" : T.titleEmpty;
    var state = "ok";
    var verdict = T.titleOk;
    if (list.length > max) {
      if (chars(title).length + 3 < max) {
        verdict = T.titleSiteCut;
      } else {
        state = "long";
        verdict = T.titleLong(list.length - max);
      }
    }
    setStatus(box, state, prefix + T.count(list.length, max) + SEP + verdict);
    setPreview(box, list, max);
  }

  function updateDescription(input, box) {
    var min = Number(input.dataset.ftSeoMin);
    var max = Number(input.dataset.ftSeoMax);
    var text = clean(input.value);
    if (!text) {
      var fallbacks = [];
      try { fallbacks = JSON.parse(input.dataset.ftSeoFallback || "[]"); } catch (error) { /* none */ }
      for (var i = 0; i < fallbacks.length; i++) {
        var value = fieldText(input.form, fallbacks[i][0]);
        if (value) {
          setStatus(box, "empty", T.descFallback(fallbacks[i][1], chars(value).length));
          return;
        }
      }
      setStatus(box, "warn", input.dataset.ftSeoDefault ? T.descDefault : T.descNone);
      return;
    }
    var n = chars(text).length;
    if (n < min) setStatus(box, "warn", T.count(n, max) + SEP + T.descShort(min, max));
    else if (n > max) setStatus(box, "long", T.count(n, max) + SEP + T.descLong(n - max));
    else setStatus(box, "ok", T.count(n, max) + SEP + T.descOk);
  }

  var fields = [];

  function updateAll() {
    fields.forEach(function (item) {
      (item.input.dataset.ftSeo === "title" ? updateTitle : updateDescription)(item.input, item.box);
    });
  }

  function init() {
    var inputs = document.querySelectorAll("[data-ft-seo]");
    if (!inputs.length) return;
    Array.prototype.forEach.call(inputs, function (input, index) {
      var box = document.createElement("div");
      box.className = "ft-seo-count";
      box.innerHTML = '<p class="ft-seo-count__status"></p>' +
        '<p class="ft-seo-count__preview" hidden><span></span> <bdi></bdi></p>';
      box.querySelector(".ft-seo-count__status").id = "ft-seo-count-" + index;
      if (input.dataset.ftSeo === "title") {
        box.querySelector(".ft-seo-count__preview span").textContent = T.preview;
      } else {
        box.querySelector(".ft-seo-count__preview").remove();
      }
      input.insertAdjacentElement("afterend", box);
      // Screen readers read the count when the field is focused (not at every key press).
      var described = input.getAttribute("aria-describedby");
      input.setAttribute("aria-describedby", (described ? described + " " : "") + "ft-seo-count-" + index);
      fields.push({ input: input, box: box });
    });
    updateAll();
    // The page title and summary are on another tab; rich text changes fire no input event,
    // so the counts are also refreshed when a tab is opened.
    var form = inputs[0].form || document;
    form.addEventListener("input", updateAll);
    form.addEventListener("change", updateAll);
    document.addEventListener("click", function (event) {
      if (event.target.closest && event.target.closest('[role="tab"]')) window.setTimeout(updateAll, 0);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
