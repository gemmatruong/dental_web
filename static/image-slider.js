document.addEventListener('DOMContentLoaded', () => {
    const slider = document.querySelector('.facility');
    if (!slider) return;

    const images = slider.querySelectorAll('img');
    let currentIndex = 0;

    function slideTo(index) {
        const slideWidth = slider.clientWidth;
        slider.scrollTo({
            left: index * slideWidth,
            behavior: 'smooth'
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;

        e.preventDefault();

        if (e.key === 'ArrowRight') {
            currentIndex = Math.min(currentIndex + 1, images.length - 1);
        }

        if (e.key === 'ArrowLeft') {
            currentIndex = Math.max(currentIndex - 1, 0);
        }

        slideTo(currentIndex);
    });
});
