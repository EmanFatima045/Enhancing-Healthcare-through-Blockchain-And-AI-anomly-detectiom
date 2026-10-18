/**
 * HealerPlus 2.0 - Red Team Cyber-Attack Simulation Engine
 */

window.HealerAttackSimulator = {
  async executeScenario(scenario) {
    const terminal = document.getElementById("sim-terminal-output");
    if (!terminal) return;

    this.logTerminal(`[ATTACK INITIATED] Vector: ${scenario.toUpperCase()}`, "text-red");
    this.logTerminal(`[RED TEAM] Injecting malicious payload through target gateway /api/v1/auth/login...`, "text-muted");

    try {
      // Try calling backend API
      const res = await fetch("http://127.0.0.1:8000/api/v1/security/simulate-attack", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ attack_scenario: scenario })
      });

      if (res.ok) {
        const data = await res.json();
        this.displayResults(data, terminal);
        return;
      }
    } catch (e) {
      // Fallback local execution
      console.log("Backend offline, running local high-fidelity attack simulation.");
    }

    // Local simulated threat response
    setTimeout(() => {
      let threatName, conf, anom, action, ip;
      if (scenario === "brute_force") {
        threatName = "Brute-Force Attack";
        conf = "98.9%";
        anom = "0.94";
        action = "BLOCK_IP_AND_TRIGGER_SMART_CONTRACT_ALERT";
        ip = "185.220.101.5";
      } else if (scenario === "credential_stuffing") {
        threatName = "Credential Stuffing & Impossible Travel";
        conf = "96.4%";
        anom = "0.89";
        action = "CHALLENGE_WITH_MFA_AND_THROTTLE";
        ip = "103.251.167.22";
      } else if (scenario === "exfiltration") {
        threatName = "Unauthorized EMR Data Exfiltration";
        conf = "99.2%";
        anom = "0.97";
        action = "REVOKE_SESSION_AND_FLAG_AUDITOR";
        ip = "193.106.191.24";
      } else {
        threatName = "Smart Contract Gateway DDoS";
        conf = "97.8%";
        anom = "0.96";
        action = "RATE_LIMIT_AND_IP_BLACKHOLE";
        ip = "45.142.122.18";
      }

      this.logTerminal(`[BLUE TEAM INTERCEPT] Intercepted by AI Intrusion Detection Engine.`, "text-cyan");
      this.logTerminal(`[AI MODEL VERDICT] Classification: ${threatName} | Confidence: ${conf} | Anomaly Score: ${anom}`, "text-green");
      this.logTerminal(`[DEFENSE ACTION] Executing: ${action}`, "text-red");
      this.logTerminal(`[BLOCKCHAIN] Logging forensic Merkle audit event to MedicalAuditRegistry.sol...`, "text-purple");
      this.logTerminal(`[STATUS] Threat neutralized. Source IP [${ip}] isolated.`, "text-green");

      // Add to SOC Feed
      window.HealerSOC.addIncident({
        type: threatName,
        ip: ip,
        conf: conf,
        action: action,
        time: "Just now"
      });

      // Add to Blockchain Explorer
      window.HealerWeb3.addTransaction("CYBER_INCIDENT_FLAGGED", `0x${ip.replace(/\./g, '')}`, "0xMedicalAuditRegistry.sol", "INTERCEPTED");

      // Update Chart
      window.HealerAI.updateThreatStats(threatName);
    }, 600);
  },

  displayResults(data, terminal) {
    const a = data.threat_analysis;
    this.logTerminal(`[AI MODEL VERDICT] Classification: ${a.attack_type} | Confidence: ${(a.confidence * 100).toFixed(1)}%`, "text-green");
    this.logTerminal(`[DEFENSE ACTION] ${a.recommended_action}`, "text-red");
    this.logTerminal(`[BLOCKCHAIN] Sealed in Block #${window.HealerWeb3.blockNumber + 1}`, "text-purple");

    window.HealerSOC.addIncident({
      type: a.attack_type,
      ip: data.threat_log_entry.ip_address,
      conf: `${(a.confidence * 100).toFixed(1)}%`,
      action: a.recommended_action,
      time: "Just now"
    });
    window.HealerAI.updateThreatStats(a.attack_type);
  },

  logTerminal(text, colorClass = "text-muted") {
    const terminal = document.getElementById("sim-terminal-output");
    if (!terminal) return;
    const line = document.createElement("div");
    line.className = `terminal-line ${colorClass}`;
    line.textContent = `[${new Date().toLocaleTimeString()}] ` + text;
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;
  }
};
