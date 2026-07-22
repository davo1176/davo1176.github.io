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

  // Live hero readout — assembled from the same data files that power the
  // dashboards. Runs only on the homepage (where #hero-readout exists).
  var readout = document.getElementById('hero-readout');
  if (readout) {
    populateHeroReadout();
  }
});

function populateHeroReadout() {
  function fmt(n) {
    return Math.round(n).toLocaleString('en-US');
  }
  function setStat(id, value) {
    var el = document.getElementById(id);
    if (el && value != null && !isNaN(value)) {
      el.textContent = fmt(value);
    }
  }
  function loadJSON(path) {
    return fetch(path).then(function (r) {
      if (!r.ok) throw new Error(path);
      return r.json();
    }).catch(function () { return null; });
  }

  Promise.all([
    loadJSON('data/coros_data.json'),
    loadJSON('data/hevy_data.json'),
    loadJSON('data/ski_day_data.json')
  ]).then(function (results) {
    var coros = results[0];
    var hevy = results[1];
    var ski = results[2];

    if (coros && coros.athlete_stats) {
      setStat('stat-miles', coros.athlete_stats.total_distance_miles);
      setStat('stat-runs', coros.athlete_stats.total_activities);
    }
    if (hevy && hevy.athlete_stats) {
      setStat('stat-lifts', hevy.athlete_stats.total_workouts);
      setStat('stat-prs', hevy.athlete_stats.total_prs);
    }
    if (Array.isArray(ski)) {
      setStat('stat-ski', ski.length);
    }

    // Freshest sync timestamp across the live sources.
    var stamps = [];
    if (coros && coros.last_updated) stamps.push(coros.last_updated);
    if (hevy && hevy.last_updated) stamps.push(hevy.last_updated);
    stamps.sort();
    var latest = stamps[stamps.length - 1];
    var meta = document.getElementById('hero-sync');
    if (meta && latest) {
      var d = new Date(latest);
      if (!isNaN(d)) {
        var date = d.toISOString().slice(0, 10);
        meta.innerHTML = '<span class="dot"></span>Live from my own data pipelines &middot; last sync ' + date;
      }
    }
  });
}
