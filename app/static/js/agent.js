function checkAgentLimit() {
	let return_value = false;
	$.ajax({
		url: '/rmon/agent/count',
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
function addAgentDialog(agent_id=0, edit=false) {
	cleanAgentAddForm();
	let tabel_title = $("#add-agent-page-overview").attr('title');
	let buttons = [];
	if (edit) {
		add_word = $('#translate').attr('data-edit');
		let reconfigure_word = $('#translate').attr('data-reconfigure');
		tabel_title = $("#add-agent-page-overview").attr('data-edit');
		getAgentSettings(agent_id);
		buttons = [
			{
				text: reconfigure_word,
				click: function () {
					addAgent($(this), agent_id, true, true);
				}
			}, {
				text: add_word,
				click: function () {
					addAgent($(this), agent_id, true);
				}
			}, {
				text: cancel_word,
				click: function () {
					$(this).dialog("close");
				}
			}
		]
	} else {
		add_word = $('#translate').attr('data-add');
		if (!checkAgentLimit()) {
			return false;
		}
		getFreeServers();
		buttons = [
			{
				text: add_word,
				click: function () {
					addAgent($(this));
				}
			}, {
				text: cancel_word,
				click: function () {
					$(this).dialog("close");
				}
			}
		]
	}
	let dialogTable = $("#add-agent-page").dialog({
		autoOpen: false,
		resizable: false,
		height: "auto",
		width: 630,
		modal: true,
		title: tabel_title,
		show: {
			effect: "fade",
			duration: 200
		},
		hide: {
			effect: "fade",
			duration: 200
		},
		buttons: buttons
	});
	dialogTable.dialog('open');
}
function addAgent(dialog_id, agent_id=0, edit=false, reconfigure=false) {
	let valid = true;
	allFields = $([]).add($('#new-agent-name'));
	allFields.removeClass("ui-state-error");
	valid = valid && checkLength($('#new-agent-name'), "Name", 1);
	let agent_name = $('#new-agent-name').val();
    let agent_server_id = $('#new-agent-server-id').val();
    let agent_desc = $('#new-agent-desc').val();
    let agent_enabled = $('#new-agent-enabled').is(':checked') ? 1 : 0;
    let agent_shared = $('#new-agent-shared').is(':checked') ? 1 : 0;
    let agent_data = {
        'name': agent_name,
        'server_id': agent_server_id,
        'desc': agent_desc,
        'enabled': agent_enabled,
        'shared': agent_shared
    };
	let method = 'POST';
	if (edit) {
		method = 'PUT'
		agent_data['agent_id'] = agent_id;
		if (reconfigure) {
			agent_data['reconfigure'] = "1";
		}
	}
	if (valid) {
		$.ajax({
			url: "/rmon/agent",
			type: method,
			data: JSON.stringify(agent_data),
			contentType: "application/json; charset=utf-8",
			success: function (data) {
				data = data.replace(/\s+/g, ' ');
				if (data.indexOf('error:') != '-1' || data.indexOf('unique') != '-1') {
					toastr.error(data);
				} else {
					toastr.clear();
					$(dialog_id).dialog("close");
					if (edit) {
						getAgent(agent_id, false);
					} else {
						getAgent(data, new_agent = true);
					}
				}
			}
		});
	}
}
function getAgentSettings(agent_id) {
	$.ajax({
		url: "/rmon/agent/settings/" + agent_id,
		async: false,
		success: function (data) {
			$('#new-agent-name').val(data['name']);
			$('#new-agent-server-id').append('<option value="' + data['server_id'] + '" selected="selected">' + data['hostname'] + '</option>');
			$('#new-agent-server-id').attr('disabled', 'disabled');
			$('#new-agent-desc').val(data['desc']);
			$('#new-agent-enabled').checkboxradio("refresh");
			if (data['enabled'] == '1') {
				$('#new-agent-enabled').prop('checked', true)
			} else {
				$('#new-agent-enabled').prop('checked', false)
			}
			if (data['shared'] == '1') {
				$('#new-agent-shared').prop('checked', true)
			} else {
				$('#new-agent-shared').prop('checked', false)
			}
			$('#new-agent-enabled').checkboxradio("refresh");
			$('#new-agent-shared').checkboxradio("refresh");
			$('#new-agent-server-id').selectmenu("refresh");
		}
	});
}
function getFreeServers() {
	$.ajax({
		url: "/rmon/agent/free",
		async: false,
		contentType: "application/json; charset=utf-8",
		success: function (data) {
			$("#new-agent-server-id option[value!='------']").remove();
			for (k in data) {
				$('#new-agent-server-id').append('<option value="' + k + '" selected="selected">' + data[k] + '</option>');
			}
			$('#new-agent-server-id').selectmenu("refresh");
		}
	});
}
function cleanAgentAddForm() {
	$('#new-agent-name').val('');
	$('#new-agent-server-id').val('------').change();
	$('#new-agent-desc').val('');
	$('#new-agent-enabled').prop('checked', true);
	$('#new-agent-enabled').checkboxradio("refresh");
	$('#new-agent-server-id').removeAttr('disabled');
	$('#new-agent-server-id').selectmenu("refresh");
}
function getAgent(agent_id, new_agent=false) {
	$.ajax({
		url: "/rmon/agent/info/" + agent_id,
		success: function (data) {
			data = data.replace(/^\s+|\s+$/g, '');
			if (data.indexOf('error:') != '-1') {
				toastr.error(data);
			} else {
				if (new_agent) {
					$('.up-pannel').append(data);
				} else {
					$('#agent-' + agent_id).replaceWith(data);
				}
				$.getScript("/static/js/fontawesome.min.js");
				$('#agent-' + agent_id).removeClass('animated-background');
			}
		}
	});
}
function getAgentVersion(server_ip, agent_id){
	$.ajax({
		url: '/rmon/agent/version/' + server_ip,
		type: 'get',
		data: {agent_id: agent_id},
		success: function (data){
			try {
				if (data['update']) {
					$('#agent-update-' + agent_id).show();
				}
				$('#agent-version-' + agent_id).text(data['version'])
			} catch (e) {
				console.log(e)
			}
		}
	});
}
function getAgentUptime(server_ip, agent_id){
	$.ajax({
		url: '/rmon/agent/uptime/' + server_ip,
		type: 'get',
		data: {agent_id: agent_id},
		success: function (data){
			try {
				data = JSON.parse(data);
				$('#agent-uptime-' + agent_id).text(data['uptime']);
				$('#agent-uptime-' + agent_id).attr('datetime', data['uptime']);
				$("#agent-uptime-"+agent_id).timeago();
			} catch (e) {
				console.log(e)
			}
		}
	});
}
function getAgentStatus(server_ip, agent_id){
	$.ajax({
		url: '/rmon/agent/status/' + server_ip,
		type: 'get',
		data: {agent_id: agent_id},
		success: function (data){
			try {
				data = JSON.parse(data);
				if (data['running']) {
					$('#agent-'+agent_id).addClass('div-server-head-up');
					$('#start-'+agent_id).children().addClass('disabled-button');
					$('#start-'+agent_id).children().removeAttr('onclick');
					$('#agent-'+agent_id).removeClass('div-server-head-down');
				} else {
					$('#agent-'+agent_id).removeClass('div-server-head-up');
					$('#agent-'+agent_id).addClass('div-server-head-pause');
					$('#pause-'+agent_id).children().addClass('disabled-button');
					$('#pause-'+agent_id).children().removeAttr('onclick');
				}
			} catch (e) {
				console.log(e);
				$('#agent-'+agent_id).addClass('div-server-head-down');
				$('#stop-'+agent_id).children().addClass('disabled-button');
				$('#pause-'+agent_id).children().addClass('disabled-button');
				$('#pause-'+agent_id).children().removeAttr('onclick');
				$('#stop-'+agent_id).children().removeAttr('onclick');
			}
		}
	});
}
function getAgentTotalChecks(server_ip, agent_id){
	$.ajax({
		url: '/rmon/agent/checks/' + server_ip,
		type: 'get',
		data: {agent_id: agent_id},
		success: function (data){
			try {
				$('#agent-total-checks-'+agent_id).text(data)
			} catch (e) {
				console.log(e);
				$('#agent-'+agent_id).addClass('div-server-head-down')
			}
		}
	});
}
function confirmDeleteAgent(id) {
	$( "#dialog-confirm" ).dialog({
		resizable: false,
		height: "auto",
		width: 400,
		modal: true,
		title: delete_word+" " +$('#agent-name-'+id).text() + "?",
		buttons: [{
			text: delete_word,
			click: function () {
				$(this).dialog("close");
				removeAgent(id, $(this));
			}
		}, {
			text: cancel_word,
			click: function() {
				$( this ).dialog( "close" );
			}
		}]
	});
}
function removeAgent(id, dialog_id) {
	$.ajax({
        url: "/rmon/agent",
        type: "delete",
        data: {agent_id: id},
        success: function (data){
            data = data.replace(/\s+/g, ' ');
            if (data.indexOf('error:') != '-1' || data.indexOf('unique') != '-1') {
                toastr.error(data);
            } else {
                toastr.clear();
                $(dialog_id).dialog("close");
				$('#agent-'+id).remove();
            }
        }
    });
}
function confirmAjaxAction(action, id, server_ip) {
	let action_word = $('#translate').attr('data-'+action);
	$( "#dialog-confirm" ).dialog({
		resizable: false,
		height: "auto",
		width: 400,
		modal: true,
		title: action_word + " " + $('#agent-name-'+id).text() + "?",
		buttons: [{
			text: action_word,
			click: function (){
				agentAction(action, id, server_ip, $(this));
			}
		}, {
			text: cancel_word,
			click: function(){
				$( this ).dialog( "close" );
			}
		}]
	});
}
function agentAction(action, id, server_ip, dialog_id) {
	$.ajax({
		url: "/rmon/agent/action/"+ action,
		type: "post",
		data: {agent_id: id, server_ip: server_ip},
		success: function (data) {
			data = data.replace(/\s+/g, ' ');
			if (data.indexOf('error:') != '-1' || data.indexOf('unique') != '-1') {
				toastr.error(data);
			} else {
				toastr.clear();
				$(dialog_id).dialog("close");
				getAgent(id, false);
			}
		}
	});
}
