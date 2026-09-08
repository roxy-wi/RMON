$(function () {
	$( "#check_type" ).on('selectmenuchange',function() {
		check_and_clear_check_type($('#check_type').val());
	});
	$("#new-smon-group").autocomplete({
		source: function (request, response) {
			$.ajax({
				url: api_v_prefix + "/rmon/check-groups",
				contentType: "application/json",
				success: function (data) {
					let names = '';
					for (let name in data) {
						names += data[name]['name'].replaceAll("'", "") + ',';
					}
					response(names.split(','));
				}
			});
		},
		autoFocus: true,
		minLength: -1,
		select: function (event, ui) {
			$('#new-smon-group').focus();
		},
	});
	$( "#smon_http_check_auth_method" ).on('selectmenuchange',function() {
		if ($('#smon_http_check_auth_method').val() === 'basic') {
			$('.smon_http_check_basic').show();
			$('.smon_http_check_mtls').hide();
		} else if ($('#smon_http_check_auth_method').val() === 'mtls') {
			$('.smon_http_check_basic').hide();
			$('.smon_http_check_mtls').show();
		} else {
			$('.smon_http_check_basic').hide();
			$('.smon_http_check_mtls').hide();
		}
	});
	$( "#smon_http_check_proxy_method" ).on('selectmenuchange',function() {
		if ($('#smon_http_check_proxy_method').val() != '0') {
			$('.smon_http_check_proxy').show();
		} else {
			$('.smon_http_check_proxy').hide();
		}
	});
	$( "#smon_http_check_headers_response_type" ).on('selectmenuchange',function() {
		if ($('#smon_http_check_headers_response_type').val() != '0') {
			$('#new-smon-headers-response').show();
		} else {
			$('#new-smon-headers-response').hide();
		}
	});
	$( "#smon_http_check_body_type" ).on('selectmenuchange',function() {
		if ($('#smon_http_check_body_type').val() == 'keyword') {
			$('.smon_http_check_body_type_keyword').show();
			$('.smon_http_check_body_type_json').hide();
		} else if ($('#smon_http_check_body_type').val() == 'json') {
			$('.smon_http_check_body_type_keyword').hide();
			$('.smon_http_check_body_type_json').show();
		} else {
			$('.smon_http_check_body_type_keyword').hide();
			$('.smon_http_check_body_type_json').hide();
		}
	});
});
function sort_by_status() {
	$('<div id="err_services" style="clear: both;"></div>').appendTo('.main');
	$('<div id="good_services" style="clear: both;"></div>').appendTo('.main');
	$('<div id="dis_services" style="clear: both;"></div>').appendTo('.main');
	$(".good").prependTo("#good_services");
	$(".err").prependTo("#err_services");
	$(".dis").prependTo("#dis_services");
	$('.group').remove();
	$('.group_name').detach();
	window.history.pushState("RMON Dashboard", "RMON Dashboard", "?sort=by_status");
}
function showSmon(action) {
	if (action === 'not_sort') {
		window.history.pushState("RMON Dashboard", "RMON Dashboard", "/rmon/dashboard");
	}
	window.location.reload();
}
function addNewSmonServer(dialog_id, smon_id=0, edit=false) {
	if (CheckEditor.isBlocked() || !CheckEditor.validate()) return false;
	const check_type = $('#check_type').val();
	const statusList = check_type === 'http' ? window.tagify.value.map(tag => tag.value) : [];
	let enable = 0;
	if ($('#new-smon-enable').is(':checked')) {
		enable = '1';
	}
	let ignore_ssl_error = 0;
	if ($('#new-smon-ignore_ssl_error').is(':checked')) {
		ignore_ssl_error = '1';
	}
	let accept_cookies = 0;
	if ($('#new-smon-accept_cookies').is(':checked')) {
		accept_cookies = '1';
	}
	let use_kernel_timestamp = 0;
	if ($('#new-smon-use_kernel_timestamp').is(':checked')) {
		use_kernel_timestamp = '1';
	}
	let entities = [];
	$("#checked-entities > div").each((index, elem) => {
		let entity_id = elem.id.split('-')[1]
		entities.push(entity_id);
	});
	let auth = null;
	if ($('#smon_http_check_auth_method').val() === 'basic') {
		auth = {'basic':{
				'username': $('#new-smon-basic_username').val(),
				'password': $('#new-smon-basic_password').val(),
			}
		}
	} else if ($('#smon_http_check_auth_method').val() === 'mtls') {
		auth = {'mtls':{
				'key': $('#new-smon-mtls_key').val(),
				'cert': $('#new-smon-mtls_cert').val(),
				'ca': $('#new-smon-mtls_ca').val(),
			}
		}
	}
	let body = null;
	let body_json = null;
	if ($("#smon_http_check_body_type").val() === "keyword") {
		body = $('#new-smon-body-keyword').val()
	} else if ($("#smon_http_check_body_type").val() === "json") {
		body_json = {
			'path': $('#new-smon-body-json-path').val(),
			'value': $('#new-smon-body-json-value').val()
		}
	}
	let proxy = null;
	if ($("#smon_http_check_proxy_method").val() != "0") {
		proxy = {
			'type': $('#smon_http_check_proxy_method').val(),
			'host': $('#new-smon-http_proxy_host').val(),
			'port': $('#new-smon-http_proxy_port').val(),
			'username': $('#new-smon-http_proxy_username').val(),
			'password': $('#new-smon-http_proxy_password').val(),
		}
	}
	let headers_response = null;
	if ($("#smon_http_check_headers_response_type").val() != "0") {
		headers_response = {
			'required_response_headers': $('#new-smon-header-response-required').val(),
			'forbidden_headers': $('#new-smon-header-response-forbidden').val(),
		}
	}
	let resole_to_ip = null;
	if ($('#new-smon-resole_to_ip').val() != "") {
		resole_to_ip = $('#new-smon-resole_to_ip').val();
	}
	let jsonData = {
		'name': $('#new-smon-name').val(),
		'ip': $('#new-smon-ip').val(),
		'port': $('#new-smon-port').val(),
		'resolver': $('#new-smon-resolver-server').val(),
		'record_type': $('#new-smon-dns_record_type').val(),
		'username': $('#new-smon-username').val(),
		'password': $('#new-smon-password').val(),
		'vhost': $('#new-smon-vhost').val(),
		'enabled': enable,
		'url': $('#new-smon-url').val(),
		'resole_to_ip': resole_to_ip,
		'body': body,
		'body_json': body_json,
		'check_group': $('#new-smon-group').val(),
		'description': $('#new-smon-description').val(),
		'telegram_channel_id': $('#new-smon-telegram').val(),
		'slack_channel_id': $('#new-smon-slack').val(),
		'pd_channel_id': $('#new-smon-pd').val(),
		'mm_channel_id': $('#new-smon-mm').val(),
		'incidentrelay_channel_id': $('#new-smon-incidentrelay').val(),
		'email_channel_id': $('#new-smon-email').val(),
		'packet_size': $('#new-smon-packet_size').val(),
		'count_packets': $('#new-smon-count_packets').val(),
		'use_kernel_timestamp': use_kernel_timestamp,
		'method': $('#new-smon-method').val(),
		'interval': $('#new-smon-interval').val(),
		'entities': entities,
		'place': $('#new-smon-place option:selected').val(),
		'body_req': $('#new-smon-body-req').val(),
		'header_req': $('#new-smon-header-req').val(),
		'accepted_status_codes': statusList,
		'check_timeout': $('#new-smon-timeout').val(),
		'ignore_ssl_error': ignore_ssl_error,
		'accept_cookies': accept_cookies,
		'retries': $('#new-smon-retries').val(),
		'redirects': $('#new-smon-redirects').val(),
		'runbook': $('#new-smon-runbook').val(),
		'priority': $('#new-smon-priority').val(),
		'expiration': $('#new-smon-expiration').val(),
		'threshold_timeout': $('#new-smon-threshold_timeout').val(),
		'auth': auth,
		'proxy': proxy,
		'headers_response': headers_response,
		'http_version': parseInt($('#new-smon-http_version').val()),
	}
	let method = "post";
	let api_url = api_v_prefix + '/rmon/check/' + check_type;
	if (edit) {
		method = "put";
		api_url = api_v_prefix + '/rmon/check/' + check_type + "/" + smon_id;
	}
    CheckEditor.setBusy(true);
    return $.ajax({
        url: api_url, data: JSON.stringify(jsonData),
        contentType: "application/json; charset=utf-8", type: method,
        error: function () { CheckEditor.showError(CheckEditor.text('save_error')); },
        success: function (data) {
            if (data.status === 'failed') {
                CheckEditor.showError(CheckEditor.text('save_error'));
            } else {
                CheckEditor.setBusy(false);
                getSmonCheck(edit ? smon_id : data.id, check_types[check_type], dialog_id, !edit);
            }
        }
    });
}
function confirmDeleteSmon(id, check_type) {
	$( "#dialog-confirm" ).dialog({
		resizable: false,
		height: "auto",
		width: 400,
		modal: true,
		title: delete_word+" " +$('#smon-name-'+id).text() + "?",
		buttons: [{
			text: delete_word,
			click: function () {
				$(this).dialog("close");
				removeSmon(id, check_type);
			}
		}, {
			text: cancel_word,
			click: function() {
				$( this ).dialog( "close" );
			}
		}]
	});
}
function removeSmon(smon_id, check_type) {
	$("#smon-" + smon_id).css("background-color", "#f2dede");
	$.ajax({
		url: api_v_prefix + "/rmon/check/" + check_type + "/" + smon_id,
		type: "DELETE",
		contentType: "application/json; charset=utf-8",
		success: function (data, statusText, xhr) {
			if (xhr.status === 204) {
				$("#smon-" + smon_id).remove();
			} else {
				if (data.status === 'failed') {
					toastr.error(data);
				}
			}
		}
	});
}
function openSmonDialog(check_type, smon_id=0, edit=false) {
    if (!edit && !checkChecksLimit()) return false;
    CheckEditor.reset(check_type);
    $('#check_type, #new-smon-place').prop('disabled', edit);
    CheckEditor.refresh();
    const dialog = $('#smon-add-table').dialog({
        autoOpen: false, resizable: false, height: "auto", width: 940, modal: true,
        title: CheckEditor.text(edit ? 'edit' : 'create'),
        show: {effect: "fade", duration: 150}, hide: {effect: "fade", duration: 150},
        beforeClose: function () { return !CheckEditor.isBusy(); },
        open: function () {
            const input = document.querySelector('#new-smon-status-code');
            if (input && !input._tagify) {
                const codes = ["1**", "2**", "3**", "4**", "5**", "100-199", "200-299", "300-399", "400-499", "500-599"];
                for (let i = 100; i <= 599; i++) codes.push(String(i));
                window.tagify = new Tagify(input, {whitelist: codes, duplicates: false,
                    // The API accepts arbitrary valid ranges such as 300-304.
                    enforceWhitelist: false, pattern: /^(?:[1-5][0-9]{2}|[1-5]\*\*|[1-5][0-9]{2}-[1-5][0-9]{2})$/,
                    dropdown: {enabled: 1, maxItems: 15}});
            }
            if (!edit) window.tagify.addTags(["200"]);
            CheckEditor.refresh();
            CheckEditor.showStep(0);
        },
        close: function () { if (window.tagify) window.tagify.removeAllTags(); },
        buttons: [
            {id: 'check-editor-back', text: CheckEditor.text('back'), click: CheckEditor.back},
            {id: 'check-editor-next', text: CheckEditor.text('next'), click: CheckEditor.next},
            {id: 'check-editor-submit', text: CheckEditor.text(edit ? 'save' : 'create'),
                click: function () { addNewSmonServer(this, smon_id, edit); }},
            {id: 'check-editor-cancel', text: cancel_word, click: function () { $(this).dialog('close'); }}
        ]
    });
    dialog.dialog('open');
    if (!edit && !window.tagify.value.length) window.tagify.addTags(["200"]);
    CheckEditor.showStep(0);
    return dialog;
}
function getCheckSettings(smon_id, check_type, onLoaded) {
    CheckEditor.setBusy(true, true);
    return $.ajax({
        url: api_v_prefix + "/rmon/check/" + check_type + "/" + smon_id,
        type: "get", dataType: "json", timeout: 15000,
        error: function () { CheckEditor.showError(CheckEditor.text('load_error'), true); },
        success: function (data) {
            try {
                CheckEditor.populate(data);
                CheckEditor.setBusy(false);
                if (onLoaded) onLoaded();
            } catch (_) { CheckEditor.showError(CheckEditor.text('load_error'), true); }
        }
    });
}
function editSmon(smon_id, check_type) {
    openSmonDialog(check_type, smon_id, true);
    return getCheckSettings(smon_id, check_type);
}
function cloneSmon(id, check_type) {
    if (!openSmonDialog(check_type)) return false;
    return getCheckSettings(id, check_type, function () {
        $('#new-smon-name').val($('#new-smon-name').val() + ' (' + CheckEditor.text('copy') + ')');
        CheckEditor.summary();
    });
}
function getSmonCheck(smon_id, check_id, dialog_id, new_check=false) {
	$.ajax({
		url: "/rmon/check/" + smon_id + "/" + check_id,
		type: "get",
		success: function (data) {
			if (new_check) {
				if (!$("#dashboards").length) {
					location.reload();
				}
				$('#dashboards').prepend(data);
			} else {
				$('#smon-' + smon_id).replaceWith(data);
			}
			$.getScript("/static/js/fontawesome.min.js");
		}
	});
	$(dialog_id).dialog("close");
}
function check_and_clear_check_type(check_type) {
    CheckEditor.setType(check_type);
}
function show_smon_history_statuses(check_id, id_for_history_replace) {
	$.ajax({
		url: api_v_prefix + "/rmon/check/" + check_id + "/statuses",
		contentType: "application/json; charset=utf-8",
		success: function (data) {
			let statuses = '';
			for (let status of data.reverse()) {
				let add_class = 'serverUp';
				if (status.status === 0 || status.status === 7 || status.status === 8) {
					add_class = 'serverDown';
				} else if (status.status === 5 || status.status === 6|| status.status === 9) {
					add_class = 'serverWarn';
				}
				statuses += '<div class="smon_server_statuses ' + add_class + '" title="" data-help="' + status.date + ' ' + status.error + '"></div>';
			}
			$(id_for_history_replace).html(statuses);
			$("[title]").tooltip({
				"content": function () {
					return $(this).attr("data-help");
				},
				show: {"delay": 1000}
			});
			$.getScript("/static/js/fontawesome.min.js");
		}
	});
}
function checkChecksLimit() {
	let return_value = false;
	$.ajax({
		url: '/rmon/checks/count',
		async: false,
		success: function (data) {
			data = data.replace(/\s+/g, ' ');
			if (data.indexOf('error:') != '-1') {
				toastr.error(data);
			} else {
				return_value = true;
			}
		}
	});
	return return_value;
}
var charts = []
function showSmonGroup(group_id) {
	$('#show-smon-group-' + group_id).css('display', 'none');
	$('#hide-smon-group-' + group_id).css('display', 'block');
	$('#smon-group-' + group_id).show();
	localStorage.setItem('show-smon-group-' + group_id, '1');
}
function hideSmonGroup(group_id) {
	$('#show-smon-group-' + group_id).css('display', 'block');
	$('#hide-smon-group-' + group_id).css('display', 'none');
	$('#smon-group-' + group_id).hide();
	localStorage.removeItem('show-smon-group-' + group_id, '1');
}
function isSmonGroupShowed(group_id) {
	if(localStorage.getItem('show-smon-group-' + group_id) === '1') {
		showSmonGroup(group_id);
	}
}
function getSmonHistoryCheckData(check_id, check_type) {
	$.ajax({
		url: api_v_prefix + "/rmon/check/" + check_type + "/" + check_id + "/metrics?step=1m&start=30m&end=now",
		success: function (result) {
			let labels = result.chartData.labels;
			if (check_type === 'http') {
				renderSMONChartHttp(result, labels, check_id, check_types[check_type]);
			} else if (check_type === 'smtp') {
				renderSMONChartSmtp(result, labels, check_id, check_types[check_type]);
			} else if (check_type === 'ping') {
				renderSMONChartPing(result, labels, check_id, check_types[check_type]);
			} else {
				let data = [];
				data.push(result.chartData.response_time);
				renderSMONChart(data[0], labels, check_id, check_types[check_type]);
			}
		}
	});
}
function renderSMONChartHttp(result, labels, check_id, check_type_id) {
    const ctx = document.getElementById('metrics_' + check_id);

    // Преобразование данных в массивы
    const labelArray = labels.split(',');
    const name_lookup = result.chartData.namelookup.split(',');
    const connect = result.chartData.connect.split(',');
    const app_connect = result.chartData.appconnect.split(',');
    const pre_transfer = result.chartData.pretransfer.split(',');
    const redirect = result.chartData.redirect.split(',');
    const start_transfer = result.chartData.starttransfer.split(',');
    const download = result.chartData.download.split(',');
    const response_time = result.chartData.response_time.split(',');

    // Удаление последнего пустого элемента в каждом массиве
    labelArray.pop();
    name_lookup.pop();
    connect.pop();
    app_connect.pop();
    pre_transfer.pop();
    redirect.pop();
    start_transfer.pop();
    download.pop();
    response_time.pop();

    // Создание объекта dataset
    const dataset = [{
        label: resp_time_word + ' (ms)',
        data: response_time,
        borderColor: 'rgba(41, 115, 147, 0.5)',
        backgroundColor: 'rgba(49, 175, 225, 0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
    }, {
		label: 'Name lookup (ms)',
        data: name_lookup,
        borderColor: 'rgba(41,147,78,0.5)',
        backgroundColor: 'rgba(49,225,84,0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
	}, {
		label: 'Connect (ms)',
        data: connect,
        borderColor: 'rgba(140,147,41,0.5)',
        backgroundColor: 'rgba(225,210,49,0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
	}, {
		label: 'App connect (ms)',
        data: app_connect,
        borderColor: 'rgba(147,126,41,0.5)',
        backgroundColor: 'rgba(225,175,49,0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
	}, {
		label: 'Pre transfer (ms)',
        data: pre_transfer,
        borderColor: 'rgba(147,101,41,0.5)',
        backgroundColor: 'rgba(225,143,49,0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
	}, {
		label: 'Redirect (ms)',
        data: redirect,
        borderColor: 'rgba(147,89,41,0.5)',
        backgroundColor: 'rgba(225,122,49,0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
	}, {
		label: 'Start transfer (ms)',
        data: start_transfer,
        borderColor: 'rgba(147,73,41,0.5)',
        backgroundColor: 'rgba(225,96,49,0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
	}, {
		label: 'Download (ms)',
        data: download,
        borderColor: 'rgba(140,41,147,0.5)',
        backgroundColor: 'rgba(134,49,225,0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
	}];

    const config = {
        type: 'line',
        data: {
            labels: labelArray,
            datasets: dataset
        },
        options: {
            animation: true,
			maintainAspectRatio: false,
			plugins: {
				title: {
					display: true,
					font: { size: 15 },
					padding: { top: 10 }
				},
				legend: {
					display: true,
					position: 'bottom',
					align: 'left',
					labels: {
						color: 'rgb(255, 99, 132)',
						font: { size: 10, family: 'BlinkMacSystemFont' },
						boxWidth: 13,
						// padding: 5
					},
				}
			},
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Time'
                    },
                    ticks: {
                        source: 'data',
                        autoSkip: true,
                        autoSkipPadding: 45,
                        maxRotation: 0
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: resp_time_word + ' (ms)'
                    },
                    ticks: {
                        font: {
                            size: 10
                        }
                    }
                }
            }
        }
    };

    const myChart = new Chart(ctx, config);
	stream_chart(myChart, check_id, check_type_id);
}
function renderSMONChartSmtp(result, labels, check_id, check_type_id) {
    const ctx = document.getElementById('metrics_' + check_id);
    // Преобразование данных в массивы
    const labelArray = labels.split(',');
    const name_lookup = result.chartData.name_lookup.split(',');
    const connect = result.chartData.connect.split(',');
    const app_connect = result.chartData.app_connect.split(',');
    const response_time = result.chartData.response_time.split(',');

    // Удаление последнего пустого элемента в каждом массиве
    labelArray.pop();
    name_lookup.pop();
    connect.pop();
    app_connect.pop();
    response_time.pop();

    // Создание объекта dataset
    const dataset = [{
        label: resp_time_word + ' (ms)',
        data: response_time,
        borderColor: 'rgba(41, 115, 147, 0.5)',
        backgroundColor: 'rgba(49, 175, 225, 0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
    }, {
		label: 'Name lookup (ms)',
        data: name_lookup,
        borderColor: 'rgba(41,147,78,0.5)',
        backgroundColor: 'rgba(49,225,84,0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
	}, {
		label: 'Connect (ms)',
        data: connect,
        borderColor: 'rgba(140,147,41,0.5)',
        backgroundColor: 'rgba(225,210,49,0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
	}, {
		label: 'App connect (ms)',
        data: app_connect,
        borderColor: 'rgba(147,126,41,0.5)',
        backgroundColor: 'rgba(225,175,49,0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
	}];

    const config = {
        type: 'line',
        data: {
            labels: labelArray,
            datasets: dataset
        },
        options: {
            animation: true,
			maintainAspectRatio: false,
			plugins: {
				title: {
					display: true,
					font: { size: 15 },
					padding: { top: 10 }
				},
				legend: {
					display: true,
					position: 'bottom',
					align: 'left',
					labels: {
						color: 'rgb(255, 99, 132)',
						font: { size: 10, family: 'BlinkMacSystemFont' },
						boxWidth: 13,
						// padding: 5
					},
				}
			},
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Time'
                    },
                    ticks: {
                        source: 'data',
                        autoSkip: true,
                        autoSkipPadding: 45,
                        maxRotation: 0
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: resp_time_word + ' (ms)'
                    },
                    ticks: {
                        font: {
                            size: 10
                        }
                    }
                }
            }
        }
    };

    const myChart = new Chart(ctx, config);
	stream_chart(myChart, check_id, check_type_id);
}
function renderSMONChartPing(result, labels, check_id, check_type_id) {
    const ctx = document.getElementById('metrics_' + check_id);
    // Преобразование данных в массивы
    const labelArray = labels.split(',');
    const avg_resp_time = result.chartData.avg_resp_time.split(',');
    const max_resp_time = result.chartData.max_resp_time.split(',');
    const min_resp_time = result.chartData.min_resp_time.split(',');
    const packet_loss_percent = result.chartData.packet_loss_percent.split(',');
    const response_time = result.chartData.response_time.split(',');

    // Удаление последнего пустого элемента в каждом массиве
    labelArray.pop();
    avg_resp_time.pop();
    max_resp_time.pop();
    min_resp_time.pop();
    packet_loss_percent.pop();
    response_time.pop();

    // Создание объекта dataset
    const dataset = [{
        label: resp_time_word + ' (s)',
        data: response_time,
        borderColor: 'rgba(41, 115, 147, 0.5)',
        backgroundColor: 'rgba(49, 175, 225, 0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
    }, {
		label: 'Avg response time (s)',
        data: avg_resp_time,
        borderColor: 'rgba(41,147,78,0.5)',
        backgroundColor: 'rgba(49,225,84,0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
	}, {
		label: 'Max response time (s)',
        data: max_resp_time,
        borderColor: 'rgba(140,147,41,0.5)',
        backgroundColor: 'rgba(225,210,49,0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
	}, {
		label: 'Min response time (s)',
        data: min_resp_time,
        borderColor: 'rgba(147,126,41,0.5)',
        backgroundColor: 'rgba(225,175,49,0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
	}, {
		label: 'Packet loss (%)',
        data: packet_loss_percent,
        borderColor: 'rgba(147,41,41,0.5)',
        backgroundColor: 'rgba(225,49,49,0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
	}];

    const config = {
        type: 'line',
        data: {
            labels: labelArray,
            datasets: dataset
        },
        options: {
            animation: true,
			maintainAspectRatio: false,
			plugins: {
				title: {
					display: true,
					font: { size: 15 },
					padding: { top: 10 }
				},
				legend: {
					display: true,
					position: 'bottom',
					align: 'left',
					labels: {
						color: 'rgb(255, 99, 132)',
						font: { size: 10, family: 'BlinkMacSystemFont' },
						boxWidth: 13,
						// padding: 5
					},
				}
			},
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Time'
                    },
                    ticks: {
                        source: 'data',
                        autoSkip: true,
                        autoSkipPadding: 45,
                        maxRotation: 0
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: resp_time_word + ' (ms)'
                    },
                    ticks: {
                        font: {
                            size: 10
                        }
                    }
                }
            }
        }
    };

    const myChart = new Chart(ctx, config);
	stream_chart(myChart, check_id, check_type_id);
}

