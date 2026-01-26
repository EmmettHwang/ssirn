// Language Toggle System
class LanguageToggle {
    constructor() {
        this.currentLang = localStorage.getItem('language') || 'ko';
        this.init();
    }

    init() {
        this.applyLanguage(this.currentLang);
        this.setupEventListeners();
    }

    setupEventListeners() {
        const toggleBtn = document.getElementById('lang-toggle');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => this.toggleLanguage());
        }
    }

    toggleLanguage() {
        this.currentLang = this.currentLang === 'ko' ? 'en' : 'ko';
        localStorage.setItem('language', this.currentLang);
        this.applyLanguage(this.currentLang);
    }

    applyLanguage(lang) {
        const elements = document.querySelectorAll('[data-kr][data-en]');
        elements.forEach(element => {
            const text = lang === 'ko' ? element.getAttribute('data-kr') : element.getAttribute('data-en');
            if (text) {
                element.textContent = text;
            }
        });

        // Update toggle button text
        const toggleBtn = document.getElementById('lang-toggle');
        if (toggleBtn) {
            const langText = toggleBtn.querySelector('.nav__lang-text');
            if (langText) {
                langText.textContent = lang === 'ko' ? 'EN' : 'KR';
            }
        }

        // Update page title
        const title = document.querySelector('title[data-kr][data-en]');
        if (title) {
            const titleText = lang === 'ko' ? title.getAttribute('data-kr') : title.getAttribute('data-en');
            if (titleText) {
                title.textContent = titleText;
            }
        }

        // Update HTML lang attribute
        document.documentElement.lang = lang;
    }
}

// Navigation
class Navigation {
    constructor() {
        this.nav = document.getElementById('nav');
        this.navToggle = document.getElementById('nav-toggle');
        this.navMenu = document.getElementById('nav-menu');
        this.init();
    }

    init() {
        this.setupScrollEffect();
        this.setupMobileMenu();
        this.highlightActiveLink();
    }

    setupScrollEffect() {
        let lastScroll = 0;
        window.addEventListener('scroll', () => {
            const currentScroll = window.pageYOffset;

            if (currentScroll > 100) {
                this.nav.classList.add('nav--scrolled');
            } else {
                this.nav.classList.remove('nav--scrolled');
            }

            lastScroll = currentScroll;
        });
    }

    setupMobileMenu() {
        if (this.navToggle && this.navMenu) {
            this.navToggle.addEventListener('click', () => {
                this.navMenu.classList.toggle('active');
                const icon = this.navToggle.querySelector('i');
                if (icon) {
                    icon.classList.toggle('fa-bars');
                    icon.classList.toggle('fa-times');
                }
            });

            // Close menu when clicking on a link
            const navLinks = this.navMenu.querySelectorAll('.nav__link');
            navLinks.forEach(link => {
                link.addEventListener('click', () => {
                    this.navMenu.classList.remove('active');
                    const icon = this.navToggle.querySelector('i');
                    if (icon) {
                        icon.classList.add('fa-bars');
                        icon.classList.remove('fa-times');
                    }
                });
            });

            // Close menu when clicking outside
            document.addEventListener('click', (e) => {
                if (!this.navMenu.contains(e.target) && !this.navToggle.contains(e.target)) {
                    this.navMenu.classList.remove('active');
                    const icon = this.navToggle.querySelector('i');
                    if (icon) {
                        icon.classList.add('fa-bars');
                        icon.classList.remove('fa-times');
                    }
                }
            });
        }
    }

    highlightActiveLink() {
        const currentPage = window.location.pathname.split('/').pop() || 'index.html';
        const navLinks = document.querySelectorAll('.nav__link');
        
        navLinks.forEach(link => {
            const linkPage = link.getAttribute('href');
            if (linkPage === currentPage || (currentPage === '' && linkPage === 'index.html')) {
                link.classList.add('nav__link--active');
            } else {
                link.classList.remove('nav__link--active');
            }
        });
    }
}

// Back to Top Button
class BackToTop {
    constructor() {
        this.button = document.getElementById('back-to-top');
        this.init();
    }

    init() {
        if (!this.button) return;

        window.addEventListener('scroll', () => {
            if (window.pageYOffset > 300) {
                this.button.classList.add('visible');
            } else {
                this.button.classList.remove('visible');
            }
        });

        this.button.addEventListener('click', () => {
            window.scrollTo({
                top: 0,
                behavior: 'smooth'
            });
        });
    }
}

// Scroll Animations
class ScrollAnimations {
    constructor() {
        this.init();
    }

