document.addEventListener("input", function (event) {
  var input = event.target.closest("[data-confirm-source]");
  if (!input) {
    return;
  }

  var form = input.closest("form");
  if (!form) {
    return;
  }

  var button = form.querySelector("[data-confirm-button]");
  if (!button) {
    return;
  }

  button.disabled = input.value.trim().toUpperCase() !== input.dataset.confirmTicker;
});
