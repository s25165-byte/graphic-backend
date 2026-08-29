/* ============================================================
   CHROME BICYCLE — interactions
   ============================================================ */
(function () {
    "use strict";

    /* ---------- Header visibility ---------- */
    var siteHeader = document.getElementById("siteHeader");

    function updateHeaderVisibility() {
        if (!siteHeader) return;
        siteHeader.classList.toggle("is-at-top", window.scrollY <= 40);
    }

    window.addEventListener("scroll", updateHeaderVisibility, { passive: true });
    updateHeaderVisibility();

    /* ---------- Mobile menu ---------- */
    var menuToggle = document.getElementById("menuToggle");
    var mobileMenu = document.getElementById("mobileMenu");

    if (menuToggle && mobileMenu) {
        menuToggle.addEventListener("click", function () {
            var open = mobileMenu.classList.toggle("is-open");
            menuToggle.classList.toggle("is-open", open);
            menuToggle.setAttribute("aria-expanded", String(open));
            document.body.style.overflow = open ? "hidden" : "";
        });

        mobileMenu.querySelectorAll("a").forEach(function (link) {
            link.addEventListener("click", function () {
                mobileMenu.classList.remove("is-open");
                menuToggle.classList.remove("is-open");
                menuToggle.setAttribute("aria-expanded", "false");
                document.body.style.overflow = "";
            });
        });
    }

    /* ---------- Frames carousel ---------- */
    var framesTrack = document.getElementById("framesTrack");
    var framesPrev = document.getElementById("framesPrev");
    var framesNext = document.getElementById("framesNext");

    if (framesTrack && framesPrev && framesNext) {
        var framesIndex = 0;
        var framesCards = Array.prototype.slice.call(framesTrack.querySelectorAll(".frame-card"));
        var framesCount = framesCards.length;
        var framesGap = 16;
        var framesBusy = false;

        var firstClone = framesCards[framesCount - 1].cloneNode(true);
        firstClone.setAttribute("aria-hidden", "true");
        framesTrack.insertBefore(firstClone, framesTrack.firstChild);
        framesCards.unshift(firstClone);

        framesCards.slice(0, 2).forEach(function (card) {
            var clone = card.cloneNode(true);
            clone.setAttribute("aria-hidden", "true");
            framesTrack.appendChild(clone);
            framesCards.push(clone);
        });

        framesIndex = 1;

        function framesUpdate() {
            var card = framesCards[0];
            var step = card ? card.getBoundingClientRect().width + framesGap : 0;
            framesTrack.style.transform = "translateX(" + (-framesIndex * step) + "px)";
        }

        function framesMove(nextIndex) {
            if (framesBusy) return;
            framesBusy = true;
            framesIndex = nextIndex;
            framesUpdate();
        }

        framesTrack.addEventListener("transitionend", function (event) {
            if (event.propertyName !== "transform") return;
            if (framesIndex > framesCount) {
                framesTrack.style.transition = "none";
                framesIndex = 1;
                framesUpdate();
                void framesTrack.offsetHeight;
                framesTrack.style.transition = "";
                framesBusy = false;
                return;
            }
            if (framesIndex > 0) return;
            framesTrack.style.transition = "none";
            framesIndex = framesCount;
            framesUpdate();
            void framesTrack.offsetHeight;
            framesTrack.style.transition = "";
            framesBusy = false;
        });

        framesTrack.addEventListener("transitionend", function (event) {
            if (event.propertyName === "transform" && framesIndex > 0 && framesIndex <= framesCount) {
                framesBusy = false;
            }
        });

        framesPrev.addEventListener("click", function () {
            framesMove(framesIndex - 1);
        });

        framesNext.addEventListener("click", function () {
            framesMove(framesIndex + 1);
        });

        setInterval(function () {
            framesMove(framesIndex + 1);
        }, 2000);

        var framesResize;
        window.addEventListener("resize", function () {
            clearTimeout(framesResize);
            framesResize = setTimeout(framesUpdate, 150);
        });

        framesUpdate();
    }

    /* ---------- Newsletter image paths ---------- */
    var newsletterSection = document.querySelector(".section-newsletter");

    if (newsletterSection && "IntersectionObserver" in window) {
        var newsletterObserver = new IntersectionObserver(function (entries) {
            entries.forEach(function (entry) {
                newsletterSection.classList.toggle("is-in-view", entry.isIntersecting);
            });
        }, { threshold: 0.2 });

        newsletterObserver.observe(newsletterSection);
    }

    /* ---------- Testimonials ---------- */
    var tTrack = document.getElementById("testimonialsTrack");
    var tDots = document.getElementById("testimonialsDots");

    if (tTrack && tDots) {
        var tSlides = tTrack.querySelectorAll(".testimonial");
        var tIndex = 0;
        var tGap = 64;
        var tTotal = tSlides.length;

        function tUpdate(animate) {
            var slide = tSlides[0];
            var step = slide ? slide.getBoundingClientRect().width + tGap : 0;
            if (!animate) {
                tTrack.style.transition = "none";
            }
            tTrack.style.transform = "translateX(" + (-tIndex * step) + "px)";
            if (!animate) {
                void tTrack.offsetHeight;
                tTrack.style.transition = "";
            }
            tDots.querySelectorAll(".dot").forEach(function (d, i) {
                d.classList.toggle("is-active", i === tIndex);
            });
        }

        tDots.querySelectorAll(".dot").forEach(function (dot, i) {
            dot.addEventListener("click", function () {
                if (i !== tIndex) {
                    tIndex = i;
                    tUpdate(true);
                }
            });
        });

        var tResize;
        window.addEventListener("resize", function () {
            clearTimeout(tResize);
            tResize = setTimeout(function () { tUpdate(false); }, 150);
        });

        tUpdate(false);
    }

    /* ---------- Newsletter form ---------- */
    var newsletterForm = document.getElementById("newsletterForm");
    var formMessage = document.getElementById("formMessage");

    if (newsletterForm) {
        newsletterForm.addEventListener("submit", function (e) {
            e.preventDefault();
            var email = document.getElementById("newsletterEmail");
            var value = email ? email.value.trim() : "";
            var valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

            if (!formMessage) return;

            if (!valid) {
                formMessage.textContent = "Please enter a valid email address.";
                formMessage.className = "form-message is-error";
            } else {
                var subscribeUrl = window.location.protocol === "file:"
                    ? "http://127.0.0.1:8000/subscribe"
                    : "/subscribe";

                fetch(subscribeUrl, {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: new URLSearchParams({ email: value }).toString()
                })
                    .then(function (response) {
                        return response.json().then(function (data) {
                            if (!response.ok) throw new Error(data.error || "Subscription failed.");
                            return data;
                        });
                    })
                    .then(function (data) {
                        formMessage.textContent = data.message || "You're on the list. Welcome to Chrome.";
                        formMessage.className = "form-message is-success";
                        if (email) email.value = "";
                    })
                    .catch(function (error) {
                        formMessage.textContent = error.message || "Could not save your subscription.";
                        formMessage.className = "form-message is-error";
                    });
            }
        });
    }
})();