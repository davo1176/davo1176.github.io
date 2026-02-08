// Scroll-triggered fade-in animations
document.addEventListener('DOMContentLoaded', function () {
  // IntersectionObserver for fade-in elements
  const fadeElements = document.querySelectorAll('.fade-in');
  if (fadeElements.length > 0 && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('visible');
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.1 });

    fadeElements.forEach(function (el) {
      observer.observe(el);
    });
  } else {
    // Fallback: make everything visible
    fadeElements.forEach(function (el) {
      el.classList.add('visible');
    });
  }

  // Navbar background on scroll (only for fixed navbars)
  var navbar = document.querySelector('.navbar:not(.navbar--interior)');
  if (navbar) {
    window.addEventListener('scroll', function () {
      if (window.scrollY > 80) {
        navbar.classList.add('navbar--scrolled');
      } else {
        navbar.classList.remove('navbar--scrolled');
      }
    });
  }

  // Hamburger menu toggle
  var hamburger = document.querySelector('.hamburger');
  var navLinks = document.querySelector('.navbar__links');
  if (hamburger && navLinks) {
    hamburger.addEventListener('click', function () {
      hamburger.classList.toggle('active');
      navLinks.classList.toggle('active');
    });

    // Close menu when a link is clicked
    navLinks.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        hamburger.classList.remove('active');
        navLinks.classList.remove('active');
      });
    });
  }
});
