/**
 * HealerPlus 2.0 - Security Operations Center (SOC) Feed Manager
 */

window.HealerSOC = {
  incidents: [
    {
      id: "INC-9912",
      type: "Brute-Force Login Attack",
      ip: "194.26.29.114",
      conf: "98.4%",
      action: "IP_BLOCKED_AND_SMART_CONTRACT_LOGGED",
      time: "2 mins ago"
    },
    {
      id: "INC-9911",
      type: "Credential Stuffing & Impossible Travel",
      ip: "45.154.255.89",
      conf: "96.1%",
      action: "MFA_CHALLENGE_FORCED",
      time: "12 mins ago"
    },
    {
      id: "INC-9910",
      type: "IoMT Sensor Fuzzing / Tampering",
      ip: "10.0.4.18 (Bedside Monitor)",
      conf: "99.0%",
      action: "DEVICE_ISOLATED_FROM_EMR",
      time: "28 mins ago"
    }
  ],

  renderFeed() {
    const container = document.getElementById("threat-feed-container");
    if (!container) return;

    container.innerHTML = this.incidents.map(inc => `
      <div class="threat-item">
        <div class="threat-header">
          <span class="threat-name"><i class="fa-solid fa-triangle-exclamation"></i> ${inc.type}</span>
          <span class="threat-time">${inc.time}</span>
        </div>
        <div class="threat-meta">
          <span>Source: <strong class="font-mono">${inc.ip}</strong></span>
          <span>AI Conf: <strong class="text-green">${inc.conf}</strong></span>
        </div>
        <div class="threat-meta mt-1">
          <span>Action: <strong class="text-red font-mono">${inc.action}</strong></span>
        </div>
      </div>
    `).join('');

    // Update Counter
    const chip = document.getElementById("threat-chip-count");
    if (chip) chip.textContent = `${this.incidents.length} Intercepts`;

    const kpiCount = document.getElementById("kpi-threats-count");
    if (kpiCount) kpiCount.textContent = `${this.incidents.length + 12} Intercepted`;
  },

  addIncident(item) {
    const id = `INC-${Math.floor(1000 + Math.random() * 9000)}`;
    this.incidents.unshift({
      id: id,
      type: item.type,
      ip: item.ip,
      conf: item.conf,
      action: item.action,
      time: item.time || "Just now"
    });
    this.renderFeed();
  }
};
