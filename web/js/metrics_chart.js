/**
 * Chart.js Analytics Controller for IR Compression Metrics.
 */

let compressionChartInstance = null;

function renderCompressionChart(metrics) {
    const canvas = document.getElementById('compression-chart');
    if (!canvas) return;

    const rawBytes = metrics.raw_ir_text_bytes || 100;
    const optBytes = metrics.optimized_ir_text_bytes || 60;
    const bcBytes = metrics.binary_bytecode_bytes || 35;
    const huffBytes = metrics.huffman_compressed_bytes || 20;

    const data = {
        labels: [
            '1. Raw Text IR',
            '2. SSA Optimized IR',
            '3. Binary Bytecode',
            '4. Huffman Compressed'
        ],
        datasets: [{
            label: 'Size in Bytes (Lower is better)',
            data: [rawBytes, optBytes, bcBytes, huffBytes],
            backgroundColor: [
                'rgba(148, 163, 184, 0.4)',  // Slate (Raw)
                'rgba(59, 130, 246, 0.65)',  // Blue (SSA Opt)
                'rgba(139, 92, 246, 0.75)',  // Purple (Bytecode)
                'rgba(6, 182, 212, 0.9)'     // Cyan (Huffman Final)
            ],
            borderColor: [
                '#94a3b8',
                '#3b82f6',
                '#8b5cf6',
                '#06b6d4'
            ],
            borderWidth: 1.5,
            borderRadius: 6,
        }]
    };

    const options = {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
            legend: {
                display: false
            },
            tooltip: {
                backgroundColor: 'rgba(15, 23, 42, 0.95)',
                titleColor: '#f8fafc',
                bodyColor: '#94a3b8',
                borderColor: 'rgba(255, 255, 255, 0.1)',
                borderWidth: 1,
                padding: 10,
                callbacks: {
                    label: function(context) {
                        const val = context.parsed.y;
                        const initial = rawBytes;
                        const savings = initial > 0 ? (((initial - val) / initial) * 100).toFixed(1) : 0;
                        return ` Size: ${val} bytes (${savings}% saved)`;
                    }
                }
            }
        },
        scales: {
            x: {
                grid: {
                    display: false,
                    drawBorder: false,
                },
                ticks: {
                    color: '#94a3b8',
                    font: {
                        family: 'Inter, sans-serif',
                        size: 11
                    }
                }
            },
            y: {
                beginAtZero: true,
                grid: {
                    color: 'rgba(255, 255, 255, 0.05)',
                    drawBorder: false,
                },
                ticks: {
                    color: '#64748b',
                    font: {
                        family: 'Fira Code, monospace',
                        size: 10
                    }
                }
            }
        },
        animation: {
            duration: 600,
            easing: 'easeOutQuart'
        }
    };

    if (compressionChartInstance) {
        compressionChartInstance.data = data;
        compressionChartInstance.update();
    } else {
        compressionChartInstance = new Chart(canvas, {
            type: 'bar',
            data: data,
            options: options
        });
    }
}
