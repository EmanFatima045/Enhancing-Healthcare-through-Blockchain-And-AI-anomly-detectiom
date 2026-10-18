/**
 * HealerPlus 2.0 - Real-Time IoMT ECG Oscilloscope & Telemetry Engine
 */

window.HealerIoMT = {
  canvas: null,
  ctx: null,
  animationFrameId: null,
  telemetryIntervalId: null,
  socket: null,
  reconnectTimerId: null,
  mode: "normal",
  x: 0,
  lastY: 100,
  step: 2,
  phase: 0,

  initECG() {
    this.canvas = document.getElementById("ecgCanvas");
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext("2d");

    if (this.animationFrameId) cancelAnimationFrame(this.animationFrameId);

    // Fix DPI
    this.canvas.width = this.canvas.parentElement.clientWidth || 1000;
    this.canvas.height = 200;

    // Draw grid
    this.clearGrid();
    this.startLoop();
    this.startTelemetryPoller();
  },

  clearGrid() {
    const width = this.canvas.width;
    const height = this.canvas.height;
    this.ctx.fillStyle = "#040810";
    this.ctx.fillRect(0, 0, width, height);

    // Minor grid
    this.ctx.strokeStyle = "rgba(0, 245, 160, 0.06)";
    this.ctx.lineWidth = 1;
    for (let gx = 0; gx < width; gx += 20) {
      this.ctx.beginPath();
      this.ctx.moveTo(gx, 0);
      this.ctx.lineTo(gx, height);
      this.ctx.stroke();
    }
    for (let gy = 0; gy < height; gy += 20) {
      this.ctx.beginPath();
      this.ctx.moveTo(0, gy);
      this.ctx.lineTo(width, gy);
      this.ctx.stroke();
    }
  },

  startLoop() {
    const draw = () => {
      const height = this.canvas.height;
      const width = this.canvas.width;
      const midY = height / 2;

      // Erase trailing slice
      this.ctx.fillStyle = "#040810";
      this.ctx.fillRect(this.x, 0, 15, height);

      // Restore faint grid for erased slice
      this.ctx.strokeStyle = "rgba(0, 245, 160, 0.06)";
      for (let gy = 0; gy < height; gy += 20) {
        this.ctx.beginPath();
        this.ctx.moveTo(this.x, gy);
        this.ctx.lineTo(this.x + 15, gy);
        this.ctx.stroke();
      }

      // Compute P-Q-R-S-T ECG Waveform
      this.phase += 0.06;
      const cycle = this.phase % (2 * Math.PI);
      let yOffset = 0;

      if (this.mode === "normal") {
        if (cycle > 0.4 && cycle < 0.6) yOffset = -12 * Math.sin((cycle - 0.4) * Math.PI / 0.2); // P-wave
        else if (cycle > 0.75 && cycle < 0.8) yOffset = 8;  // Q-dip
        else if (cycle >= 0.8 && cycle <= 0.95) yOffset = -75 * Math.sin((cycle - 0.8) * Math.PI / 0.15); // R-Peak
        else if (cycle > 0.95 && cycle < 1.05) yOffset = 18; // S-dip
        else if (cycle > 1.3 && cycle < 1.7) yOffset = -18 * Math.sin((cycle - 1.3) * Math.PI / 0.4); // T-wave
        else yOffset = (Math.random() - 0.5) * 2;
      } else if (this.mode === "clinical_emergency") {
        // Fast, elevated ST tachycardia
        this.phase += 0.08;
        if (cycle >= 0.75 && cycle <= 0.95) yOffset = -90 * Math.sin((cycle - 0.75) * Math.PI / 0.2);
        else yOffset = -25 + (Math.random() - 0.5) * 8; // ST Elevation
      } else if (this.mode === "sensor_tampering") {
        // Square wave noise / fuzzing
        yOffset = (Math.random() > 0.5 ? 60 : -60) + (Math.random() - 0.5) * 20;
      } else {
        // MITM glitch / flatline replay
        yOffset = Math.sin(this.phase * 5) * 8;
      }

      const currentY = midY + yOffset;

      // Draw ECG line
      this.ctx.beginPath();
      this.ctx.strokeStyle = (this.mode === "normal") ? "#00f5a0" : (this.mode === "clinical_emergency" ? "#ff9f1c" : "#ff3366");
      this.ctx.lineWidth = 2.2;
      this.ctx.shadowColor = this.ctx.strokeStyle;
      this.ctx.shadowBlur = 8;
      this.ctx.moveTo(this.x, this.lastY);
      this.ctx.lineTo(this.x + this.step, currentY);
      this.ctx.stroke();

      this.lastY = currentY;
      this.x += this.step;

      if (this.x >= width) {
        this.x = 0;
      }

      this.animationFrameId = requestAnimationFrame(draw);
    };

    draw();
  },

  startTelemetryPoller() {
    if (this.telemetryIntervalId) return;
    this.connectWebSocket();
    this.telemetryIntervalId = setInterval(() => {
      if (!this.socket || this.socket.readyState !== WebSocket.OPEN) this.fetchTelemetry();
    }, 1800);
  },

  setMode(mode) {
    this.mode = mode;
    this.connectWebSocket(true);
  },

  connectWebSocket(forceReconnect = false) {
    if (forceReconnect && this.socket) {
      this.socket.onclose = null;
      this.socket.close();
      this.socket = null;
    }
    if (this.socket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(this.socket.readyState)) return;

    const streamStatus = document.getElementById("telemetry-live-status");
    const url = `ws://127.0.0.1:8000/api/v1/iomt/ws/PATIENT_001?mode=${encodeURIComponent(this.mode)}`;
    try {
      this.socket = new WebSocket(url);
      this.socket.onopen = () => {
        if (streamStatus) streamStatus.textContent = "Live • WebSocket";
      };
      this.socket.onmessage = event => this.applyTelemetry(JSON.parse(event.data));
      this.socket.onerror = () => {
        if (streamStatus) streamStatus.textContent = "Reconnecting…";
      };
      this.socket.onclose = () => {
        this.socket = null;
        if (streamStatus) streamStatus.textContent = "Demo • reconnecting";
        clearTimeout(this.reconnectTimerId);
        this.reconnectTimerId = setTimeout(() => this.connectWebSocket(), 3500);
      };
    } catch (error) {
      this.fetchTelemetry();
    }
  },

  async fetchTelemetry() {
    const streamStatus = document.getElementById("telemetry-live-status");
    try {
      const url = `http://127.0.0.1:8000/api/v1/iomt/stream?patient_id=PATIENT_001&mode=${encodeURIComponent(this.mode)}`;
      const response = await fetch(url, { signal: AbortSignal.timeout(2200) });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const packet = await response.json();
      this.applyTelemetry(packet);
      if (streamStatus) streamStatus.textContent = "Live • AI analyzed";
    } catch (error) {
      this.updateGauges();
      if (streamStatus) streamStatus.textContent = "Demo • browser generated";
    }
  },

  applyTelemetry(packet) {
    const security = packet.security_status || {};
    const isCyberAttack = security.classification === "SENSOR_TAMPERING_ATTACK";
    const isEmergency = security.classification === "CLINICAL_EMERGENCY";
    const isAlarm = isCyberAttack || isEmergency;
    const hrCard = document.getElementById("gauge-card-hr");
    const spo2Card = document.getElementById("gauge-card-spo2");
    const alarmBadge = document.getElementById("ecg-alarm-badge");
    const alertMsg = document.getElementById("iomt-alert-msg");

    hrCard?.classList.toggle("gauge-alarm", isAlarm);
    spo2Card?.classList.toggle("gauge-alarm", isAlarm);
    if (alarmBadge) {
      const label = isCyberAttack ? "SENSOR TAMPERING / MITM ATTACK" : (isEmergency ? "CRITICAL CLINICAL ALERT" : "SINUS RHYTHM NORMAL");
      alarmBadge.innerHTML = `<span class="pulse-dot ${isAlarm ? "red" : "green"}"></span> ${label}`;
      alarmBadge.style.color = isAlarm ? "#ff6687" : "#2dd4bf";
    }
    if (alertMsg) alertMsg.textContent = security.message || "Telemetry analyzed by the Healer Plus AI service.";

    document.getElementById("val-hr").innerHTML = `${packet.heart_rate_bpm} <span class="gauge-unit">BPM</span>`;
    document.getElementById("val-spo2").innerHTML = `${packet.spo2_percentage} <span class="gauge-unit">%</span>`;
    document.getElementById("val-bp").innerHTML = `${packet.systolic_bp}/${packet.diastolic_bp} <span class="gauge-unit">mmHg</span>`;
    document.getElementById("val-temp").innerHTML = `${packet.body_temp_celsius} <span class="gauge-unit">°C</span>`;
    document.getElementById("val-glucose").innerHTML = `${packet.blood_glucose_mgdl} <span class="gauge-unit">mg/dL</span>`;
    document.getElementById("val-jitter").innerHTML = `${packet.packet_jitter_ms} <span class="gauge-unit">ms</span>`;
    document.getElementById("val-chkerr").textContent = Number(packet.checksum_error_rate).toFixed(3);
  },

  updateGauges() {
    let hr, spo2, sys, dia, temp, glucose, jitter, chkerr;
    const hrCard = document.getElementById("gauge-card-hr");
    const spo2Card = document.getElementById("gauge-card-spo2");
    const alarmBadge = document.getElementById("ecg-alarm-badge");
    const alertMsg = document.getElementById("iomt-alert-msg");

    if (this.mode === "normal") {
      hr = 72 + Math.floor(Math.random() * 5);
      spo2 = 98 + Math.floor(Math.random() * 2);
      sys = 120 + Math.floor(Math.random() * 4);
      dia = 80 + Math.floor(Math.random() * 3);
      temp = (36.8 + (Math.random() * 0.2 - 0.1)).toFixed(1);
      glucose = 95 + Math.floor(Math.random() * 6);
      jitter = (3.5 + Math.random() * 2).toFixed(1);
      chkerr = "0.001";

      hrCard.classList.remove("gauge-alarm");
      spo2Card.classList.remove("gauge-alarm");
      alarmBadge.innerHTML = `<span class="pulse-dot green"></span> SINUS RHYTHM NORMAL`;
      alarmBadge.style.color = "#00f5a0";
      alertMsg.textContent = "End-to-end cryptographic checksum verified. Zero tampering detected across medical IoT payload.";
    } else if (this.mode === "clinical_emergency") {
      hr = 168 + Math.floor(Math.random() * 10);
      spo2 = 82 + Math.floor(Math.random() * 4);
      sys = 195 + Math.floor(Math.random() * 10);
      dia = 112 + Math.floor(Math.random() * 6);
      temp = "39.4";
      glucose = 280;
      jitter = "8.4";
      chkerr = "0.008";

      hrCard.classList.add("gauge-alarm");
      spo2Card.classList.add("gauge-alarm");
      alarmBadge.innerHTML = `<span class="pulse-dot red"></span> CRITICAL: TACHYCARDIA & HYPOXIA`;
      alarmBadge.style.color = "#ff3366";
      alertMsg.textContent = "⚠️ CLINICAL ALARM: Acute desaturation (SpO2 82%) and severe tachycardia detected! Dispatched to ER ICU monitor.";
    } else {
      hr = 240;
      spo2 = 45;
      sys = 270;
      dia = 160;
      temp = "44.2";
      glucose = 540;
      jitter = "215.0";
      chkerr = "0.780";

      hrCard.classList.add("gauge-alarm");
      spo2Card.classList.add("gauge-alarm");
      alarmBadge.innerHTML = `<span class="pulse-dot red"></span> 🚨 SENSOR TAMPERING / MITM ATTACK`;
      alarmBadge.style.color = "#ff3366";
      alertMsg.textContent = "🚨 CYBER THREAT DETECTED: Checksum failure (78%) & high jitter (215ms). Tampered telemetry isolated from patient health database.";
    }

    document.getElementById("val-hr").innerHTML = `${hr} <span class="gauge-unit">BPM</span>`;
    document.getElementById("val-spo2").innerHTML = `${spo2} <span class="gauge-unit">%</span>`;
    document.getElementById("val-bp").innerHTML = `${sys}/${dia} <span class="gauge-unit">mmHg</span>`;
    document.getElementById("val-temp").innerHTML = `${temp} <span class="gauge-unit">°C</span>`;
    document.getElementById("val-glucose").innerHTML = `${glucose} <span class="gauge-unit">mg/dL</span>`;
    document.getElementById("val-jitter").innerHTML = `${jitter} <span class="gauge-unit">ms</span>`;
    document.getElementById("val-chkerr").textContent = chkerr;
  }
};
