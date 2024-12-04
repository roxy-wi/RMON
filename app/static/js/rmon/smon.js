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
	let valid = true;
	let check_type = $('#check_type').val();
	let allFields = '';
	if (check_type === 'tcp') {
		allFields = $([]).add($('#new-smon-ip')).add($('#new-smon-port')).add($('#new-smon-name')).add($('#new-smon-interval')).add($('#new-smon-timeout'))
		allFields.removeClass("ui-state-error");
		valid = valid && checkLength($('#new-smon-port'), "Port", 1);
		valid = valid && checkLength($('#new-smon-ip'), "Hostname", 1);
	}
	if (check_type === 'http') {
		allFields = $([]).add($('#new-smon-url')).add($('#new-smon-name')).add($('#new-smon-interval')).add($('#new-smon-timeout'))
		allFields.removeClass("ui-state-error");
		valid = valid && checkLength($('#new-smon-url'), "URL", 1);
	}
	if (check_type === 'ping') {
		allFields = $([]).add($('#new-smon-ip')).add($('#new-smon-name')).add($('#new-smon-packet_size')).add($('#new-smon-interval')).add($('#new-smon-timeout'))
		allFields.removeClass("ui-state-error");
		valid = valid && checkLength($('#new-smon-ip'), "Hostname", 1);
	}
	if (check_type === 'dns') {
		allFields = $([]).add($('#new-smon-ip')).add($('#new-smon-port')).add($('#new-smon-name')).add($('#new-smon-resolver-server')).add($('#new-smon-interval')).add($('#new-smon-timeout'))
		allFields.removeClass("ui-state-error");
		valid = valid && checkLength($('#new-smon-port'), "Port", 1);
		valid = valid && checkLength($('#new-smon-resolver-server'), "Resolver server", 1);
		valid = valid && checkLength($('#new-smon-ip'), "Hostname", 1);
	}
	if (check_type === 'smtp') {
		allFields = $([]).add($('#new-smon-ip')).add($('#new-smon-port')).add($('#new-smon-name')).add($('#new-smon-username')).add($('#new-smon-password')).add($('#new-smon-interval')).add($('#new-smon-timeout'))
		allFields.removeClass("ui-state-error");
		valid = valid && checkLength($('#new-smon-port'), "Port", 1);
		valid = valid && checkLength($('#new-smon-username'), "Username", 1);
		valid = valid && checkLength($('#new-smon-password'), "Password", 1);
		valid = valid && checkLength($('#new-smon-ip'), "Hostname", 1);
	}
	if (check_type === 'rabbit') {
		allFields = $([]).add($('#new-smon-ip')).add($('#new-smon-port')).add($('#new-smon-name')).add($('#new-smon-username')).add($('#new-smon-password')).add($('#new-smon-vhost')).add($('#new-smon-interval')).add($('#new-smon-timeout'))
		allFields.removeClass("ui-state-error");
		valid = valid && checkLength($('#new-smon-port'), "Port", 1);
		valid = valid && checkLength($('#new-smon-username'), "Username", 1);
		valid = valid && checkLength($('#new-smon-password'), "Password", 1);
		valid = valid && checkLength($('#new-smon-vhost'), "VHost", 1);
		valid = valid && checkLength($('#new-smon-ip'), "Hostname", 1);
	}
	valid = valid && checkLength($('#new-smon-name'), "Name", 1);
	valid = valid && checkLength($('#new-smon-interval'), "Check interval", 1);
	valid = valid && checkLength($('#new-smon-timeout'), "Timeout", 1);
	let enable = 0;
	if ($('#new-smon-enable').is(':checked')) {
		enable = '1';
	}
	let ignore_ssl_error = 0;
	if ($('#new-smon-ignore_ssl_error').is(':checked')) {
		ignore_ssl_error = '1';
	}
	let entities = [];
	$("#checked-entities > div").each((index, elem) => {
		let entity_id = elem.id.split('-')[1]
		entities.push(entity_id);
	});
	if ($('#new-smon-place option:selected').val() !== 'all') {
		if (entities.length === 0) {
			toastr.warning('Check must have at least one entity');
			return false;
		}
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
		'body': $('#new-smon-body').val(),
		'check_group': $('#new-smon-group').val(),
		'description': $('#new-smon-description').val(),
		'telegram_channel_id': $('#new-smon-telegram').val(),
		'slack_channel_id': $('#new-smon-slack').val(),
		'pd_channel_id': $('#new-smon-pd').val(),
		'mm_channel_id': $('#new-smon-mm').val(),
		'packet_size': $('#new-smon-packet_size').val(),
		'method': $('#new-smon-method').val(),
		'interval': $('#new-smon-interval').val(),
		'entities': entities,
		'place': $('#new-smon-place option:selected').val(),
		'body_req': $('#new-smon-body-req').val(),
		'header_req': $('#new-smon-header-req').val(),
		'accepted_status_codes': $('#new-smon-status-code').val(),
		'check_timeout': $('#new-smon-timeout').val(),
		'ignore_ssl_error': ignore_ssl_error
	}
	let method = "post";
	let api_url = api_v_prefix + '/rmon/check/' + check_type;
	if (edit) {
		method = "put";
		api_url = api_v_prefix + '/rmon/check/' + check_type + "/" + smon_id;
	}
	if (valid) {
		$.ajax( {
			url: api_url,
            data: JSON.stringify(jsonData),
            contentType: "application/json; charset=utf-8",
			type: method,
			success: function( data ) {
				if (data.status === 'failed') {
					toastr.error(data);
				} else {
					let check_id = check_types[check_type];
					if (edit) {
						getSmonCheck(smon_id, check_id, dialog_id);
					} else {
						getSmonCheck(data.id, check_id, dialog_id, true);
					}
				}
			}
		} );
	}
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
	check_and_clear_check_type(check_type);
	$('#checked-entities').empty();
	$('#all-entities').empty();
	$('#new-smon-place').val('all').change();
	$('#new-smon-place').selectmenu('refresh');
	let smon_add_tabel_title = $("#smon-add-table-overview").attr('title');
	if (edit) {
		add_word = $('#translate').attr('data-edit');
		smon_add_tabel_title = $("#smon-add-table-overview").attr('data-edit');
		$('#check_type').attr('disabled', 'disabled');
		$('#new-smon-place').attr('disabled', 'disabled');
		$('#check_type').selectmenu("refresh");
		$('#new-smon-place').selectmenu("refresh");
	} else {
		if (!checkChecksLimit()) {
			return false;
		}
		$('#check_type').removeAttr('disabled');
		$('#new-smon-place').removeAttr('disabled');
		$('#check_type').selectmenu("refresh");
		$('#new-smon-place').selectmenu("refresh");
		$('#new-smon-name').val('');
	}
	let addSmonServer = $("#smon-add-table").dialog({
		autoOpen: false,
		resizable: false,
		height: "auto",
		width: 600,
		modal: true,
		title: smon_add_tabel_title,
		show: {
			effect: "fade",
			duration: 200
		},
		hide: {
			effect: "fade",
			duration: 200
		},
		buttons: [{
			text: add_word,
			click: function () {
				if (edit) {
					addNewSmonServer(this, smon_id, check_type);
				} else {
					addNewSmonServer(this);
				}
			}
		}, {
			text: cancel_word,
			click: function () {
				$(this).dialog("close");
				clearTips();
			}
		}]
	});
	addSmonServer.dialog('open');
}
function getCheckSettings(smon_id, check_type) {
	$.ajax({
		url: api_v_prefix + "/rmon/check/" + check_type + "/" + smon_id,
		type: "get",
		async: false,
		dataType: "json",
		success: function (data) {
			$('#new-smon-name').val(data['checks'][0]['smon_id']['name'].replaceAll("'", ""));
			$('#new-smon-ip').val(data['checks'][0]['ip']);
			$('#new-smon-port').val(data['checks'][0]['port']);
			$('#new-smon-resolver-server').val(data['checks'][0]['resolver']);
			$('#new-smon-dns_record_typer').val(data['checks'][0]['record_type']);
			$('#new-smon-url').val(data['checks'][0]['url']);
			$('#new-smon-description').val(data['checks'][0]['smon_id']['description'].replaceAll("'", ""))
			$('#new-smon-packet_size').val(data['checks'][0]['packet_size']);
			$('#new-smon-interval').val(data['checks'][0]['interval']);
			$('#new-smon-username').val(data['checks'][0]['username']);
			$('#new-smon-password').val(data['checks'][0]['password']);
			if (data['check_group']) {
				$('#new-smon-group').val(data['check_group'].replaceAll("'", ""));
			}
			if (data['checks'][0]['smon_id']['check_timeout']) {
				$('#new-smon-timeout').val(data['checks'][0]['smon_id']['check_timeout']);
			}
			try {
				$('#new-smon-body').val(data['checks'][0]['body'].replaceAll("'", ""));
			} catch (e) {
				$('#new-smon-body').val(data['checks'][0]['body']);
			}
			try {
				$('#new-smon-body-req').val(data['checks'][0]['body_req'].replaceAll("'", ""));
			} catch (e) {
				$('#new-smon-body-req').val(data['checks'][0]['body_req']);
			}
			try {
				$('#new-smon-header-req').val(data['checks'][0]['header_req'].replaceAll("'", ""));
			} catch (e) {
				$('#new-smon-header-req').val(data['checks'][0]['header_req']);
			}
			$('#new-smon-status-code').val(data['checks'][0]['accepted_status_codes']);
			$('#new-smon-place').val(data['place']).change();
			$('#new-smon-telegram').selectmenu("refresh");
			$('#new-smon-place').trigger('selectmenuchange');
			$('#new-smon-slack').selectmenu("refresh");
			if (data['place'] != 'all') {
				for (let entity_id of data['entities']) {
					getEntityJson(entity_id, data['place']);
				}
			}
			if (data['checks'][0]['smon_id']['mm_channel_id']) {
				$('#new-smon-mm').val(data['checks'][0]['smon_id']['mm_channel_id']).change();
				$('#new-smon-mm').selectmenu("refresh");
			}
			if (data['checks'][0]['smon_id']['pd_channel_id']) {
				$('#new-smon-pd').val(data['checks'][0]['smon_id']['pd_channel_id']).change();
				$('#new-smon-mm').selectmenu("refresh");
			}
			if (data['checks'][0]['smon_id']['telegram_channel_id']) {
				$('#new-smon-telegram').val(data['checks'][0]['smon_id']['telegram_channel_id']).change();
				$('#new-smon-mm').selectmenu("refresh");
			}
			if (data['checks'][0]['smon_id']['slack_channel_id']) {
				$('#new-smon-slack').val(data['checks'][0]['smon_id']['slack_channel_id']).change();
				$('#new-smon-mm').selectmenu("refresh");
			}
			if (data['checks'][0]['method']) {
				$('#new-smon-method').val(data['checks'][0]['method']).change();
				$('#new-smon-method').selectmenu("refresh");
			}
			$('select').selectmenu("refresh");
			if (data['checks'][0]['smon_id']['enabled']) {
				$('#new-smon-enable').prop('checked', true)
			} else {
				$('#new-smon-enable').prop('checked', false)
			}
			if (data['checks'][0]['ignore_ssl_error']) {
				$('#new-smon-ignore_ssl_error').prop('checked', true)
			} else {
				$('#new-smon-ignore_ssl_error').prop('checked', false)
			}
			$('#new-smon-enable').checkboxradio("refresh");
			$('#new-smon-ignore_ssl_error').checkboxradio("refresh");
		}
	});
}
function editSmon(smon_id, check_type) {
	check_and_clear_check_type(check_type);
	openSmonDialog(check_type, smon_id, true);
	getCheckSettings(smon_id, check_type);

}
function cloneSmon(id, check_type) {
	check_and_clear_check_type(check_type);
	getCheckSettings(id, check_type);
	openSmonDialog(check_type);
}
function getSmonCheck(smon_id, check_id, dialog_id, new_check=false, intervaled=false) {
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
	if (!intervaled) {
		setInterval(getSmonCheck, 60000, smon_id, check_id, '', false, true);
		$(dialog_id).dialog("close");
	}
}
function check_and_clear_check_type(check_type) {
	$("#check_type").val(check_type);
	$('#check_type').selectmenu("refresh");
	if (check_type === 'http') {
		$('.new_smon_hostname').hide();
		$('.smon_tcp_check').hide();
		$('.smon_ping_check').hide();
		$('.smon_dns_check').hide();
		$('.smon_smtp_check').hide();
		$('.smon_rabbit_check').hide();
		clear_check_vals();
		$('.smon_http_check').show();
	} else if (check_type === 'tcp') {
		$('.new_smon_hostname').show();
		$('.smon_http_check').hide();
		$('.smon_dns_check').hide();
		$('.smon_ping_check').hide();
		$('.smon_smtp_check').hide();
		$('.smon_rabbit_check').hide();
		clear_check_vals();
		$('.smon_tcp_check').show();
	} else if (check_type === 'dns') {
		$('.new_smon_hostname').show();
		$('.smon_tcp_check').hide();
		$('.smon_http_check').hide();
		$('.smon_ping_check').hide();
		$('.smon_smtp_check').hide();
		$('.smon_rabbit_check').hide();
		clear_check_vals();
		$('#new-smon-port').val('53');
		$('.smon_dns_check').show();
	} else if (check_type === 'smtp') {
		$('.new_smon_hostname').show();
		$('.smon_tcp_check').hide();
		$('.smon_http_check').hide();
		$('.smon_ping_check').hide();
		$('.smon_dns_check').hide();
		$('.smon_rabbit_check').hide();
		clear_check_vals();
		$('#new-smon-port').val('587');
		$('#new-smon-username').attr('placeholder', 'examplte@example.com');
		$('.smon_smtp_check').show();
	} else if (check_type === 'rabbitmq') {
		$('.new_smon_hostname').show();
		$('.smon_tcp_check').hide();
		$('.smon_http_check').hide();
		$('.smon_ping_check').hide();
		$('.smon_dns_check').hide();
		$('.smon_smtp_check').hide();
		clear_check_vals();
		$('#new-smon-port').val('5672');
		$('#new-smon-vhost').val('/');
		$('#new-smon-username').attr('placeholder', 'guest');
		$('.smon_rabbit_check').show();
	} else {
		$('.new_smon_hostname').show();
		$('.smon_http_check').hide();
		$('.smon_tcp_check').hide();
		$('.smon_dns_check').hide();
		$('.smon_smtp_check').hide();
		$('.smon_rabbit_check').hide();
		clear_check_vals();
		$('#new-smon-packet_size').val('56');
		$('.smon_ping_check').show();
	}
}
function clear_check_vals() {
	const inputs_for_clean = ['url', 'body', 'body-req', 'port', 'packet_size', 'ip', 'header-req', 'username', 'password', 'vhost', 'group', 'description']
	for (let i of inputs_for_clean) {
		$('#new-smon-' + i).val('');
	}
}
function show_smon_history_statuses(check_id, id_for_history_replace) {
	$.ajax({
		url: api_v_prefix + "/rmon/check/" + check_id + "/statuses",
		contentType: "application/json; charset=utf-8",
		success: function (data) {
			let statuses = '';
			for (let status of data.reverse()) {
				let add_class = 'serverUp';
				if (status.status === 0) {
					add_class = 'serverDown'
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
		url: api_v_prefix + "/rmon/check/" + check_type + "/" + check_id + "/metrics",
		success: function (result) {
			let labels = result.chartData.labels;
			if (check_type === 'http') {
				renderSMONChartHttp(result, labels, check_id, check_types[check_type]);
			} else if (check_type === 'smtp') {
				renderSMONChartSmtp(result, labels, check_id, check_types[check_type]);
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
				}
			}
			chart_id.data.labels.push(data.time);
			chart_id.data.datasets[0].data.push(data.response_time);
			if (check_type_id === '2' || check_type_id === '3') {
				chart_id.data.datasets[1].data.push(data.name_lookup);
				chart_id.data.datasets[2].data.push(data.connect);
				chart_id.data.datasets[3].data.push(data.app_connect);
				if (check_type_id === '2') {
					chart_id.data.datasets[4].data.push(data.pre_transfer);
					chart_id.data.datasets[5].data.push(data.redirect);
					chart_id.data.datasets[6].data.push(data.m_download);
				}
			}
			if (data.status === "0") {
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
		last_resp_time = last_resp_time + 'ms'
	}
	if ($('#translate').attr('data-history_of')) {
		let title_text = `${$('#translate').attr('data-history_of')} ${data.name.replaceAll("'", "")}`
		$('title').text(title_text);
		$('h2').text(title_text);
	}
	$('#last_resp_time').html(last_resp_time);
	$('#uptime').html(data.uptime + '%');
	$('#avg_res_time').html(data.avg_res_time + 'ms');
	$('#interval').text(data.interval);
	$('#updated_at').text(data.updated_at);
	$('#ssl_expire_date').text(data.ssl_expire_date);
	updateCurrentStatus(check_id, data);
}
