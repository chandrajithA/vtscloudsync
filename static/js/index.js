const track = document.querySelector(".carousel-track");
const nextBtn = document.querySelector(".next");
const prevBtn = document.querySelector(".prev");

let index = 0;
const cardWidth = 390;
const AUTO_SLIDE_DELAY = 4000; // 4 seconds
let autoSlideInterval;

/* Update slide position */
function updateCarousel() {
    track.style.transform = `translateX(-${index * cardWidth}px)`;
}

/* Go to next slide */
function nextSlide() {
    index = (index + 1) % track.children.length;
    updateCarousel();
    resetAutoSlide();
}

/* Go to previous slide */
function prevSlide() {
    index = (index - 1 + track.children.length) % track.children.length;
    updateCarousel();
    resetAutoSlide();
}

/* Start auto sliding */
function startAutoSlide() {
    autoSlideInterval = setInterval(() => {
        index = (index + 1) % track.children.length;
        updateCarousel();
    }, AUTO_SLIDE_DELAY);
}

/* Reset auto sliding timer */
function resetAutoSlide() {
    clearInterval(autoSlideInterval);
    startAutoSlide();
}

/* Button events */
nextBtn.addEventListener("click", nextSlide);
prevBtn.addEventListener("click", prevSlide);

/* Init */
startAutoSlide();