    init() {
        const observer = new IntersectionObserver(
            (entries) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        entry.target.classList.add('animate-in');
                    }
                });
            },
            {
                threshold: 0.1,
                rootMargin: '0px 0px -50px 0px'
            }
        );

        const animatedElements = document.querySelectorAll(
            '.card, .tech-card, .ssirn-card, .timeline__item, .market-card'
        );

        animatedElements.forEach(el => {
            el.style.opacity = '0';
            el.style.transform = 'translateY(30px)';
            el.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
            observer.observe(el);
        });

        // Add animation styles
        const style = document.createElement('style');
        style.textContent = `
            .animate-in {
                opacity: 1 !important;
                transform: translateY(0) !important;
            }
        `;
        document.head.appendChild(style);
    }
}

// Form Validation
class FormValidation {
    constructor() {
        this.forms = document.querySelectorAll('form');
        this.init();
    }

    init() {
        this.forms.forEach(form => {
            form.addEventListener('submit', (e) => {
                if (!this.validateForm(form)) {
                    e.preventDefault();
                }
            });
        });
    }

    validateForm(form) {
        let isValid = true;
        const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');

        inputs.forEach(input => {
            if (!input.value.trim()) {
                this.showError(input, 'This field is required');
                isValid = false;
            } else {
                this.clearError(input);
            }

            // Email validation
            if (input.type === 'email' && input.value.trim()) {
                const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
                if (!emailPattern.test(input.value.trim())) {
                    this.showError(input, 'Please enter a valid email address');
                    isValid = false;
                }
            }

            // Phone validation
            if (input.type === 'tel' && input.value.trim()) {
                const phonePattern = /^[0-9-+().\s]+$/;
                if (!phonePattern.test(input.value.trim())) {
                    this.showError(input, 'Please enter a valid phone number');
                    isValid = false;
                }
            }
        });

        return isValid;
    }

    showError(input, message) {
        input.classList.add('input-error');
        
        let errorElement = input.nextElementSibling;
        if (!errorElement || !errorElement.classList.contains('error-message')) {
            errorElement = document.createElement('span');
            errorElement.classList.add('error-message');
            input.parentNode.insertBefore(errorElement, input.nextSibling);
        }
        
        errorElement.textContent = message;
    }

    clearError(input) {
        input.classList.remove('input-error');
        const errorElement = input.nextElementSibling;
        if (errorElement && errorElement.classList.contains('error-message')) {
            errorElement.remove();
        }
    }
}

// Lazy Loading Images
class LazyLoadImages {
    constructor() {
        this.images = document.querySelectorAll('img[loading="lazy"]');
        this.init();
    }

    init() {
        if ('IntersectionObserver' in window) {
            const imageObserver = new IntersectionObserver((entries, observer) => {
                entries.forEach(entry => {
                    if (entry.isIntersecting) {
                        const img = entry.target;
                        img.src = img.dataset.src || img.src;
                        img.classList.add('loaded');
                        observer.unobserve(img);
                    }
                });
            });

            this.images.forEach(img => imageObserver.observe(img));
        } else {
            // Fallback for browsers that don't support IntersectionObserver
            this.images.forEach(img => {
                img.src = img.dataset.src || img.src;
                img.classList.add('loaded');
            });
        }
    }
}

// Video Player Enhancement
class VideoPlayer {
    constructor() {
        this.videos = document.querySelectorAll('video');
        this.init();
    }

    init() {
        this.videos.forEach(video => {
            // Pause other videos when one starts playing
            video.addEventListener('play', () => {
                this.videos.forEach(v => {
                    if (v !== video) {
                        v.pause();
                    }
                });
            });

            // Add loading indicator
            video.addEventListener('waiting', () => {
                video.classList.add('loading');
            });

            video.addEventListener('canplay', () => {
                video.classList.remove('loading');
            });
        });
    }
}

// Initialize all modules when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    new LanguageToggle();
    new Navigation();
    new BackToTop();
    new ScrollAnimations();
    new FormValidation();
    new LazyLoadImages();
    new VideoPlayer();
});

// Handle page visibility for videos
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        document.querySelectorAll('video').forEach(video => {
            if (!video.paused) {
                video.dataset.wasPlaying = 'true';
                video.pause();
            }
        });
    } else {
        document.querySelectorAll('video').forEach(video => {
            if (video.dataset.wasPlaying === 'true') {
                video.play();
                delete video.dataset.wasPlaying;
            }
        });
    }
});
