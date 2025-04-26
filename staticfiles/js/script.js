// Hamburger menu logic for mobile navigation

document.addEventListener("DOMContentLoaded", function () {
  const menuIcon = document.getElementById("menu-icon");
  const navLinks = document.getElementById("nav-links");
  if (!menuIcon || !navLinks) return;

  function isMobile() {
    return window.innerWidth <= 700;
  }

  function showMenuIcon() {
    menuIcon.style.display = "block";
  }
  function hideMenuIcon() {
    menuIcon.style.display = "none";
    navLinks.classList.remove("show");
    menuIcon.setAttribute('aria-expanded', false);
  }

  // Hamburger click toggles menu
  menuIcon.addEventListener("click", function (e) {
    if (isMobile()) {
      e.stopPropagation();
      navLinks.classList.toggle("show");
      menuIcon.setAttribute('aria-expanded', navLinks.classList.contains("show"));
    }
  });

  // Clicking outside closes menu
  document.addEventListener("click", function (e) {
    if (
      isMobile() &&
      navLinks.classList.contains("show") &&
      !navLinks.contains(e.target) &&
      e.target !== menuIcon &&
      !menuIcon.contains(e.target)
    ) {
      navLinks.classList.remove("show");
      menuIcon.setAttribute('aria-expanded', false);
    }
  });
  // Clicking a link closes menu
  navLinks.querySelectorAll("a").forEach(link => {
    link.addEventListener("click", function () {
      if (isMobile()) {
        navLinks.classList.remove("show");
        menuIcon.setAttribute('aria-expanded', false);
      }
    });
  });

  // Responsive: show/hide hamburger and menu on resize
  function handleResize() {
    if (isMobile()) {
      showMenuIcon();
      navLinks.classList.remove("show");
      menuIcon.setAttribute('aria-expanded', false);
    } else {
      hideMenuIcon();
      navLinks.style.display = ""; // Let CSS control
    }
  }
  window.addEventListener("resize", handleResize);
  handleResize();
});
