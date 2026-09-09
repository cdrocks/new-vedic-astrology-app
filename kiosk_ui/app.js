/* ===================================================
   VEDIC ASTROLOGY READER - SCRIPT LOGIC
   3D Cinematic Planets (Saturn & Mars) + Deep Starfield
   =================================================== */

// --- 1. THREE.JS CINEMATIC PLANETS (SATURN & MARS) ---
let scene, camera, renderer;
let saturnGroup, marsMesh, starPoints;
let targetCameraX = 0, targetCameraY = 4;

// Procedural Saturn Atmospheric Banding
function createSaturnTexture() {
  const c = document.createElement("canvas");
  c.width = 512;
  c.height = 256;
  const ctx = c.getContext("2d");
  const grad = ctx.createLinearGradient(0, 0, 0, 256);
  grad.addColorStop(0.00, "#a68852");
  grad.addColorStop(0.15, "#dfc691");
  grad.addColorStop(0.30, "#bfa065");
  grad.addColorStop(0.48, "#eed9ab");
  grad.addColorStop(0.62, "#c4a368");
  grad.addColorStop(0.78, "#dfc691");
  grad.addColorStop(0.92, "#b39154");
  grad.addColorStop(1.00, "#8a6d38");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 512, 256);
  return new THREE.CanvasTexture(c);
}

// Procedural Saturn Ring Texture with Cassini Division
function createSaturnRingTexture() {
  const c = document.createElement("canvas");
  c.width = 512;
  c.height = 1;
  const ctx = c.getContext("2d");
  const grad = ctx.createLinearGradient(0, 0, 512, 0);
  grad.addColorStop(0.00, "rgba(180, 150, 90, 0)");
  grad.addColorStop(0.06, "rgba(215, 185, 125, 0.55)");
  grad.addColorStop(0.35, "rgba(240, 215, 155, 0.85)");
  grad.addColorStop(0.46, "rgba(220, 190, 130, 0.7)");
  grad.addColorStop(0.50, "rgba(10, 6, 20, 0.05)"); // Cassini Division gap
  grad.addColorStop(0.56, "rgba(205, 175, 115, 0.6)");
  grad.addColorStop(0.85, "rgba(175, 145, 90, 0.35)");
  grad.addColorStop(1.00, "rgba(140, 110, 60, 0)");
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 512, 1);
  return new THREE.CanvasTexture(c);
}

// Procedural Mars Rust Red Surface
function createMarsTexture() {
  const c = document.createElement("canvas");
  c.width = 512;
  c.height = 256;
  const ctx = c.getContext("2d");
  // Deep rust red baseline
  ctx.fillStyle = "#b83f14";
  ctx.fillRect(0, 0, 512, 256);
  // Craters & darker iron-oxide formations
  ctx.fillStyle = "#7a2205";
  for (let i = 0; i < 35; i++) {
    const x = Math.random() * 512;
    const y = Math.random() * 256;
    const r = 12 + Math.random() * 30;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.filter = "blur(10px)";
    ctx.fill();
  }
  // Subtle polar ice cap
  ctx.filter = "blur(3px)";
  ctx.fillStyle = "rgba(255, 240, 230, 0.55)";
  ctx.fillRect(0, 0, 512, 16);
  return new THREE.CanvasTexture(c);
}

