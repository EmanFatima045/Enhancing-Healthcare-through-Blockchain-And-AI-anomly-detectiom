/**
 * HealerPlus 2.0 - AI Intrusion Detection & Threat Chart Visualizer
 */

window.HealerAI = {
  chartInstance: null,

  initChart() {
    const ctx = document.getElementById('threatDistributionChart');
    if (!ctx) return;

    if (this.chartInstance) {
      this.chartInstance.destroy();
    }

    this.chartInstance = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['Benign Normal Logins', 'Brute-Force Intercepts', 'Credential Stuffing', 'Unauthorized Exfiltration'],
        datasets: [{
          data: [65, 18, 10, 7],
          backgroundColor: [
            '#059669', // emerald green
            '#e11d48', // medical red
            '#d97706', // amber
            '#0284c7'  // royal blue
          ],
          borderColor: '#ffffff',
          borderWidth: 3,
          hoverOffset: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              color: '#334155',
              font: { family: 'Plus Jakarta Sans', size: 12, weight: '600' },
              padding: 14
            }
          }
        },
        cutout: '68%'
      }
    });
  },

  updateThreatStats(threatType) {
    if (!this.chartInstance) return;

    const data = this.chartInstance.data.datasets[0].data;
    if (threatType.includes("Brute-Force")) {
      data[1] += 1;
    } else if (threatType.includes("Credential")) {
      data[2] += 1;
    } else if (threatType.includes("Exfiltration")) {
      data[3] += 1;
    } else {
      data[0] += 1;
    }
    this.chartInstance.update();
  }
};
