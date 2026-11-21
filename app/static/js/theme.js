/* Theme switching for Bookshelf.
 *
 * The initial theme is applied by an inline script in <head> to avoid a flash.
 * This file keeps the toggle button, the browser theme colour and the saved
 * preference in sync.
 */

(function () {
  "use strict";

  var STORAGE_KEY = "bookshelf-theme";
  var LIGHT_THEME_COLOR = "#78917B";
  var DARK_THEME_COLOR = "#171A1E";

  var root = document.documentElement;
  var buttons = document.querySelectorAll("[data-theme-toggle]");
  var themeColor = document.querySelector('meta[name="theme-color"]');

  function storedTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY);
    } catch (error) {
      return null;
    }
  }

  function activeTheme() {
    return root.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function apply(theme, save) {
    var isDark = theme === "dark";
    root.setAttribute("data-theme", theme);

    if (themeColor) {
      themeColor.setAttribute("content", isDark ? DARK_THEME_COLOR : LIGHT_THEME_COLOR);
    }

    buttons.forEach(function (button) {
      var label = isDark ? "Switch to light mode" : "Switch to dark mode";
      button.setAttribute("aria-pressed", isDark ? "true" : "false");
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
    });

    if (save) {
      try {
        localStorage.setItem(STORAGE_KEY, theme);
      } catch (error) {
        /* Storage can be unavailable in private modes; the theme still works. */
      }
    }
  }

  buttons.forEach(function (button) {
    button.addEventListener("click", function () {
      apply(activeTheme() === "dark" ? "light" : "dark", true);
    });
  });

  apply(activeTheme(), false);

  // Follow the OS only while the user has not chosen a theme explicitly.
  var media = window.matchMedia("(prefers-color-scheme: dark)");
  function onSystemChange(event) {
    if (!storedTheme()) {
      apply(event.matches ? "dark" : "light", false);
    }
  }
  if (media.addEventListener) {
    media.addEventListener("change", onSystemChange);
  } else if (media.addListener) {
    media.addListener(onSystemChange);
  }
})();
