$(function () {
	$( "#new-smon-place" ).on('selectmenuchange',function() {
		if ($('#new-smon-place option:selected').val() === 'all') {
			$('#checked-entities').empty();
			$('#all-entities').empty();
			$('#agent_tr').hide();
		} else if ($('#new-smon-place option:selected').val() === 'country') {
			$('#checked-entities').empty();
			$('#all-entities').empty();
			getCountriesForCheck();
			$('#agent_tr').show();
		} else if ($('#new-smon-place option:selected').val() === 'region') {
			$('#checked-entities').empty();
			$('#all-entities').empty();
			getRegionsForCheck();
			$('#agent_tr').show();
		} else {
			$('#checked-entities').empty();
			$('#all-entities').empty();
			getAgentsForCheck();
			$('#agent_tr').show();
		}
	});
});
function getAgentsForCheck() {
	$.ajax({
		url: api_v_prefix + "/rmon/agents",
		type: "get",
		contentType: "application/json; charset=UTF-8",
		async: false,
		success: function (data) {
			if (data.status === 'failed') {
				toastr.error(data.error);
			} else {
				for (let k in data) {
                    let agent = data[k];
					if (agent.enabled === 0) {
						continue;
					}
                    removeEntityFromStatus(agent.id, agent.name);
                }
			}
		}
	});
}
function getRegionsForCheck() {
	$.ajax({
		url: api_v_prefix + "/rmon/regions",
		type: "get",
		contentType: "application/json; charset=UTF-8",
		async: false,
		success: function (data) {
			if (data.status === 'failed') {
				toastr.error(data.error);
			} else {
				for (let k in data) {
                    let agent = data[k];
					if (agent.enabled === 0) {
						continue;
					}
                    removeEntityFromStatus(agent.id, agent.name);
                }
			}
		}
	});
}
function getCountriesForCheck() {
	$.ajax({
		url: api_v_prefix + "/rmon/countries",
		type: "get",
		contentType: "application/json; charset=UTF-8",
		async: false,
		success: function (data) {
			if (data.status === 'failed') {
				toastr.error(data.error);
			} else {
				for (let k in data) {
                    let agent = data[k];
					if (agent.enabled === 0) {
						continue;
					}
					removeEntityFromStatus(agent.id, agent.name);
                }
			}
		}
	});
}
function addEntityToStatus(server_id, hostname) {
	let service_word = translate_div.attr('data-service');
	let html_tag = '<div id="remove_check-' + server_id + '" data-name="' + hostname + '">' +
		'<div class="check-name">' + hostname + '</div>' +
		'<div class="add_user_group check-button" onclick="removeEntityFromStatus(' + server_id + ', \'' + hostname + '\')" title="' + delete_word + ' ' + service_word + '">-</div>' +
		'</div>';
	$('#add_check-' + server_id).remove();
	$('#checked-entities').append(html_tag);
}
function removeEntityFromStatus(server_id, hostname) {
	let add_word = translate_div.attr('data-add');
	let service_word = translate_div.attr('data-service');

	let html_tag = '<div class="all-checks" id="add_check-' + server_id + '" data-name="' + hostname + '">' +
		'<div class="check-name">' + hostname + '</div>' +
		'<div class="add_user_group check-button" onclick="addEntityToStatus(' + server_id + ',  \'' + hostname + '\')" title="' + add_word + ' ' + service_word + '">+</div></div>';
    $('#all-entities').append(html_tag);
	$('#remove_check-' + server_id).remove();
}
function getEntityJson(entity_id, entity_type) {
	let isGetEntity = true;
	let dataId = '';
	let dataName = '';
	$.ajax({
		url: api_v_prefix + "/rmon/" + entity_type + "/" + entity_id,
		async: false,
		contentType: "application/json; charset=utf-8",
		success: function (data) {
			$("#checked-entities > div").each((index, elem) => {
				if (data.id === Number(elem.id.split('-')[1])) {
					isGetEntity = false;
				}
			});
			dataId = data.id;
			dataName = data.name;
		}
	});
	if (isGetEntity) {
		addEntityToStatus(dataId, dataName);
	}
}
function updateCurrentStatusRequest(check_id) {
	$.ajax({
		url: api_v_prefix + "/rmon/check/" + check_id + "/status",
		type: "get",
		contentType: "application/json; charset=UTF-8",
		async: false,
		statusCode: {
			404: function (xhr) {
				updateCurrentStatus(check_id, {'status': 3});
			}
		},
		success: function (data) {
			if (data.status === 'failed') {
				toastr.error(data.error);
			} else {
				updateCurrentStatus(check_id, data)
			}
		}
	});
}
function updateCurrentStatus(check_id, data) {
	let add_class = 'serverUp';
	let cur_status = translate_div.attr('data-up');
	if (data.status === 0) {
		add_class = 'serverDown';
		cur_status = translate_div.attr('data-down');
	} else if (data.status === 3) {
		add_class = 'serverWarn';
		cur_status = translate_div.attr('data-unknown');
	} else if (data.status === 4) {
		add_class = 'serverNone';
		cur_status = translate_div.attr('data-disabled');
	}
	if (data.time) {
		let time = data.time;
		let mes = data.mes;
		let div_server_statuses = '<div class="smon_server_statuses ' + add_class + '" title="" data-help="' + time + ' ' + mes + '"></div>'
		if ($('#smon_history_statuses-' + check_id).children().length === 40) {
			$('#smon_history_statuses-' + check_id).find('div:first').remove()
		}
		$('#smon_history_statuses-' + check_id).append(div_server_statuses);
		$("[title]").tooltip({
			"content": function () {
				return $(this).attr("data-help");
			},
			show: {"delay": 1000}
		});
	}
	let div_cur_status = '<span class="' + add_class + ' cur_status" style="font-size: 15px; border-radius: 50rem!important;min-width: 62px;">' + cur_status + '</span>'
	$('#cur_status-' + check_id).html(div_cur_status);
}
function confirmDeleteCheckGroup(check_group_id) {
	$("#dialog-confirm").dialog({
		resizable: false,
		height: "auto",
		width: 400,
		modal: true,
		title: delete_word + " ?",
		buttons: [{
			text: delete_word,
			click: function () {
				$(this).dialog("close");
				removeCheckGroup(check_group_id);
			}
		}, {
			text: cancel_word,
			click: function () {
				$(this).dialog("close");
			}
		}]
	});
}
function removeCheckGroup(check_group_id) {
	$.ajax({
		url: api_v_prefix + "/rmon/check-group/" + check_group_id,
		type: "DELETE",
		contentType: "application/json; charset=utf-8",
		success: function (data, statusText, xhr) {
			if (xhr.status === 204) {
				$('#smon-group-' + check_group_id).appendTo('#smon-group-')
				$("#check-group-" + check_group_id).remove();
			} else {
				if (data.status === 'failed') {
					toastr.error(data);
				}
			}
		}
	});
}