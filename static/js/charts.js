/**
 * ═══════════════════════════════════════════════════════
 * CHART.JS UTILITIES & CONFIGURATIONS
 * ═══════════════════════════════════════════════════════
 */

// Configure Chart.js defaults
Chart.defaults.font.family = "'IBM Plex Sans', sans-serif";
Chart.defaults.color = '#8892a8';
Chart.defaults.borderColor = '#1f2d47';

const chartColors = {
    green: '#10b981',
    blue: '#3b82f6',
    amber: '#f59e0b',
    red: '#ef4444',
    greens: ['#10b981', '#34d399', '#6ee7b7', '#d1fae5'],
    blues: ['#3b82f6', '#60a5fa', '#93c5fd', '#dbeafe'],
    reds: ['#ef4444', '#f87171', '#fca5a5', '#fee2e2'],
    ambers: ['#f59e0b', '#fbbf24', '#fcd34d', '#fef3c7']
};

/**
 * Create a styled line chart
 */
function createLineChart(ctx, label, data, color = chartColors.blue) {
    return new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.labels,
            datasets: [{
                label: label,
                data: data.values,
                borderColor: color,
                backgroundColor: color + '1a',
                borderWidth: 2,
                fill: true,
                tension: 0.4,
                pointRadius: 3,
                pointHoverRadius: 5,
                pointBackgroundColor: color
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    labels: { color: '#e1e8f0', font: { size: 12 } }
                }
            },
            scales: {
                y: {
                    ticks: { color: '#8892a8' },
                    grid: { color: 'rgba(31, 45, 71, 0.5)' }
                },
                x: {
                    ticks: { 
                        color: '#8892a8',
                        autoSkip: true,
                        maxTicksLimit: 12
                    },
                    grid: { color: 'rgba(31, 45, 71, 0.5)' }
                }
            }
        }
    });
}

/**
 * Create a styled bar chart
 */
function createBarChart(ctx, label, data, colors = chartColors.blues) {
    return new Chart(ctx, {
        type: 'bar',
        data: {
            labels: data.labels,
            datasets: [{
                label: label,
                data: data.values,
                backgroundColor: colors,
                borderColor: colors,
                borderWidth: 1
            }]
        },
        options: {
            responsive: true,
            indexAxis: 'x',
            plugins: {
                legend: { labels: { color: '#e1e8f0' } }
            },
            scales: {
                y: {
                    ticks: { color: '#8892a8' },
                    grid: { color: 'rgba(31, 45, 71, 0.5)' }
                },
                x: {
                    ticks: { 
                        color: '#8892a8',
                        autoSkip: true,
                        maxTicksLimit: 12
                    },
                    grid: { color: 'rgba(31, 45, 71, 0.5)' }
                }
            }
        }
    });
}

/**
 * Create a styled radar chart
 */
function createRadarChart(ctx, label, data) {
    return new Chart(ctx, {
        type: 'radar',
        data: {
            labels: data.labels,
            datasets: [{
                label: label,
                data: data.values,
                borderColor: chartColors.green,
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                borderWidth: 2,
                pointBackgroundColor: chartColors.green,
                pointBorderColor: '#0a0e27',
                pointRadius: 5
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: { labels: { color: '#e1e8f0' } }
            },
            scales: {
                r: {
                    beginAtZero: true,
                    grid: { color: 'rgba(31, 45, 71, 0.5)' },
                    ticks: { color: '#8892a8' }
                }
            }
        }
    });
}

/**
 * Create a styled doughnut chart
 */
function createDoughnutChart(ctx, label, data, colors = chartColors.blues) {
    return new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                backgroundColor: colors,
                borderColor: '#0a0e27',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: '#e1e8f0' }
                }
            }
        }
    });
}

/**
 * Update existing chart with new data
 */
function updateChartData(chart, newData, newLabels = null) {
    if (!chart) return;
    
    chart.data.datasets[0].data = newData;
    if (newLabels) chart.data.labels = newLabels;
    chart.update('none'); // Update without animation
}

/**
 * Initialize all charts on page load
 */
document.addEventListener('DOMContentLoaded', () => {
    // Charts will be created by specific tab loaders
    console.log('✅ Chart utilities loaded');
});