function renderSMONChart(data, labels, check_id, check_type_id) {
    const ctx = document.getElementById('metrics_' + check_id);

    // Преобразование данных в массивы
    const labelArray = labels.split(',');
    const dataArray = data.split(',');

    // Удаление последнего пустого элемента в каждом массиве
    labelArray.pop();
    dataArray.pop();

    // Создание объекта dataset
    const dataset = {
        label: resp_time_word + ' (ms)',
        data: dataArray,
        borderColor: 'rgba(41, 115, 147, 0.5)',
        backgroundColor: 'rgba(49, 175, 225, 0.5)',
        tension: 0.4,
        pointRadius: 3,
        borderWidth: 1,
        fill: true
    };

    const config = {
        type: 'line',
        data: {
            labels: labelArray,
            datasets: [dataset]
        },
        options: {
            animation: true,
			maintainAspectRatio: false,
			plugins: {
				title: {
					display: true,
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
                    title: {
                        display: true,
                        text: 'Time'
                    },
                    ticks: {
                        source: 'data',
                        autoSkip: true,
                        autoSkipPadding: 45,
                        maxRotation: 0
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: resp_time_word + ' (ms)'
                    },
                    ticks: {
                        font: {
                            size: 10
                        }
                    }
                }
            }
        }
    };

    const myChart = new Chart(ctx, config);
	stream_chart(myChart, check_id, check_type_id);
}
function stream_chart(chart_id, check_id, check_type_id) {
    const source = new EventSource(`/rmon/history/metrics/stream/${check_id}/${check_type_id}`);
	let prev_date = '';
    source.onmessage = function (event) {
        const data = JSON.parse(event.data);
		if (prev_date != data.time) {
			if (chart_id.data.labels.length >= 40) {
				chart_id.data.labels.shift();
				chart_id.data.datasets[0].data.shift();
				if (check_type_id === '2' || check_type_id === '3') {
					chart_id.data.datasets[1].data.shift();
					chart_id.data.datasets[2].data.shift();
					chart_id.data.datasets[3].data.shift();
					if (check_type_id === '2') {
						chart_id.data.datasets[4].data.shift();
						chart_id.data.datasets[5].data.shift();
						chart_id.data.datasets[6].data.shift();
					}
				} else if (check_type_id === '4') {
					chart_id.data.datasets[1].data.shift();
					chart_id.data.datasets[2].data.shift();
					chart_id.data.datasets[3].data.shift();
					chart_id.data.datasets[4].data.shift();
				}
			}
			chart_id.data.labels.push(data.time);
			chart_id.data.datasets[0].data.push(data.response_time);
			if (check_type_id === 2 || check_type_id === 3) {
				chart_id.data.datasets[1].data.push(data.name_lookup);
				chart_id.data.datasets[2].data.push(data.connect);
				chart_id.data.datasets[3].data.push(data.app_connect);
				if (check_type_id === 2) {
					chart_id.data.datasets[4].data.push(data.pre_transfer);
					chart_id.data.datasets[5].data.push(data.redirect);
					chart_id.data.datasets[6].data.push(data.m_download);
				}
			} else if (check_type_id === 4) {
				chart_id.data.datasets[1].data.push(data.avg_resp_time)
				chart_id.data.datasets[2].data.push(data.max_resp_time)
				chart_id.data.datasets[3].data.push(data.min_resp_time)
				chart_id.data.datasets[4].data.push(data.packet_loss_percent)
			}
			if (data.status === 0) {
				chart_id.data.datasets[0].fillColor = 'rgb(239,5,59)';
			}
			chart_id.update();
			update_cur_statues(check_id, data);
		}
		prev_date = data.time;
    }
}
function update_cur_statues(check_id, data) {
	if (data.status === "4") {
		return false;
	}
	let last_resp_time = data.response_time;
	if (last_resp_time.length === 0) {
		last_resp_time = 'N/A';
	} else {
		last_resp_time = last_resp_time + 's'
	}
	if ($('#translate').attr('data-history_of')) {
		let title_text = `${$('#translate').attr('data-history_of')} ${data.name.replaceAll("'", "")}`
		$('title').text(title_text);
		$('h2').text(title_text);
	}
	$('#last_resp_time').html(last_resp_time);
	$('#uptime').html(data.uptime + '%');
	$('#avg_res_time').html(data.avg_res_time + 's');
	$('#interval').text(data.interval);
	$('#updated_at').text(data.updated_at);
	$('#ssl_expire_date').text(data.ssl_expire_date);
	updateCurrentStatus(check_id, data);
}
function showRoute(checkId) {
	$.ajax({
		url: api_v_prefix + '/rmon/check/' + checkId + '/route',
		contentType: "application/json; charset=utf-8",
		success: function (data) {
			if (data.status === 'failed') {
				toastr.error(data.error);
				return;
			}
			let html_data = '';
			let total_hops = 0;
			let add_class = ''
			data = data.report.hubs
			for (let i = 0; i < data.length; i++) {
				add_class = '';
				if (data[i].host === '???') {
					add_class = 'color: red;'
				}
				html_data += `<div style="${add_class}">${data[i].count} - <b>${data[i].host}</b> - Avg: ${data[i].Avg}</div>`;
				total_hops += 1;
			}
			html_data += `<br/><div><b>Total hops: ${total_hops}</b></div>`;
			$('#show_route').html(html_data);
			$("#route").dialog({
				resizable: false,
				height: "auto",
				width: 400,
				modal: true,
				title: "Route for check",
				buttons: [{
					text: cancel_word,
					click: function () {
						$(this).dialog("close");
					}
				}]
			});
		}
	});
}
