function createStatusPageStep1(edited=false, page_id=0) {
	clearStatusPageDialog();
	let next_word = $('#translate').attr('data-next');
	let smon_add_tabel_title = $("#create-status-page-step-1-overview").attr('title');
	if (edited) {
		smon_add_tabel_title = $("#create-status-page-step-1-overview").attr('data-edit');
		$('#new-status-page-name').val($('#page_name-' + page_id).text());
		$('#new-status-page-slug').val($('#page_slug-' + page_id).text().split('/').pop());
		$('#new-status-page-desc').val($('#page_desc-' + page_id).text().replace('(', '').replace(')', ''));
		$.ajax({
			url: api_v_prefix + '/rmon/status-page/' + page_id + '?recurse=true',
			async: false,
			contentType: "application/json; charset=utf-8",
			success: function (data) {
				if (data.status === 'failed') {
					toastr.error(data.error);
				} else {
					for (let i = 0; i < data.checks.length; i++) {
						addCheckToStatus(data.checks[i]['check_id']['id']);
					}
					$('#new-status-page-style').val(data.custom_style.replaceAll("'", ""));
				}
			}
		});
	}
	let regx = /^[a-z0-9_-]+$/;
	let addSmonStatus = $("#create-status-page-step-1").dialog({
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
				clearStatusPageDialog();
				$(this).dialog("close");
			}
		}]
	});
	addSmonStatus.dialog('open');
}
function createStatusPageStep2(edited, page_id) {
	let smon_add_tabel_title = $("#create-status-page-step-2-overview").attr('title');
	if (edited) {
		smon_add_tabel_title = $("#create-status-page-step-2-overview").attr('data-edit');
		add_word = $('#translate').attr('data-edit');
	}
	let addSmonStatus = $("#create-status-page-step-2").dialog({
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
				clearStatusPageDialog();
				$(this).dialog("close");
			}
		}]
	});
	addSmonStatus.dialog('open');
}
function clearStatusPageDialog() {
	clearTips();
	$('#new-status-page-name').val('');
	$('#new-status-page-slug').val('');
	$('#new-status-page-desc').val('');
	$('#new-status-page-style').val('');
	$("#enabled-check > div").each((index, elem) => {
		let check_id = elem.id.split('-')[1]
		removeCheckFromStatus(check_id);
	});
}
function createStatusPage(dialog_id) {
	let json_data = createJsonData();
	$.ajax({
		url: api_v_prefix + '/rmon/status-page',
		type: 'POST',
		data: JSON.stringify(json_data),
		contentType: "application/json; charset=utf-8",
		success: function (data) {
			if (data.status === 'failed') {
				toastr.error(data);
			} else {
				let id = data.id;
				let new_page = elem("div", {"id":"page_"+id,"class":"page_div"}, [
					elem("a", {"href":"/rmon/status/"+json_data['slug'],"id":"page_link-"+id,"class":"page_link","target":"_blank","title":"Open status page"}, [
						elem("span", {"id":"page_status-"+id}),
						elem("div", null, [
							elem("span", {"class":"page_name","id":"page_name-"+id}, json_data['name']),
							elem("span", {"class":"page_desc","id":"page_desc-"+id}, "("+json_data['description']+")"),
						]),
						elem("div", {"class":"page_slug","id":"page_slug-"+id}, "/rmon/status/"+json_data['slug'])
					]),
					elem("div", {"class":"edit status_page-edit","onclick":"createStatusPageStep1('true', '"+id+"')"}),
					elem("div", {"class":"delete","onclick":"confirmDeleteStatusPage('"+id+"')"})
				])
				$("#pages").append(new_page);
				smon_manage_status_page_avg_status(id);
				$(dialog_id).dialog('close');
				$.getScript("/static/js/fontawesome.min.js");
			}
		}
	});
}
function editStatusPage(dialog_id, page_id) {
	let json_data = createJsonData();
	$.ajax({
		url: api_v_prefix + '/rmon/status-page/' + page_id,
		type: 'PUT',
		data: JSON.stringify(json_data),
		contentType: "application/json; charset=utf-8",
		success: function (data) {
			if (data.status === 'failed') {
				toastr.error(data);
			} else {
				clearStatusPageDialog();
				$(dialog_id).dialog("close");
				$("#page_name-" + page_id).text(json_data['name']);
				$("#page_slug-" + page_id).text('/rmon/status/' + json_data['slug']);
				$("#page_link-" + page_id).attr('href', '/rmon/status/' + json_data['slug']);
				if (json_data['description']) {
					$("#page_desc-" + page_id).text('(' + json_data['description'] + ')');
				}
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
		url: api_v_prefix + '/rmon/status-page/' + page_id,
		type: 'DELETE',
		contentType: "application/json; charset=utf-8",
		statusCode: {
			204: function (xhr) {
				$("#page_" + page_id).remove();
			},
			404: function (xhr) {
				$("#page_" + page_id).remove();
			}
		},
		success: function (data) {
			if (data) {
				if (data.status === "failed") {
					toastr.error(data);
				}
			}
		}
	});
}
function createJsonData() {
	let name = $('#new-status-page-name').val();
	let slug = $('#new-status-page-slug').val();
	let desc = $('#new-status-page-desc').val();
	let checks = [];
	let check_id = '';
	$("#enabled-check > div").each((index, elem) => {
		check_id = elem.id.split('-')[1]
		checks.push(check_id);
	});
	return {
		"name": name,
		"slug": slug,
		"description": desc,
		"custom_style": $('#new-status-page-style').val(),
		"checks": checks
	};
}
function getSmonHistoryCheckDataStatusPage(check_id, check_type_id) {
	console.log(resp_time_word)
	$.ajax({
		url: api_v_prefix + "/rmon/check/" + check_type_id + "/" + check_id + "/metrics",
		success: function (result) {
			let data = [];
			data.push(result.chartData.response_time);
			let labels = result.chartData.labels;
			renderSMONChart(data[0], labels, check_id, check_types[check_type_id]);
			$('#en_table_metric-' + check_id).css('display', 'none');
			$('#dis_table_metric-' + check_id).css('display', 'inline');
			$('#history-status-' + check_id).show();
		}
	});
}
function hideSmonHistoryCheckDataStatusPage(server) {
	$('#en_table_metric-' + server).css('display', 'inline');
	$('#dis_table_metric-' + server).css('display', 'none');
	Chart.getChart('metrics_' + server).destroy();
	$('#history-status-' + server).hide();
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
