/**
 * Chart.js Analytics Controller for IR Compression Metrics.
 */

let compressionChartInstance = null;
let compressionChartAnalyticsInstance = null;

function renderCompressionChart(metrics, advanced, comparison) {
    const canvas = document.getElementById('compression-chart');
    const canvasAnalytics = document.getElementById('compression-chart-analytics');
    if (!canvas && !canvasAnalytics) return;

    const rawBytes = metrics.raw_ir_text_bytes || 100;
    const optBytes = metrics.optimized_ir_text_bytes || 60;
    const bcBytes = metrics.binary_bytecode_bytes || 35;
    const huffBytes = metrics.huffman_compressed_bytes || 20;

    const labels = [
        '1. Raw Text IR',
        '2. SSA Optimized IR',
        '3. Binary Bytecode',
        '4. Huffman Baseline'
    ];
    const values = [rawBytes, optBytes, bcBytes, huffBytes];
    const bgColors = [
        'rgba(142, 142, 147, 0.35)', // System Gray (Raw)
        'rgba(10, 132, 255, 0.65)',   // System Blue (SSA Opt)
        'rgba(191, 90, 242, 0.75)',   // System Purple (Bytecode)
        'rgba(100, 210, 255, 0.85)'   // System Teal (Huffman Baseline)
    ];
    const borderColors = ['#8e8e93', '#0a84ff', '#bf5af2', '#64d2ff'];

    // 5th bar: Advanced SoA (columnar) bitstream, when the server surfaces it.
    if (advanced && typeof advanced.final_advanced_bitstream_bytes === 'number') {
        labels.push('5. Advanced SoA Bitstream');
        values.push(advanced.final_advanced_bitstream_bytes);
        bgColors.push('rgba(48, 209, 88, 0.85)'); // System Green (Advanced)
        borderColors.push('#30d158');
    }

    // 6th bar: Overall Benchmark Champion (Deflate, Brotli, Zstd, SoA, etc.)
    if (comparison && comparison.best_technique && typeof comparison.best_compressed_bytes === 'number') {
        const cleanName = comparison.best_technique.replace(/\s*\(.*\)/, '').trim();
        labels.push(`6. 🏆 Winner (${cleanName})`);
        values.push(comparison.best_compressed_bytes);
        bgColors.push('rgba(255, 214, 10, 0.85)'); // System Amber/Gold (Winner)
        borderColors.push('#ffd60a');
    }

    const data = {
        labels: labels,
        datasets: [{
            label: 'Size in Bytes (Lower is better)',
            data: values,
            backgroundColor: bgColors,
            borderColor: borderColors,
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
                backgroundColor: 'rgba(36, 36, 40, 0.95)',
                titleColor: '#ffffff',
                bodyColor: '#8e8e93',
                borderColor: 'rgba(255, 255, 255, 0.14)',
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
                    color: '#8e8e93',
                    font: {
                        family: '-apple-system, BlinkMacSystemFont, "SF Pro", sans-serif',
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
                    color: '#8e8e93',
                    font: {
                        family: 'SF Mono, Menlo, monospace',
                        size: 10
                    }
                }
            }
        },
        animation: {
            duration: (window.matchMedia
                && window.matchMedia('(prefers-reduced-motion: reduce)').matches)
                ? 0 : 600,
            easing: 'easeOutQuart'
        }
    };

    if (canvas) {
        if (compressionChartInstance) {
            compressionChartInstance.data = JSON.parse(JSON.stringify(data));
            compressionChartInstance.update();
        } else {
            compressionChartInstance = new Chart(canvas, {
                type: 'bar',
                data: JSON.parse(JSON.stringify(data)),
                options: options
            });
        }
    }

    if (canvasAnalytics) {
        if (compressionChartAnalyticsInstance) {
            compressionChartAnalyticsInstance.data = JSON.parse(JSON.stringify(data));
            compressionChartAnalyticsInstance.update();
        } else {
            compressionChartAnalyticsInstance = new Chart(canvasAnalytics, {
                type: 'bar',
                data: JSON.parse(JSON.stringify(data)),
                options: options
            });
        }
    }
}
