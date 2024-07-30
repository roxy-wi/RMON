var check_types = {'tcp': 1, 'http': 2, 'ping': 4, 'dns': 5};
$(function () {
	$( "#check_type" ).on('selectmenuchange',function() {
		check_and_clear_check_type($('#check_type').val());
	});
	$("#new-smon-group").autocomplete({
		source: function (request, response) {
			$.ajax({
				url: "/rmon/groups",
				success: function (data) {
					response(data.split("\n"));
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
	window.history.pushState("SMON Dashboard", "SMON Dashboard", "?sort=by_status");
}
function showSmon(action) {
	if (action === 'not_sort') {
		window.history.pushState("SMON Dashboard", "SMON Dashboard", "/rmon/dashboard");
	}
	window.location.reload();
}
function addNewSmonServer(dialog_id, smon_id=0, edit=false) {
	let valid = true;
	let check_type = $('#check_type').val();
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
	valid = valid && checkLength($('#new-smon-name'), "Name", 1);
	valid = valid && checkLength($('#new-smon-interval'), "Check interval", 1);
	valid = valid && checkLength($('#new-smon-timeout'), "Timeout", 1);
	let enable = 0;
	if ($('#new-smon-enable').is(':checked')) {
		enable = '1';
	}
	let jsonData = {
		'name': $('#new-smon-name').val(),
		'ip': $('#new-smon-ip').val(),
		'port': $('#new-smon-port').val(),
		'resolver': $('#new-smon-resolver-server').val(),
		'record_type': $('#new-smon-dns_record_type').val(),
		'enabled': enable,
		'url': $('#new-smon-url').val(),
		'body': $('#new-smon-body').val(),
		'group': $('#new-smon-group').val(),
		'desc': $('#new-smon-description').val(),
		'tg': $('#new-smon-telegram').val(),
		'slack': $('#new-smon-slack').val(),
		'pd': $('#new-smon-pd').val(),
		'mm': $('#new-smon-mm').val(),
		'packet_size': $('#new-smon-packet_size').val(),
		'http_method': $('#new-smon-method').val(),
		'interval': $('#new-smon-interval').val(),
		'agent_id': $('#new-smon-agent-id').val(),
		'body_req': $('#new-smon-body-req').val(),
		'header_req': $('#new-smon-header-req').val(),
		'accepted_status_codes': $('#new-smon-status-code').val(),
		'timeout': $('#new-smon-timeout').val()
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
	let smon_add_tabel_title = $("#smon-add-table-overview").attr('title');
	if (edit) {
		add_word = $('#translate').attr('data-edit');
		smon_add_tabel_title = $("#smon-add-table-overview").attr('data-edit');
		$('#check_type').attr('disabled', 'disabled');
		$('#check_type').selectmenu("refresh");
	} else {
		if (!checkChecksLimit()) {
			return false;
		}
		$('#check_type').removeAttr('disabled');
		$('#check_type').selectmenu("refresh");
		$('#new-smon-name').val('');
	}
	getAgents('#new-smon-agent-id');
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
		url: api_v_prefix + "/rmon/check/" +  check_type + "/" + smon_id,
		type: "get",
		async: false,
		dataType: "json",
		success: function (data) {
			$('#new-smon-name').val(data['smon_id']['name'].replaceAll("'", ""));
			$('#new-smon-ip').val(data['ip']);
			$('#new-smon-port').val(data['port']);
			$('#new-smon-resolver-server').val(data['resolver']);
			$('#new-smon-dns_record_typer').val(data['record_type']);
			$('#new-smon-url').val(data['url']);
			$('#new-smon-description').val(data['smon_id']['desc'].replaceAll("'", ""))
			$('#new-smon-packet_size').val(data['packet_size']);
			$('#new-smon-interval').val(data['interval']);
			if (data['group_name']) {
				$('#new-smon-group').val(data['group_name'].replaceAll("'", ""));
			}
			if (data['timeout']) {
				$('#new-smon-timeout').val(data['timeout']);
			}
			try {
				$('#new-smon-body').val(data['body'].replaceAll("'", ""));
			} catch (e) {
				$('#new-smon-body').val(data['body']);
			}
			try {
				$('#new-smon-body-req').val(data['body_req'].replaceAll("'", ""));
			} catch (e) {
				$('#new-smon-body-req').val(data['body_req']);
			}
			try {
				$('#new-smon-header-req').val(data['header_req'].replaceAll("'", ""));
			} catch (e) {
				$('#new-smon-header-req').val(data['header_req']);
			}
			$('#new-smon-status-code').val(data['accepted_status_codes']);
			$('#new-smon-agent-id').val(data['agent_id']).change();
			$('#new-smon-telegram').val(data['tg']).change();
			$('#new-smon-slack').val(data['slack']).change();
			$('#new-smon-pd').val(data['pd']).change();
			$('#new-smon-telegram').selectmenu("refresh");
			$('#new-smon-slack').selectmenu("refresh");
			if (data['mm']) {
				$('#new-smon-mm').val(data['mm']).change();
				$('#new-smon-mm').selectmenu("refresh");
			}
			if (data['method']) {
				$('#new-smon-method').val(data['method']).change();
				$('#new-smon-method').selectmenu("refresh");
			}
			$('#new-smon-agent-id').selectmenu("refresh");
			if (data['smon_id']['enabled']) {
				$('#new-smon-enable').prop('checked', true)
			} else {
				$('#new-smon-enable').prop('checked', false)
			}
			$('#new-smon-enable').checkboxradio("refresh");
		}
	});
}
function editSmon(smon_id, check_type) {
	check_and_clear_check_type(check_type);
	openSmonDialog(check_type, smon_id, true);
	getCheckSettings(smon_id, check_type);

}
function cloneSmom(id, check_type) {
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
	if (check_type === 'http') {
		$('.new_smon_hostname').hide();
		$("#check_type").val('http');
		$('#check_type').selectmenu("refresh");
		$('.smon_tcp_check').hide();
		$('.smon_ping_check').hide();
		$('.smon_dns_check').hide();
		clear_check_vals();
		$('.smon_http_check').show();
	} else if (check_type === 'tcp') {
		$("#check_type").val('tcp');
		$('#check_type').selectmenu("refresh");
		$('.new_smon_hostname').show();
		$('.smon_http_check').hide();
		$('.smon_dns_check').hide();
		$('.smon_ping_check').hide();
		clear_check_vals();
		$('.smon_tcp_check').show();
	} else if (check_type === 'dns') {
		$("#check_type").val('dns');
		$('#check_type').selectmenu("refresh");
		$('.smon_tcp_check').hide();
		$('.new_smon_hostname').show();
		$('.smon_http_check').hide();
		$('.smon_ping_check').hide();
		clear_check_vals();
		$('#new-smon-port').val('53');
		$('.smon_dns_check').show();
	} else {
		$('.smon_http_check').hide();
		$('.new_smon_hostname').show();
		$('.smon_tcp_check').hide();
		$('.smon_dns_check').hide();
		$('.smon_ping_check').show();
		$("#check_type").val('ping');
		clear_check_vals();
		$('#new-smon-packet_size').val('56');
		$('#check_type').selectmenu("refresh");
	}
}
function clear_check_vals() {
	const inputs_for_clean = ['url', 'body', 'body-req', 'port', 'packet_size', 'ip', 'header-req']
	for (let i of inputs_for_clean) {
		$('#new-smon-' + i).val('');
	}
}
function show_statuses(dashboard_id, check_id, id_for_history_replace) {
	show_smon_history_statuses(dashboard_id, id_for_history_replace);
	$.ajax({
		url: "/rmon/history/cur_status/" + dashboard_id + "/" + check_id,
		success: function (data) {
			data = data.replace(/\s+/g, ' ');
			if (data.indexOf('error:') != '-1' || data.indexOf('unique') != '-1') {
				toastr.error(data);
			} else {
				toastr.clear();
				$("#cur_status").html(data);
			}
		}
	});
}
function show_smon_history_statuses(dashboard_id, id_for_history_replace) {
	$.ajax({
		url: "/rmon/history/statuses/" + dashboard_id,
		success: function (data) {
			data = data.replace(/\s+/g, ' ');
			$(id_for_history_replace).html(data);
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
function smon_status_page_avg_status(page_id) {
	$.ajax({
		url: "/rmon/status/avg/" + page_id,
		success: function (data) {
			data = data.replace(/\s+/g, ' ');
			if (data.indexOf('error:') != '-1' || data.indexOf('unique') != '-1') {
				toastr.error(data);
			} else {
				toastr.clear();
				if (data == '1') {
					$('#page_status').html('<i class="far fa-check-circle page_icon page_icon_all_ok"></i><span>All Systems Operational</span>');
				} else {
					$('#page_status').html('<i class="far fa-times-circle page_icon page_icon_not_ok"></i><span>Not all Systems Operational</span>')
				}
			}
		}
	});
}
function smon_manage_status_page_avg_status(page_id) {
	$.ajax({
		url: "/rmon/status/avg/" + page_id,
		success: function (data) {
			data = data.replace(/\s+/g, ' ');
			if (data.indexOf('error:') != '-1' || data.indexOf('unique') != '-1') {
				toastr.error(data);
			} else {
				toastr.clear();
				if (data == '1') {
					$('#page_status-'+page_id).html('<i class="far fa-check-circle status-page-icon status-page-icon-ok"></i>');
				} else {
					$('#page_status-'+page_id).html('<i class="far fa-times-circle status-page-icon status-page-icon-not-ok"></i>')
				}
			}
		}
	});
}
function createStatusPageStep1(edited=false, page_id=0) {
	var next_word = $('#translate').attr('data-next');
	var smon_add_tabel_title = $("#create-status-page-step-1-overview").attr('title');
	if (edited) {
		smon_add_tabel_title = $("#create-status-page-step-1-overview").attr('data-edit');
		$('#new-status-page-name').val($('#page_name-'+page_id).text());
		$('#new-status-page-slug').val($('#page_slug-'+page_id).text().split('/').pop());
		$('#new-status-page-desc').val($('#page_desc-'+page_id).text().replace('(','').replace(')',''));
	}
	var regx = /^[a-z0-9_-]+$/;
	var addSmonStatus = $("#create-status-page-step-1").dialog({
		autoOpen: false,
		resizable: false,
		height: "auto",
		width: 630,
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
			text: next_word,
			click: function () {
				if ($('#new-status-page-name').val() == '') {
					toastr.error('error: Fill in the Name field');
					return false;
				}
				if (!regx.test($('#new-status-page-slug').val())) {
					toastr.error('error: Incorrect Slug');
					return false;
				}
				if ($('#new-status-page-slug').val().indexOf('--') != '-1') {
					toastr.error('error: "--" are prohibeted in Slug');
					return false;
				}
				if ($('#new-status-page-slug').val() == '') {
					toastr.error('error: Fill in the Slug field');
					return false;
				}
				createStatusPageStep2(edited, page_id);
				$(this).dialog("close");
				toastr.clear();
			}
		}, {
			text: cancel_word,
			click: function () {
				clearStatusPageDialog($(this));
			}
		}]
	});
	addSmonStatus.dialog('open');
}
function createStatusPageStep2(edited, page_id) {
	var back_word = $('#translate').attr('data-back');
	var smon_add_tabel_title = $("#create-status-page-step-2-overview").attr('title');
	if (edited) {
		smon_add_tabel_title = $("#create-status-page-step-2-overview").attr('data-edit');
		add_word = $('#translate').attr('data-edit');
		if ($("#enabled-check > div").length == 0) {
			$.ajax({
				url: "/rmon/status/checks/" + page_id,
				async: false,
				type: "GET",
				success: function (data) {
					if (data.indexOf('error:') != '-1') {
						toastr.error(data);
					} else {
						for (let i = 0; i < data.length; i++) {
							addCheckToStatus(data[i]);
						}
					}
				}
			});
		}
	}
	var addSmonStatus = $("#create-status-page-step-2").dialog({
		autoOpen: false,
		resizable: false,
		height: "auto",
		width: 630,
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
				if (edited) {
					editStatusPage($(this), page_id);
				} else {
					createStatusPage($(this));
				}
			}
		}, {
			text: back_word,
			click: function () {
				$(this).dialog("close");
				createStatusPageStep1(edited, page_id);
			}
		}, {
			text: cancel_word,
			click: function () {
				clearStatusPageDialog($(this));
			}
		}]
	});
	addSmonStatus.dialog('open');
}
function clearStatusPageDialog(dialog_id) {
	dialog_id.dialog("close");
	clearTips();
	$('#new-status-page-name').val('');
	$('#new-status-page-slug').val('');
	$('#new-status-page-desc').val('');
	$("#enabled-check > div").each((index, elem) => {
		check_id = elem.id.split('-')[1]
		removeCheckFromStatus(check_id);
	});
}
function createStatusPage(dialog_id) {
	let name_id = $('#new-status-page-name');
	let slug_id = $('#new-status-page-slug');
	let desc_id = $('#new-status-page-desc');
	let checks = [];
	let check_id = '';
	$("#enabled-check > div").each((index, elem) => {
		check_id = elem.id.split('-')[1]
		checks.push(check_id);
	});
	$.ajax({
		url: '/rmon/status-page',
		type: 'POST',
		data: {
			name: name_id.val(),
			slug: slug_id.val(),
			desc: desc_id.val(),
			checks: JSON.stringify({'checks': checks})
		},
		success: function (data) {
			data = data.replace(/\s+/g, ' ');
			if (data.indexOf('error:') != '-1' || data.indexOf('unique') != '-1') {
				toastr.error(data);
			} else {
				clearStatusPageDialog(dialog_id);
				$("#pages").append(data);
				$.getScript("/static/js/fontawesome.min.js");
			}
		}
	});
}
function editStatusPage(dialog_id, page_id) {
	let name_id = $('#new-status-page-name');
	let slug_id = $('#new-status-page-slug');
	let desc_id = $('#new-status-page-desc');
	let checks = [];
	let check_id = '';
	$("#enabled-check > div").each((index, elem) => {
		check_id = elem.id.split('-')[1]
		checks.push(check_id);
	});
	$.ajax({
		url: '/rmon/status-page',
		type: 'PUT',
		data: {
			page_id: page_id,
			name: name_id.val(),
			slug: slug_id.val(),
			desc: desc_id.val(),
			checks: JSON.stringify({'checks': checks})
		},
		success: function (data) {
			data = data.replace(/\s+/g, ' ');
			if (data.indexOf('error:') != '-1' || data.indexOf('unique') != '-1') {
				toastr.error(data);
			} else {
				clearStatusPageDialog(dialog_id);
				$("#page_" + page_id).replaceWith(data);
				$("#page_" + page_id).addClass("update", 1000);
				setTimeout(function () {
					$("#page_" + page_id).removeClass("update");
				}, 2500);
				$.getScript("/static/js/fontawesome.min.js");
			}
		}
	});
}
function addCheckToStatus(service_id) {
	var service_name = $('#add_check-' + service_id).attr('data-service_name');
	var service_word = $('#translate').attr('data-service');
	var length_tr = $('#all-checks').length;
	var tr_class = 'odd';
	if (length_tr % 2 != 0) {
		tr_class = 'even';
	}
	var html_tag = '<div class="' + tr_class + '" id="remove_check-' + service_id + '" data-service_name="' + service_name + '">' +
		'<div class="check-name">' + service_name + '</div>' +
		'<div class="add_user_group check-button" onclick="removeCheckFromStatus(' + service_id + ')" title="' + delete_word + ' ' + service_word + '">-</div></div>';
	$('#add_check-' + service_id).remove();
	$("#enabled-check").append(html_tag);
}
function removeCheckFromStatus(service_id) {
	var service_name = $('#remove_check-' + service_id).attr('data-service_name');
	var service_word = $('#translate').attr('data-service');
	var length_tr = $('#all_services tbody tr').length;
	var tr_class = 'odd';
	if (length_tr % 2 != 0) {
		tr_class = 'even';
	}
	var html_tag = '<div class="' + tr_class + ' all-checks" id="add_check-' + service_id + '" data-service_name="' + service_name + '">' +
		'<div class="check-name">' + service_name + '</div>' +
		'<div class="add_user_group check-button" onclick="addCheckToStatus(' + service_id + ')" title="' + add_word + ' ' + service_word + '">+</div></div>';
	$('#remove_check-' + service_id).remove();
	$("#all-checks").append(html_tag);
}
function confirmDeleteStatusPage(id) {
	$("#dialog-confirm").dialog({
		resizable: false,
		height: "auto",
		width: 400,
		modal: true,
		title: delete_word + " " + $('#page_name-' + id).text() + "?",
		buttons: [{
			text: delete_word,
			click: function () {
				$(this).dialog("close");
				deleteStatusPage(id);
			}
		}, {
			text: cancel_word,
			click: function () {
				$(this).dialog("close");
			}
		}]
	});
}
function deleteStatusPage(page_id) {
	$.ajax({
		url: '/rmon/status-page',
		type: 'DELETE',
		data: {
			page_id: page_id,
		},
		success: function (data) {
			data = data.replace(/\s+/g, ' ');
			if (data.indexOf('error:') != '-1' || data.indexOf('unique') != '-1') {
				toastr.error(data);
			} else {
				$('#page_' + page_id).remove();
			}
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
function getSmonHistoryCheckDataStatusPage(server, check_type_id) {
	let check_types = {'ping': '1', 'tcp': '2', 'http': '4', 'dns': '5'}
	$.ajax({
		url: "/rmon/history/metric/" + server + "/" + check_types[check_type_id],
		success: function (result) {
			let data = [];
			data.push(result.chartData.curr_con);
			let labels = result.chartData.labels;
			renderSMONChart(data[0], labels, server);
			$('#en_table_metric-' + server).css('display', 'none');
			$('#dis_table_metric-' + server).css('display', 'inline');
			$('#history-status-' + server).show();
		}
	});
}
function hideSmonHistoryCheckDataStatusPage(server) {
	$('#en_table_metric-' + server).css('display', 'inline');
	$('#dis_table_metric-' + server).css('display', 'none');
	Chart.getChart('metrics_' + server).destroy();
	$('#history-status-' + server).hide();
}
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
function getSmonHistoryCheckData(check_id, check_type_id) {
    $.ajax({
        url: "/rmon/history/metric/" + check_id + "/" + check_type_id,
        success: function (result) {
            let data = [];
            data.push(result.chartData.curr_con);
            let labels = result.chartData.labels;
			if (check_type_id == 2) {
				renderSMONChartHttp(result, labels, check_id, check_type_id);
			} else {
				renderSMONChart(data[0], labels, check_id, check_type_id);
			}
        }
    });
}
function renderSMONChartHttp(result, labels, check_id, check_type_id) {
	const resp_time_word = $('#translate').attr('data-resp_time');
    const ctx = document.getElementById('metrics_' + check_id);

    // Преобразование данных в массивы
    const labelArray = labels.split(',');
    const name_lookup = result.chartData.name_lookup.split(',');
    const connect = result.chartData.connect.split(',');
    const app_connect = result.chartData.app_connect.split(',');
    const pre_transfer = result.chartData.pre_transfer.split(',');
    const redirect = result.chartData.redirect.split(',');
    const start_transfer = result.chartData.start_transfer.split(',');
    const download = result.chartData.download.split(',');
    const curr_con = result.chartData.curr_con.split(',');

    // Удаление последнего пустого элемента в каждом массиве
    labelArray.pop();
    name_lookup.pop();
    connect.pop();
    app_connect.pop();
    pre_transfer.pop();
    redirect.pop();
    start_transfer.pop();
    download.pop();
    curr_con.pop();

    // Создание объекта dataset
    const dataset = [{
        label: resp_time_word + ' (ms)',
        data: curr_con,
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
function renderSMONChart(data, labels, check_id, check_type_id) {
    const resp_time_word = $('#translate').attr('data-resp_time');
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
    source.onmessage = function (event) {
        const data = JSON.parse(event.data);
        if (chart_id.data.labels.length >= 40) {
            chart_id.data.labels.shift();
            chart_id.data.datasets[0].data.shift();
			if (check_type_id === '2') {
				chart_id.data.datasets[1].data.shift();
				chart_id.data.datasets[2].data.shift();
				chart_id.data.datasets[3].data.shift();
				chart_id.data.datasets[4].data.shift();
				chart_id.data.datasets[5].data.shift();
				chart_id.data.datasets[6].data.shift();
			}
        }
        chart_id.data.labels.push(data.time);
        chart_id.data.datasets[0].data.push(data.value);
        if (check_type_id === '2') {
            chart_id.data.datasets[1].data.push(data.name_lookup);
            chart_id.data.datasets[2].data.push(data.connect);
            chart_id.data.datasets[3].data.push(data.app_connect);
            chart_id.data.datasets[4].data.push(data.pre_transfer);
            chart_id.data.datasets[5].data.push(data.redirect);
            chart_id.data.datasets[6].data.push(data.m_download);
        }
		if (data.status === "0") {
			chart_id.data.datasets[0].fillColor = 'rgb(239,5,59)';
		}
        chart_id.update();
		update_cur_statues(check_id, data);
    }
}
function update_cur_statues(check_id, data) {
	let status = data.status;
	if (status == "4") {
		return false;
	}
	let last_resp_time = data.value;
	let time = data.time;
	let mes = data.mes;
	let add_class = 'serverUp';
	let cur_status = 'UP';
	if (status === "0") {
		add_class = 'serverDown';
		cur_status = 'DOWN';
	} else if (status == "4") {
		add_class = 'serverNone';
		cur_status = 'DISABLED';
	}
	if (last_resp_time.length === 0) {
		last_resp_time = 'N/A';
	} else {
		last_resp_time = last_resp_time + 'ms'
	}
	let title_text = `${$('#translate').attr('data-history_of')} ${data.name}`
	let div_cur_status = '<span class="' + add_class + ' cur_status" style="font-size: 30px; border-radius: 50rem!important;min-width: 62px;">' + cur_status + '</span>'
	let div_server_statuses = '<div class="smon_server_statuses ' + add_class + '" title="" data-help="' + time + ' ' + mes + '" style="margin-left: 4px;"></div>'
	$('#cur_status').html(div_cur_status);
	$('#last_resp_time').html(last_resp_time);
	$('#uptime').html(data.uptime + '%');
	$('#avg_res_time').html(data.avg_res_time + 'ms');
	$('#interval').text(data.interval);
	$('#updated_at').text(data.updated_at);
	$('#agent').text(data.agent);
	$('title').text(title_text);
	$('h2').text(title_text);
	$('#ssl_expire_date').text(data.ssl_expire_date);
	if ($('#smon_history_statuses').children().length == 40) {
		$('#smon_history_statuses').find('div:first').remove()
	}
	$('#smon_history_statuses').append(div_server_statuses);
	$("[title]").tooltip({
		"content": function () {
			return $(this).attr("data-help");
		},
		show: {"delay": 1000}
	});
}
