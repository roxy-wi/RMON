$( function() {
	$("#ajax-servers input").change(function () {
		let id = $(this).attr('id').split('-');
		updateServer(id[1])
	});
	$("#ajax-servers select").on('selectmenuchange', function () {
		let id = $(this).attr('id').split('-');
		updateServer(id[1])
	});
	$('#add-server-button').click(function () {
		addServerDialog.dialog('open');
	});
	let server_tabel_title = $("#server-add-table-overview").attr('title');
	let addServerDialog = $("#server-add-table").dialog({
		autoOpen: false,
		resizable: false,
		height: "auto",
		width: 600,
		modal: true,
		title: server_tabel_title,
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
				addServer(this);
			}
		}, {
			text: cancel_word,
			click: function () {
				$(this).dialog("close");
				clearTips();
			}
		}]
	});
});
function addServer(dialog_id) {
    toastr.clear()
    let valid = true;
    let servername = $('#new-server-add').val();
    let ip = $('#new-ip').val();
    let server_group = $('#new-server-group-add').val();
    let cred = $('#credentials').val();
    let enable = 0;
    let add_to_smon = 0;
    if ($('#enable').is(':checked')) {
        enable = '1';
    }
    if ($('#add_to_smon').is(':checked')) {
        add_to_smon = '1';
    }
    let allFields = $([]).add($('#new-server-add')).add($('#new-ip')).add($('#new-port'))
    allFields.removeClass("ui-state-error");
    valid = valid && checkLength($('#new-server-add'), "Hostname", 1);
    valid = valid && checkLength($('#new-ip'), "IP", 1);
    valid = valid && checkLength($('#new-port'), "Port", 1);
    if (cred == null) {
        toastr.error('First select credentials');
        return false;
    }
    if (server_group === '------') {
        toastr.error('First select a group');
        return false;
    }
	if (server_group === undefined || server_group === null) {
		server_group = $('#new-sshgroup').val();
	}
    if (valid) {
        let json_data = {
            "name": servername,
            "ip": ip,
            "port": $('#new-port').val(),
            "group": server_group,
            "add_to_smon": add_to_smon,
            "enabled": enable,
            "creds_id": cred,
            "desc": $('#desc').val(),
        }
        $.ajax({
            url: "/server",
            type: "POST",
            data: JSON.stringify(json_data),
            contentType: "application/json; charset=utf-8",
            success: function (data) {
                if (data.status === 'failed') {
                    toastr.error(data.error);
                } else {
                    common_ajax_action_after_success(dialog_id, 'newserver', 'ajax-servers', data.data);
                    $("input[type=submit], button").button();
                    $("input[type=checkbox]").checkboxradio();
                    $(".controlgroup").controlgroup();
                    $("select").selectmenu();
                    let id = data.id;
                    // after_server_creating(servername, ip, scan_server);
                }
            }
        });
    }
}
function confirmDeleteServer(id) {
	$( "#dialog-confirm" ).dialog({
		resizable: false,
		height: "auto",
		width: 400,
		modal: true,
		title: delete_word + " " + $('#hostname-' + id).val() + "?",
		buttons: [{
			text: delete_word,
			click: function () {
				$(this).dialog("close");
				removeServer(id);
			}
		},{
			text: cancel_word,
			click: function () {
				$(this).dialog("close");
			}
		}]
	});
}
function removeServer(id) {
	$("#server-" + id).css("background-color", "#f2dede");
	$.ajax({
		url: "/server",
		data: JSON.stringify({'id': id}),
		type: "DELETE",
		contentType: "application/json; charset=utf-8",
		success: function (data) {
			if (data.status === "failed") {
				toastr.error(data);
			} else {
				$("#server-" + id).remove();
			}
		}
	});
}
function updateServer(id) {
    toastr.clear();
    let enable = 0;
    if ($('#enable-' + id).is(':checked')) {
        enable = '1';
    }
    let server_group = $('#servergroup-' + id + ' option:selected').val();
    if (server_group === undefined || server_group === null) {
		server_group = $('#new-sshgroup').val();
	}
    let json_data = {
        "name": $('#hostname-' + id).val(),
        "port": $('#port-' + id).val(),
        "group": server_group,
        "enabled": enable,
        "creds_id": $('#credentials-' + id + ' option:selected').val(),
        "id": id,
        "desc": $('#desc-' + id).val()
    }
    $.ajax({
        url: "/server",
        data: JSON.stringify(json_data),
        contentType: "application/json; charset=utf-8",
        type: "PUT",
        success: function (data) {
            if (data.status === 'failed') {
                toastr.error(data.error);
            } else {
                toastr.clear();
                $("#server-" + id).addClass("update", 1000);
                setTimeout(function () {
                    $("#server-" + id).removeClass("update");
                }, 2500);
            }
        }
    });
}
function checkSshConnect(ip) {
	$.ajax({
		url: "/server/check/ssh/" + ip,
		success: function (data) {
			if (data.indexOf('error:') != '-1') {
				toastr.error(data)
			} else if (data.indexOf('failed') != '-1') {
				toastr.error(data)
			} else if (data.indexOf('Errno') != '-1') {
				toastr.error(data)
			} else {
				toastr.clear();
				toastr.success('Connect is accepted');
			}
		}
	});
}
function cloneServer(id) {
	$( "#add-server-button" ).trigger( "click" );
	if ($('#enable-'+id).is(':checked')) {
		$('#enable').prop('checked', true)
	} else {
		$('#enable').prop('checked', false)
	}
	$('#enable').checkboxradio("refresh");
	$('#new-server-add').val($('#hostname-'+id).val())
	$('#new-ip').val($('#ip-'+id).val())
	$('#new-port').val($('#port-'+id).val())
	$('#desc').val($('#desc-'+id).val())
	$('#credentials').val($('#credentials-'+id+' option:selected').val()).change()
	$('#credentials').selectmenu("refresh");
	if (cur_url[0].indexOf('admin') != '-1') {
		$('#new-server-group-add').val($('#servergroup-'+id+' option:selected').val()).change()
		$('#new-server-group-add').selectmenu("refresh");
	}
}
function serverIsUp(server_ip, server_id) {
	var cur_url = window.location.href.split('/').pop();
	if (cur_url.split('#')[1] == 'servers') {
		$.ajax({
			url: "/server/check/server/" + server_ip,
			success: function (data) {
				data = data.replace(/^\s+|\s+$/g, '');
				if (data.indexOf('up') != '-1') {
					$('#server_status-' + server_id).removeClass('serverNone');
					$('#server_status-' + server_id).removeClass('serverDown');
					$('#server_status-' + server_id).addClass('serverUp');
					$('#server_status-' + server_id).attr('title', 'Server is reachable');
				} else if (data.indexOf('down') != '-1') {
					$('#server_status-' + server_id).removeClass('serverNone');
					$('#server_status-' + server_id).removeClass('serverUp');
					$('#server_status-' + server_id).addClass('serverDown');
					$('#server_status-' + server_id).attr('title', 'Server is unreachable');
				} else {
					$('#server_status-' + server_id).removeClass('serverDown');
					$('#server_status-' + server_id).removeClass('serverUp');
					$('#server_status-' + server_id).addClass('serverNone');
					$('#server_status-' + server_id).attr('title', 'Cannot get server status');
				}
			}
		});
	}
}
function showServerInfo(id, ip) {
	var close_word = $('#translate').attr('data-close');
	var server_info = $('#translate').attr('data-server_info');
	$.ajax({
		url: "/server/system_info/get/" + ip + "/" +id,
		success: function (data) {
			data = data.replace(/\s+/g, ' ');
			if (data.indexOf('error:') != '-1' || data.indexOf('error_code') != '-1') {
				toastr.error(data);
			} else {
				$("#server-info").html(data);
				$("#dialog-server-info").dialog({
					resizable: false,
					height: "auto",
					width: 1000,
					modal: true,
					title: server_info + " (" + ip + ")",
					buttons: [{
						text: close_word,
						click: function () {
							$(this).dialog("close");
						}
					}]
				});
				$.getScript(awesome);
			}
		}
	});
}
function updateServerInfo(ip, id) {
	$.ajax({
		url: "/server/system_info/update/" + ip + "/" + id,
		success: function (data) {
			data = data.replace(/\s+/g, ' ');
			if (data.indexOf('error:') != '-1' || data.indexOf('error_code') != '-1') {
				toastr.error(data);
			} else {
				$("#server_info-" + id).html(data);
				$('#server_info-' + id).show();
				$('#server_info_link-' + id).attr('title', 'Hide System info');
				$.getScript(awesome);
			}
		}
	});
}
function viewFirewallRules(ip) {
	$.ajax({
		url: "/server/firewall/" + ip,
		success: function (data) {
			data = data.replace(/\s+/g, ' ');
			if (data.indexOf('danger') != '-1' || data.indexOf('unique') != '-1' || data.indexOf('error: ') != '-1') {
				toastr.error(data);
			} else {
				toastr.clear();
				$("#firewall_rules_body").html(data);
				$("#firewall_rules" ).dialog({
					resizable: false,
					height: "auto",
					width: 860,
					modal: true,
					title: "Firewall rules",
					buttons: {
						Close: function() {
							$( this ).dialog( "close" );
							$("#firewall_rules_body").html('');
						}
					}
				});
			}
		}
	} );
}