function initThreeBg() {
  const canvas = document.getElementById("bg-canvas");
  if (!canvas) return;

  try {
    scene = new THREE.Scene();
    camera = new THREE.PerspectiveCamera(50, window.innerWidth / window.innerHeight, 0.1, 1000);
    camera.position.set(0, 4, 48);
    camera.lookAt(0, 0, 0);

    renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: "high-performance" });
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

    // 1. Directional Sun Light & Ambient Fill (Photorealistic day/night shading)
    const sunLight = new THREE.DirectionalLight(0xfff7e8, 1.8);
    sunLight.position.set(40, 25, 35);
    scene.add(sunLight);

    const ambientLight = new THREE.AmbientLight(0x282045, 0.45);
    scene.add(ambientLight);

    // 2. Deep Starfield Background
    const starCount = 1400;
    const starGeo = new THREE.BufferGeometry();
    const starPos = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount * 3; i += 3) {
      starPos[i] = (Math.random() - 0.5) * 180;
      starPos[i + 1] = (Math.random() - 0.5) * 140;
      starPos[i + 2] = -30 + (Math.random() - 0.5) * 120;
    }
    starGeo.setAttribute("position", new THREE.BufferAttribute(starPos, 3));
    const starMat = new THREE.PointsMaterial({
      color: 0xfbf6ea,
      size: 0.8,
      transparent: true,
      opacity: 0.55,
      blending: THREE.AdditiveBlending,
    });
    starPoints = new THREE.Points(starGeo, starMat);
    scene.add(starPoints);

    // 3. SATURN (Shani - The Lord of Karma & Time)
    saturnGroup = new THREE.Group();
    saturnGroup.position.set(22, 10, -14); // Positioned in upper right

    // Saturn Globe
    const saturnGeo = new THREE.SphereGeometry(4.5, 48, 48);
    const saturnMat = new THREE.MeshLambertMaterial({
      map: createSaturnTexture(),
    });
    const saturnGlobe = new THREE.Mesh(saturnGeo, saturnMat);
    saturnGroup.add(saturnGlobe);

    // Saturn Ring with Radial UV Mapping
    const innerR = 5.6;
    const outerR = 10.8;
    const ringGeo = new THREE.RingGeometry(innerR, outerR, 96);
    const pos = ringGeo.attributes.position;
    const uvs = ringGeo.attributes.uv;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const y = pos.getY(i);
      const r = Math.sqrt(x * x + y * y);
      const u = (r - innerR) / (outerR - innerR);
      uvs.setXY(i, u, 0.5);
    }
    uvs.needsUpdate = true;

    const ringMat = new THREE.MeshBasicMaterial({
      map: createSaturnRingTexture(),
      side: THREE.DoubleSide,
      transparent: true,
      opacity: 0.85,
    });
    const saturnRing = new THREE.Mesh(ringGeo, ringMat);
    saturnRing.rotation.x = Math.PI / 2;
    saturnGroup.add(saturnRing);

    // Realistic Saturn Axial Tilt (~27 degrees)
    saturnGroup.rotation.z = Math.PI * 0.15;
    saturnGroup.rotation.x = Math.PI * 0.22;
    scene.add(saturnGroup);

    // 4. MARS (Mangala - The Fiery Red Planet)
    const marsGeo = new THREE.SphereGeometry(2.3, 36, 36);
    const marsMat = new THREE.MeshLambertMaterial({
      map: createMarsTexture(),
    });
    marsMesh = new THREE.Mesh(marsGeo, marsMat);
    marsMesh.position.set(-22, -6, -10); // Positioned in midground left
    scene.add(marsMesh);

    // Micro-parallax on mouse/touch
    window.addEventListener("mousemove", onCosmicMove, { passive: true });
    window.addEventListener("touchmove", onCosmicTouch, { passive: true });
    window.addEventListener("resize", onWindowResize);

    animateThree();
  } catch (err) {
    console.warn("WebGL background initialization fallback:", err);
  }
}

function onCosmicMove(e) {
  const normX = (e.clientX / window.innerWidth) * 2 - 1;
  const normY = -(e.clientY / window.innerHeight) * 2 + 1;
  targetCameraX = normX * 4;
  targetCameraY = 4 + normY * 2.5;
}

function onCosmicTouch(e) {
  if (e.touches && e.touches[0]) {
    const normX = (e.touches[0].clientX / window.innerWidth) * 2 - 1;
    const normY = -(e.touches[0].clientY / window.innerHeight) * 2 + 1;
    targetCameraX = normX * 3;
    targetCameraY = 4 + normY * 2;
  }
}

function onWindowResize() {
  if (!camera || !renderer) return;
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
}

function animateThree() {
  requestAnimationFrame(animateThree);
  try {
    // Glacial rotation of Saturn on its axis
    if (saturnGroup) {
      saturnGroup.rotation.y += 0.0007;
    }

    // Mars rotation and subtle slow orbital drift
    if (marsMesh) {
      marsMesh.rotation.y += 0.001;
      marsMesh.position.y = -6 + Math.sin(Date.now() * 0.0004) * 0.8;
    }

    // Deep starfield rotation
    if (starPoints) {
      starPoints.rotation.y += 0.0001;
    }

    // Smooth camera micro-parallax
    if (camera) {
      camera.position.x += (targetCameraX - camera.position.x) * 0.03;
      camera.position.y += (targetCameraY - camera.position.y) * 0.03;
      camera.lookAt(0, 0, 0);
    }

    if (renderer && scene && camera) {
      renderer.render(scene, camera);
    }
  } catch (e) {
    // Ignore frame hiccups
  }
}


// --- 2. TOPIC SELECTION & UI STATE ---
let selectedTopic = "career";
let selectedPrompt = "Based on my planetary strengths and current Dasha, what leadership qualities and professional milestones are opening up for me?";
let idleTimerInterval = null;
const TOTAL_IDLE_SECONDS = 180; // 3 full minutes of inactivity
let countdownSeconds = TOTAL_IDLE_SECONDS;

