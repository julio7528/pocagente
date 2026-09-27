(() => {
  const carousel = document.querySelector("[data-home-carousel]");
  if (!carousel) return;

  const track = carousel.querySelector("[data-carousel-track]");
  const slides = Array.from(carousel.querySelectorAll("[data-carousel-slide]"));
  const previousButton = carousel.querySelector("[data-carousel-previous]");
  const nextButton = carousel.querySelector("[data-carousel-next]");
  const toggleButton = carousel.querySelector("[data-carousel-toggle]");
  const pauseIcon = carousel.querySelector("[data-carousel-pause-icon]");
  const playIcon = carousel.querySelector("[data-carousel-play-icon]");

  if (!track || slides.length < 2 || !previousButton || !nextButton || !toggleButton) return;

  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
  let currentIndex = 0;
  let isPaused = reducedMotion.matches;
  let autoplayTimer = null;

  function stopAutoplay() {
    if (autoplayTimer !== null) {
      window.clearInterval(autoplayTimer);
      autoplayTimer = null;
    }
  }

  function startAutoplay() {
    stopAutoplay();
    if (!isPaused && !document.hidden) {
      autoplayTimer = window.setInterval(() => showSlide(currentIndex + 1), 5000);
    }
  }

  function updatePauseControl() {
    const action = isPaused ? "Reproduzir" : "Pausar";
    toggleButton.setAttribute("aria-label", `${action} carrossel`);
    toggleButton.title = `${action} carrossel`;
    if (pauseIcon) pauseIcon.hidden = isPaused;
    if (playIcon) playIcon.hidden = !isPaused;
  }

  function showSlide(index) {
    currentIndex = (index + slides.length) % slides.length;
    track.style.transform = `translate3d(-${currentIndex * (100 / slides.length)}%, 0, 0)`;
    slides.forEach((slide, slideIndex) => {
      slide.setAttribute("aria-hidden", String(slideIndex !== currentIndex));
    });
    startAutoplay();
  }

  previousButton.addEventListener("click", () => showSlide(currentIndex - 1));
  nextButton.addEventListener("click", () => showSlide(currentIndex + 1));
  toggleButton.addEventListener("click", () => {
    isPaused = !isPaused;
    updatePauseControl();
    startAutoplay();
  });

  document.addEventListener("visibilitychange", startAutoplay);
  reducedMotion.addEventListener?.("change", (event) => {
    if (event.matches) {
      isPaused = true;
      updatePauseControl();
      startAutoplay();
    }
  });

  updatePauseControl();
  showSlide(currentIndex);
})();
