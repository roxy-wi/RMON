var charts = []
function getChartDataHapWiRam(ip) {
    let jsonData = {
        'ip': ip,
    }
    $.ajax({
        url: "/metrics/ram",
		data: JSON.stringify(jsonData),
        contentType: "application/json; charset=utf-8",
		beforeSend: function() {
			$('#ram').html('<img class="loading_hapwi_overview" src="/static/images/loading.gif" alt="loading..." />')
		},
		type: "POST",
        success: function (result) {
            let data = [];
            data.push(result.chartData.rams);
            // Получение значений из строки и разделение их на массив
            const ramsData = data[0].trim().split(' ');

            // Преобразование значений в числа
            const formattedData = ramsData.map(value => parseFloat(value));
            renderChartHapWiRam(formattedData);
        }
    });
}
function renderChartHapWiRam(data) {
    var ctx = document.getElementById('ram').getContext('2d');
    var myChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['used','free','shared','buff','available','total'],
            datasets: [
                {
                    normalized: true,
                    data: data,
                    backgroundColor: [
                        '#ff6384',
                        '#33ff26',
                        '#ff9f40',
                        '#ffcd56',
                        '#4bc0c0',
                        '#36a2eb',
                    ]
                }
            ]
        },
        options: {
            maintainAspectRatio: false,
            plugins: {
                title: {
                    display: true,
                    text: "RAM usage in Mb",
                    font: {
                        size: 15
                    },
                    padding: {
                        top: 10,
                        bottom: 0
                    }
                },
                legend: {
                    display: false,
                    align: 'start',
                    position: 'left',
                    labels: {
                        color: 'rgb(255, 99, 132)',
                        font: {
                            size: 5,
                            family: 'BlinkMacSystemFont'
                        },
                        boxWidth: 13,
                        padding: 5
                    },
                }
            }
        }
    });
    charts.push(myChart);
}
function getChartDataHapWiCpu(ip) {
    let jsonData = {
        'ip': ip,
    }
    $.ajax({
        url: "/metrics/cpu",
		data: JSON.stringify(jsonData),
        contentType: "application/json; charset=utf-8",
		type: "POST",
        success: function (result) {
            // Получение значений из строки и разделение их на массив
            const ramsData = result.chartData.cpus.trim().split(' ').map(parseFloat);

            // Преобразование значений в числа
            const formattedData = ramsData.map(value => parseFloat(value));
            renderChartHapWiCpu(formattedData);
        }
    });
}
function renderChartHapWiCpu(data) {
    var ctx = document.getElementById('cpu').getContext('2d');
    var myChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['user','sys','nice','idle','wait','hi','si','steal', 'total'],
            datasets: [
                {
                    normalized: true,
                    data: data,
                    backgroundColor: [
						'#ff6384',
						'#36a2eb',
						'#ff9f40',
						'#ffcd56',
						'#4bc0c0',
						'#5d9ceb',
						'#2c6969',
						'#5e1313',
					]
                }
            ]
        },
        options: {
            animation: true,
			maintainAspectRatio: false,
			plugins: {
				title: {
					display: true,
					text: "CPU usage in %",
					font: { size: 15 },
					padding: { top: 10 }
				},
				legend: {
					display: false,
					position: 'left',
					align: 'end',
					labels: {
						color: 'rgb(255, 99, 132)',
						font: { size: 10, family: 'BlinkMacSystemFont' },
						boxWidth: 13,
						padding: 5
					},
				}
			},
            scales: {
                x: {
                    ticks: {
                        max: 100,
                        min: 100
                    }
                }
            },
        }
    });
    charts.push(myChart);
}

function showOverviewHapWI() {
    removeData();
	getChartDataHapWiCpu('127.0.0.1');
	getChartDataHapWiRam('127.0.0.1');
	NProgress.configure({showSpinner: false});
}
function updatingCpuRamCharts() {
	showOverviewHapWI();
}