function setupTopicCards() {
  const cards = document.querySelectorAll(".topic-card");
  const customBox = document.getElementById("custom-question-container");
  const customInput = document.getElementById("custom-question-input");

  cards.forEach((card) => {
    card.addEventListener("click", () => {
      cards.forEach((c) => c.classList.remove("active"));
      card.classList.add("active");

      selectedTopic = card.dataset.topic;
      selectedPrompt = card.dataset.prompt;

      if (selectedTopic === "custom") {
        customBox.style.display = "block";
        if (window.gsap) {
          gsap.fromTo(customBox, { opacity: 0, y: -10 }, { opacity: 1, y: 0, duration: 0.3 });
        } else {
          customBox.style.opacity = "1";
        }
        customInput.focus();
      } else {
        customBox.style.display = "none";
      }
    });
  });
}


// --- 3. FORM SUBMISSION & READING GENERATION ---
async function handleFormSubmit() {
  const name = document.getElementById("guest-name").value.trim();
  const dob = document.getElementById("guest-dob").value.trim();
  const time = document.getElementById("guest-time").value.trim();
  const city = document.getElementById("guest-city").value.trim();
  const country = document.getElementById("guest-country").value;
  const email = document.getElementById("guest-email").value.trim();
  const errorBanner = document.getElementById("error-banner");

  errorBanner.style.display = "none";

  let finalQuestion = selectedPrompt;
  if (selectedTopic === "custom") {
    const customText = document.getElementById("custom-question-input").value.trim();
    if (!customText) {
      showError("Please enter your custom question in the box.");
      return;
    }
    finalQuestion = customText;
  }

  if (!name || !dob || !time || !city) {
    showError("Please fill in all required birth details.");
    return;
  }

  // Switch to Screen 2 & Show Loader
  showScreen("screen-reading");
  showLoader(true);
  startLoaderMessages();

  try {
    const payload = {
      name,
      dob,
      time,
      city,
      country,
      question: finalQuestion,
      topic: selectedTopic,
      email,
    };

    const response = await fetch("/api/reading", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const json = await response.json();

    if (!response.ok) {
      throw new Error(json.detail || "Error generating reading.");
    }

    renderReadingResult(json.data);
  } catch (err) {
    console.error("Submission error:", err);
    showLoader(false);
    showScreen("screen-input");
    showError(err.message || "Could not connect to cosmic engine. Please check birth city spelling.");
  }
}

function showError(msg) {
  const banner = document.getElementById("error-banner");
  banner.textContent = msg;
  banner.style.display = "block";
  if (window.gsap) {
    gsap.fromTo(banner, { scale: 0.95, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.3 });
  }
}


// --- 4. SCREEN SWITCHER ---
function showScreen(screenId) {
  const screens = document.querySelectorAll(".kiosk-screen");
  screens.forEach((s) => {
    if (s.id === screenId) {
      s.classList.add("active");
      s.style.display = "block";
      s.style.opacity = "1";
    } else {
      s.classList.remove("active");
      s.style.display = "none";
      s.style.opacity = "0";
    }
  });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

function showLoader(isLoading) {
  const loader = document.getElementById("reading-loader");
  const content = document.getElementById("reading-content");
  if (loader) loader.style.display = isLoading ? "block" : "none";
  if (content) content.style.display = isLoading ? "none" : "block";
}

let loaderMsgInterval;
function startLoaderMessages() {
  const msgs = [
    "Calculating exact planetary positions at birth...",
    "Analyzing your Lagna and Moon Rashi (Chandra)...",
    "Mapping Bhava strengths and planetary dignities...",
    "Computing Vimshottari Mahadasha and Antardasha...",
    "Preparing your personalized Kundali guidance...",
  ];
  let idx = 0;
  const statusEl = document.getElementById("loader-status");
  statusEl.textContent = msgs[0];

  clearInterval(loaderMsgInterval);
  loaderMsgInterval = setInterval(() => {
    idx = (idx + 1) % msgs.length;
    statusEl.textContent = msgs[idx];
  }, 2500);
}


// --- 5. RENDER READING RESULT ---
function renderReadingResult(data) {
  clearInterval(loaderMsgInterval);
  showLoader(false);

  // Fill in badges
  document.getElementById("res-guest-name").textContent = data.name || "You";
  document.getElementById("res-asc").textContent = data.ascendant || "Unknown";
  document.getElementById("res-moon").textContent = `${data.moon_sign || ""} (${data.nakshatra || ""})`;
  document.getElementById("res-ak").textContent = data.atmakaraka || "Sun";
  document.getElementById("res-dasha").textContent = data.current_dasha || "Active Period";

  // Render Active Yogas
  const yogasContainer = document.getElementById("res-yogas-container");
  const yogasList = document.getElementById("res-yogas-list");
  if (yogasContainer && yogasList) {
    if (data.active_yogas && data.active_yogas.length > 0) {
      yogasList.innerHTML = data.active_yogas.map(y => `
        <div style="background: rgba(14, 20, 32, 0.85); border: 1px solid rgba(229, 185, 76, 0.4); padding: 5px 12px; border-radius: 6px; font-size: 0.85rem; color: #fff; display: inline-flex; align-items: center; gap: 6px;">
          <span style="color: #10b981; font-size: 0.65rem;">●</span>
          <span style="color: #ffd875; font-weight: 700;">${y.name}</span>
          <span style="font-size: 0.72rem; color: #94a3b8;">[${y.category}]</span>
        </div>
      `).join('');
      yogasContainer.style.display = "block";
    } else {
      yogasContainer.style.display = "none";
    }
  }

  // Parse Markdown to HTML
  const markdownContainer = document.getElementById("res-reading-text");
  if (window.marked) {
    markdownContainer.innerHTML = marked.parse(data.reading || "Your reading is complete.");
  } else {
    markdownContainer.textContent = data.reading || "";
  }

  // Sacred Kuldevi & Nakshatra Blessing Card
  const deity = data.nakshatra_deity || data.archetype_title || "Your Divine Guardian";
  const blessing = data.blessing_message || data.life_focus || `${deity} is your Nakshatra Lord. May their divine blessings guide you on your life journey.`;
  const deityTitleEl = document.getElementById("res-deity-title");
  const deityBlessingEl = document.getElementById("res-deity-blessing");
  const blessingCardEl = document.getElementById("res-blessing-card");
  if (deityTitleEl) deityTitleEl.textContent = deity;
  if (deityBlessingEl) deityBlessingEl.textContent = blessing;
  if (blessingCardEl) blessingCardEl.style.display = "block";

  // Scroll reading pane to top
  const scrollPane = document.querySelector(".reading-scroll-pane");
  if (scrollPane) scrollPane.scrollTop = 0;

  // Start User Activity-Aware Idle Timer
  startIdleCountdown();
}


// --- 6. USER-ACTIVITY-AWARE IDLE TIMER ---
function resetIdleTimerOnActivity() {
  // If reading screen is active, reset countdown on any user touch/scroll/click
  const screenReading = document.getElementById("screen-reading");
  if (screenReading && screenReading.classList.contains("active")) {
    countdownSeconds = TOTAL_IDLE_SECONDS;
    const countEl = document.getElementById("countdown-num");
    if (countEl) countEl.textContent = countdownSeconds;
  }
}

function startIdleCountdown() {
  clearInterval(idleTimerInterval);
  countdownSeconds = TOTAL_IDLE_SECONDS;
  const countEl = document.getElementById("countdown-num");
  if (countEl) countEl.textContent = countdownSeconds;

  idleTimerInterval = setInterval(() => {
    countdownSeconds--;
    if (countEl) countEl.textContent = countdownSeconds;
    if (countdownSeconds <= 0) {
      clearInterval(idleTimerInterval);
      window.location.href = "/";
    }
  }, 1000);
}

// Gentle form inactivity timeout (2.5 mins idle returns to cosmic attractor)
let formInactivityTimeout = null;
const FORM_INACTIVITY_LIMIT = 150000;

function resetFormInactivityTimer() {
  clearTimeout(formInactivityTimeout);
  const screenInput = document.getElementById("screen-input");
  if (screenInput && screenInput.classList.contains("active")) {
    formInactivityTimeout = setTimeout(() => {
      window.location.href = "/";
    }, FORM_INACTIVITY_LIMIT);
  }
}

// Attach activity listeners to window & scroll containers
["mousedown", "mousemove", "touchstart", "touchmove", "scroll", "keydown"].forEach((evtName) => {
  window.addEventListener(evtName, () => {
    resetIdleTimerOnActivity();
    resetFormInactivityTimer();
  }, { passive: true });
});
resetFormInactivityTimer();

function resetToWelcomeScreen() {
  clearInterval(idleTimerInterval);
  clearInterval(loaderMsgInterval);

  // Reset form
  document.getElementById("kiosk-form").reset();
  document.getElementById("guest-dob").value = "1995-05-15";
  document.getElementById("guest-time").value = "10:30";
  document.getElementById("guest-country").value = "India";
  document.getElementById("custom-question-container").style.display = "none";
  document.getElementById("custom-question-input").value = "";

  // Reset topic cards to first
  const cards = document.querySelectorAll(".topic-card");
  cards.forEach((c) => c.classList.remove("active"));
  if (cards[0]) {
    cards[0].classList.add("active");
    selectedTopic = cards[0].dataset.topic;
    selectedPrompt = cards[0].dataset.prompt;
  }

  showScreen("screen-input");
}


// --- 7. INITIALIZE ON LOAD ---
window.addEventListener("DOMContentLoaded", () => {
  initThreeBg();
  setupTopicCards();
});
