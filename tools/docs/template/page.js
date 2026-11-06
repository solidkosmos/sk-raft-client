/*
 * The navigation and the search of the documentation file.
 *
 * Each page of the documentation is a <section class="sk-page">. The
 * address after "#" selects the page to show: the id of a page, or the id
 * of an element in a page. The search index is in the <script id="sk-index">
 * element. It is a list of [target id, title, page title, text].
 */
(function () {
  "use strict";

  var SITE = document.title;
  var HOME = document.querySelector(".sk-title").getAttribute("href").slice(1);
  var INDEX = JSON.parse(document.getElementById("sk-index").textContent);
  var MAX_RESULTS = 30;

  var nav = document.getElementById("sk-nav");
  var menu = document.querySelector(".sk-menu");
  var query = document.getElementById("sk-query");
  var results = document.getElementById("sk-results");
  var current = null;
  var foundTerms = [];

  /* Pages */

  function show(hash) {
    var id = "";
    try {
      id = decodeURIComponent((hash || "").replace(/^#/, ""));
    } catch (e) {
      id = "";
    }
    var target = id ? document.getElementById(id) : null;
    var page = target ? target.closest(".sk-page") : null;
    if (!page) {
      target = page = document.getElementById(HOME);
    }
    if (page !== current) {
      if (current) {
        current.classList.remove("sk-current");
      }
      page.classList.add("sk-current");
      current = page;
      document.title = page.dataset.title + " - " + SITE;
      selectNavLink(page.id);
    }
    unmark();
    if (foundTerms.length) {
      mark(page, foundTerms);
      foundTerms = [];
    }
    /* The theme scrolls smoothly. A jump to another page must not. */
    if (target === page) {
      window.scrollTo({ top: 0, behavior: "instant" });
    } else {
      target.scrollIntoView({ behavior: "instant" });
    }
  }

  function selectNavLink(pageId) {
    var active = nav.querySelector("a.sk-active");
    if (active) {
      active.classList.remove("sk-active");
    }
    var link = nav.querySelector('a[href="#' + CSS.escape(pageId) + '"]');
    if (!link) {
      return;
    }
    link.classList.add("sk-active");
    for (var el = link.parentElement; el && el !== nav; el = el.parentElement) {
      if (el.tagName === "DETAILS") {
        el.open = true;
      }
    }
  }

  window.addEventListener("hashchange", function () {
    show(location.hash);
  });

  nav.addEventListener("click", function (event) {
    if (event.target.closest("a")) {
      setMenu(false);
    }
  });

  function setMenu(open) {
    nav.classList.toggle("sk-open", open);
    menu.setAttribute("aria-expanded", String(open));
  }

  menu.addEventListener("click", function () {
    setMenu(!nav.classList.contains("sk-open"));
  });

  /* Colour theme. The choice is kept in the browser, if it allows it. */

  function getStored() {
    try {
      return localStorage.getItem("sk-docs-theme");
    } catch (e) {
      return null;
    }
  }

  function setTheme(dark, keep) {
    document.body.setAttribute("data-md-color-scheme", dark ? "slate" : "default");
    if (keep) {
      try {
        localStorage.setItem("sk-docs-theme", dark ? "dark" : "light");
      } catch (e) {
        /* The browser does not keep data for this file. */
      }
    }
  }

  var stored = getStored();
  setTheme(stored ? stored === "dark"
    : window.matchMedia("(prefers-color-scheme: dark)").matches, false);

  document.querySelector(".sk-theme").addEventListener("click", function () {
    var dark = document.body.getAttribute("data-md-color-scheme") === "slate";
    setTheme(!dark, true);
  });

  /* Search */

  function escapeHtml(text) {
    return text.replace(/[&<>"]/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c];
    });
  }

  function termPattern(terms) {
    var parts = terms.map(function (t) {
      return t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    });
    return new RegExp("(" + parts.join("|") + ")", "gi");
  }

  function highlight(text, pattern) {
    return escapeHtml(text).replace(pattern, "<mark>$1</mark>");
  }

  function getTerms(text) {
    return text.toLowerCase().split(/[\s\-]+/).filter(function (t) {
      return t.length > 0;
    });
  }

  function search(terms) {
    var hits = [];
    INDEX.forEach(function (entry) {
      var title = entry[1].toLowerCase();
      var text = entry[3].toLowerCase();
      var score = 0;
      for (var i = 0; i < terms.length; i++) {
        var inTitle = title.indexOf(terms[i]) >= 0;
        if (!inTitle && text.indexOf(terms[i]) < 0) {
          return;
        }
        score += inTitle ? 10 : 1;
      }
      if (title === terms.join(" ")) {
        score += 20;
      }
      hits.push({ entry: entry, score: score });
    });
    hits.sort(function (a, b) {
      return b.score - a.score;
    });
    return hits.slice(0, MAX_RESULTS);
  }

  function snippet(text, terms) {
    var lower = text.toLowerCase();
    var at = -1;
    terms.forEach(function (t) {
      var i = lower.indexOf(t);
      if (i >= 0 && (at < 0 || i < at)) {
        at = i;
      }
    });
    var start = Math.max(0, at - 60);
    var end = Math.min(text.length, start + 200);
    return (start > 0 ? "…" : "") + text.slice(start, end)
      + (end < text.length ? "…" : "");
  }

  function render() {
    var terms = getTerms(query.value);
    if (!terms.length) {
      results.hidden = true;
      results.innerHTML = "";
      return;
    }
    var hits = search(terms);
    var pattern = termPattern(terms);
    if (!hits.length) {
      results.innerHTML = "<p>No results.</p>";
    } else {
      results.innerHTML = hits.map(function (hit, n) {
        var e = hit.entry;
        var page = e[2] && e[2] !== e[1]
          ? '<span class="sk-hit-page">' + escapeHtml(e[2]) + "</span>" : "";
        return '<a href="#' + escapeHtml(e[0]) + '"'
          + (n === 0 ? ' class="sk-selected"' : "") + ">" + page
          + '<span class="sk-hit-title">' + highlight(e[1], pattern) + "</span>"
          + '<span class="sk-hit-text">'
          + highlight(snippet(e[3], terms), pattern) + "</span></a>";
      }).join("");
    }
    results.hidden = false;
  }

  function moveSelection(step) {
    var links = Array.prototype.slice.call(results.querySelectorAll("a"));
    if (!links.length) {
      return;
    }
    var at = links.indexOf(results.querySelector("a.sk-selected"));
    var next = Math.max(0, Math.min(links.length - 1, at + step));
    if (at >= 0) {
      links[at].classList.remove("sk-selected");
    }
    links[next].classList.add("sk-selected");
    links[next].scrollIntoView({ block: "nearest" });
  }

  function open(link) {
    foundTerms = getTerms(query.value);
    results.hidden = true;
    query.blur();
    var hash = link.getAttribute("href");
    if (location.hash === hash) {
      show(hash);
    } else {
      location.hash = hash;
    }
  }

  query.addEventListener("input", render);
  query.addEventListener("focus", function () {
    if (query.value) {
      render();
    }
  });

  query.addEventListener("keydown", function (event) {
    if (event.key === "ArrowDown" || event.key === "ArrowUp") {
      event.preventDefault();
      moveSelection(event.key === "ArrowDown" ? 1 : -1);
    } else if (event.key === "Enter") {
      var link = results.querySelector("a.sk-selected");
      if (link) {
        event.preventDefault();
        open(link);
      }
    } else if (event.key === "Escape") {
      results.hidden = true;
      query.blur();
    }
  });

  results.addEventListener("click", function (event) {
    var link = event.target.closest("a");
    if (link) {
      event.preventDefault();
      open(link);
    }
  });

  document.addEventListener("click", function (event) {
    if (!event.target.closest(".sk-search")) {
      results.hidden = true;
    }
  });

  /* Press "/" or "s" to search. */
  document.addEventListener("keydown", function (event) {
    var tag = document.activeElement ? document.activeElement.tagName : "";
    if ((event.key === "/" || event.key === "s") && tag !== "INPUT"
        && tag !== "TEXTAREA" && !event.ctrlKey && !event.metaKey
        && !event.altKey) {
      event.preventDefault();
      query.focus();
      query.select();
    }
  });

  /* Mark the search terms in the page that a result opens. */

  function mark(page, terms) {
    var pattern = termPattern(terms);
    var walker = document.createTreeWalker(page, NodeFilter.SHOW_TEXT);
    var nodes = [];
    while (walker.nextNode()) {
      pattern.lastIndex = 0;
      if (pattern.test(walker.currentNode.nodeValue)) {
        nodes.push(walker.currentNode);
      }
    }
    nodes.forEach(function (node) {
      var parts = node.nodeValue.split(pattern);
      var fragment = document.createDocumentFragment();
      parts.forEach(function (part, i) {
        if (i % 2) {
          var m = document.createElement("mark");
          m.className = "sk-found";
          m.textContent = part;
          fragment.appendChild(m);
        } else if (part) {
          fragment.appendChild(document.createTextNode(part));
        }
      });
      node.parentNode.replaceChild(fragment, node);
    });
  }

  function unmark() {
    document.querySelectorAll("mark.sk-found").forEach(function (m) {
      var parent = m.parentNode;
      parent.replaceChild(document.createTextNode(m.textContent), m);
      parent.normalize();
    });
  }

  show(location.hash);
})();
