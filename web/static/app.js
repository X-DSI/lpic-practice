// Countdown and keyboard shortcuts for the mock exam. The server enforces the deadline itself;
// this only draws the clock and submits when it reaches zero.
(function () {
  "use strict";
  const clock = document.getElementById("countdown");
  if (clock) {
    const end = Date.now() + Number(clock.dataset.remaining) * 1000;
    const tick = () => {
      const left = Math.max(0, Math.round((end - Date.now()) / 1000));
      clock.textContent = Math.floor(left / 60) + ":" + String(left % 60).padStart(2, "0");
      clock.classList.toggle("low", left <= 300);
      if (left === 0) {
        document.getElementById("expire-form").submit();
      } else {
        setTimeout(tick, 1000);
      }
    };
    tick();
  }

  // a–h choose an option, m marks, n / p move. Ignored while typing in a text field.
  document.addEventListener("keydown", (event) => {
    const target = event.target;
    if (event.ctrlKey || event.metaKey || event.altKey) return;
    if (target instanceof HTMLInputElement && target.type === "text") return;
    if (target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement) return;
    const control = document.querySelector('#question-form [data-key="' + event.key.toLowerCase() + '"]');
    if (!control || control.disabled) return;
    event.preventDefault();
    control.click();
  });
})();
