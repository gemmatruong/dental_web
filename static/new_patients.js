document.addEventListener("DOMContentLoaded", function () {

  function setRequired(container, on) {
    container.querySelectorAll("input, select, textarea").forEach(el => {
      if (el.dataset.req === "1") el.required = on;
    });
  }

  function markRequired(el) {
    if (el.required) el.dataset.req = "1";
  }

  // Mark required inputs inside PI block
  document
    .querySelectorAll("#pi_block input[required], #pi_block select[required], #pi_block textarea[required]")
    .forEach(markRequired);

  const piHas = document.querySelectorAll('input[name="pi_has"]');
  const piIsSub = document.querySelectorAll('input[name="pi_is_subscriber"]');

  const piBlock = document.getElementById("pi_block");
  const piSubBlock = document.getElementById("pi_subscriber_block");

  // Patient fields
  const pFirst = document.querySelector('input[name="p_first"]');
  const pLast  = document.querySelector('input[name="p_last"]');
  const pDob   = document.querySelector('input[name="p_dob"]');

  // Subscriber fields
  const piSubscriber = document.querySelector('input[name="pi_subscriber"]');
  const piDob = document.querySelector('input[name="pi_dob"]');

  function fullName() {
    return [pFirst?.value?.trim(), pLast?.value?.trim()]
      .filter(Boolean)
      .join(" ");
  }

  function updatePI() {
    if (!piBlock || !piSubBlock) return;

    const has = document.querySelector('input[name="pi_has"]:checked')?.value;
    piBlock.style.display = (has === "Yes") ? "" : "none";

    if (has !== "Yes") {
      piSubBlock.style.display = "none";
      return;
    }

    const isSub = document.querySelector('input[name="pi_is_subscriber"]:checked')?.value;

    if (isSub === "Yes") {
      // Auto-fill subscriber info from patient
      if (piSubscriber) piSubscriber.value = fullName();
      if (piDob && pDob) piDob.value = pDob.value;

      piSubBlock.style.display = "none";
    } 
    else if (isSub === "No") {
      piSubBlock.style.display = "";
    } 
    else {
      piSubBlock.style.display = "none";
    }
  }

  piHas.forEach(r => r.addEventListener("change", updatePI));
  piIsSub.forEach(r => r.addEventListener("change", updatePI));

  [pFirst, pLast, pDob].forEach(el => {
    if (el) el.addEventListener("input", updatePI);
  });

  // Initial run
  updatePI();
});
